"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.orm import Session

from backend.audit import record_audit_event
from backend.auth import (
    AuthenticatedUser,
    authenticate_credentials,
    clear_auth_cookie,
    create_auth_session,
    invalidate_session_by_token,
    require_current_user,
    set_auth_cookie,
)
from backend.config import settings
from backend.database import get_db
from backend.errors import AppError
from backend.schemas import CurrentUserRead, LoginRequest, MessageRead
from backend.security import enforce_rate_limit


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=CurrentUserRead,
    summary="Выполнить вход в систему",
    description=(
        "Проверяет имя пользователя и пароль, создает серверную сессию и "
        "возвращает сведения о текущем пользователе."
    ),
    responses={
        200: {"description": "Вход выполнен успешно, сессия создана."},
        401: {"description": "Переданы неверные учетные данные."},
        403: {"description": "Учетная запись пользователя деактивирована."},
    },
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> CurrentUserRead:
    enforce_rate_limit(
        request,
        "auth_login",
        discriminator=payload.username,
        limit=settings.login_rate_limit_count,
        window_seconds=settings.login_rate_limit_window_seconds,
    )
    try:
        user = authenticate_credentials(db, payload.username, payload.password)
    except AppError:
        record_audit_event(
            db,
            "auth_login_failed",
            use_case="Login",
            payload={"username": payload.username, "client": request.client.host if request.client else None},
        )
        db.commit()
        raise
    token = create_auth_session(db, user)
    set_auth_cookie(response, token)
    record_audit_event(
        db,
        "auth_login_succeeded",
        use_case="Login",
        user_id=int(user.id),
        payload={"username": user.username, "client": request.client.host if request.client else None},
    )
    db.commit()
    return CurrentUserRead.model_validate(user.to_dict())


@router.post(
    "/logout",
    response_model=MessageRead,
    summary="Завершить пользовательскую сессию",
    description=(
        "Инвалидирует текущую серверную сессию, если cookie присутствует, и "
        "очищает auth-cookie в браузере."
    ),
    responses={
        200: {"description": "Сессия завершена, cookie очищена."},
    },
)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    raw_token: str | None = Cookie(
        default=None,
        alias=settings.auth_cookie_name,
        description="Cookie с идентификатором текущей пользовательской сессии.",
    ),
) -> MessageRead:
    invalidate_session_by_token(db, raw_token)
    clear_auth_cookie(response)
    record_audit_event(db, "auth_logout", use_case="Logout", payload={"had_cookie": bool(raw_token)})
    db.commit()
    return MessageRead(message="Logged out")


@router.get(
    "/me",
    response_model=CurrentUserRead,
    summary="Получить текущего пользователя",
    description=(
        "Возвращает профиль авторизованного пользователя, связанного с текущей "
        "серверной сессией."
    ),
    responses={
        200: {"description": "Профиль текущего пользователя успешно получен."},
        401: {"description": "Пользователь не авторизован или сессия истекла."},
    },
)
def get_current_user(
    current_user: AuthenticatedUser = Depends(require_current_user),
) -> CurrentUserRead:
    return CurrentUserRead.model_validate(current_user.to_dict())
