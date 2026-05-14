"""User management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from backend.audit import record_audit_event
from backend.auth import (
    AuthenticatedUser,
    count_active_developers,
    hash_password,
    normalize_full_name,
    normalize_username,
    require_developer,
    validate_role,
)
from backend.database import get_db
from backend.errors import AppError
from backend.models import User
from backend.schemas import MessageRead, UserCreate, UserRead, UserResetPasswordRequest, UserUpdate
from backend.security import enforce_rate_limit
from backend.config import settings


router = APIRouter(prefix="/api/users", tags=["users"])


def _user_read(user: User) -> UserRead:
    return UserRead.model_validate(user.to_dict())


def _get_user(db: Session, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise AppError(404, "user_not_found", "User not found")
    return user


def _ensure_username_available(db: Session, username: str, *, exclude_user_id: int | None = None) -> None:
    query = db.query(User).filter(User.username == username)
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    if query.first() is not None:
        raise AppError(409, "username_already_exists", "Username is already taken")


def _ensure_last_developer_can_be_changed(
    db: Session,
    user: User,
    *,
    next_role: str | None = None,
    next_is_active: bool | None = None,
) -> None:
    resulting_role = next_role if next_role is not None else user.role
    resulting_is_active = next_is_active if next_is_active is not None else user.is_active
    if not (user.role == "developer" and user.is_active):
        return
    if resulting_role == "developer" and resulting_is_active:
        return
    if count_active_developers(db, exclude_user_id=user.id) == 0:
        raise AppError(409, "last_active_developer_required", "At least one active developer must remain")


@router.get(
    "",
    response_model=list[UserRead],
    summary="Получить список пользователей",
    description=(
        "Возвращает всех пользователей системы с их ролями и признаками "
        "активности. Доступно только разработчикам."
    ),
    responses={
        200: {"description": "Список пользователей успешно получен."},
        403: {"description": "Доступ разрешен только пользователю с ролью developer."},
    },
)
def list_users(
    _: AuthenticatedUser = Depends(require_developer),
    db: Session = Depends(get_db),
) -> list[UserRead]:
    users = db.query(User).order_by(User.full_name.asc(), User.username.asc()).all()
    return [_user_read(user) for user in users]


@router.post(
    "",
    response_model=UserRead,
    summary="Создать пользователя",
    description=(
        "Создает новую учетную запись пользователя, задает роль, пароль и "
        "начальный статус активности. Доступно только разработчикам."
    ),
    responses={
        200: {"description": "Пользователь успешно создан."},
        403: {"description": "Доступ разрешен только пользователю с ролью developer."},
        409: {"description": "Указанное имя пользователя уже занято."},
    },
)
def create_user(
    payload: UserCreate,
    current_user: AuthenticatedUser = Depends(require_developer),
    db: Session = Depends(get_db),
) -> UserRead:
    username = normalize_username(payload.username)
    _ensure_username_available(db, username)
    user = User(
        username=username,
        full_name=normalize_full_name(payload.full_name),
        role=validate_role(payload.role),
        password_hash=hash_password(payload.password),
        is_active=payload.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    record_audit_event(
        db,
        "user_created",
        use_case="CreateUser",
        user_id=current_user.id,
        payload={"target_user_id": user.id, "username": user.username, "role": user.role},
    )
    db.commit()
    return _user_read(user)


@router.patch(
    "/{user_id}",
    response_model=UserRead,
    summary="Изменить пользователя",
    description=(
        "Частично обновляет профиль пользователя, его роль или статус "
        "активности. Запрещает деактивацию или понижение последнего активного "
        "разработчика."
    ),
    responses={
        200: {"description": "Пользователь успешно обновлен."},
        403: {"description": "Доступ разрешен только пользователю с ролью developer."},
        404: {"description": "Пользователь с указанным идентификатором не найден."},
        409: {"description": "Нарушено правило уникальности имени или последнего developer."},
    },
)
def update_user(
    user_id: int,
    payload: UserUpdate,
    current_user: AuthenticatedUser = Depends(require_developer),
    db: Session = Depends(get_db),
) -> UserRead:
    user = _get_user(db, user_id)
    updates = payload.model_dump(exclude_unset=True)

    next_role = validate_role(updates["role"]) if "role" in updates and updates["role"] is not None else None
    next_is_active = bool(updates["is_active"]) if "is_active" in updates and updates["is_active"] is not None else None
    _ensure_last_developer_can_be_changed(db, user, next_role=next_role, next_is_active=next_is_active)

    if "username" in updates and updates["username"] is not None:
        user.username = normalize_username(updates["username"])
        _ensure_username_available(db, user.username, exclude_user_id=user.id)
    if "full_name" in updates and updates["full_name"] is not None:
        user.full_name = normalize_full_name(updates["full_name"])
    if next_role is not None:
        user.role = next_role
    if next_is_active is not None:
        user.is_active = next_is_active

    db.commit()
    db.refresh(user)
    record_audit_event(
        db,
        "user_updated",
        use_case="UpdateUser",
        user_id=current_user.id,
        payload={"target_user_id": user.id, "fields": sorted(updates.keys())},
    )
    db.commit()
    return _user_read(user)


@router.post(
    "/{user_id}/reset-password",
    response_model=MessageRead,
    summary="Сбросить пароль пользователя",
    description=(
        "Заменяет пароль указанного пользователя на новый. Доступно только "
        "разработчикам."
    ),
    responses={
        200: {"description": "Пароль пользователя успешно обновлен."},
        403: {"description": "Доступ разрешен только пользователю с ролью developer."},
        404: {"description": "Пользователь с указанным идентификатором не найден."},
    },
)
def reset_user_password(
    user_id: int,
    payload: UserResetPasswordRequest,
    request: Request,
    current_user: AuthenticatedUser = Depends(require_developer),
    db: Session = Depends(get_db),
) -> MessageRead:
    enforce_rate_limit(
        request,
        "user_password_reset",
        discriminator=str(user_id),
        limit=settings.login_rate_limit_count,
        window_seconds=settings.login_rate_limit_window_seconds,
    )
    user = _get_user(db, user_id)
    user.password_hash = hash_password(payload.password)
    db.commit()
    record_audit_event(
        db,
        "user_password_reset",
        use_case="ResetUserPassword",
        user_id=current_user.id,
        payload={"target_user_id": user.id, "username": user.username},
    )
    db.commit()
    return MessageRead(message=f"Password reset for {user.username}")
