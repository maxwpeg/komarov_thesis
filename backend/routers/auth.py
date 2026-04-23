"""Authentication routes."""

from __future__ import annotations

from fastapi import APIRouter, Cookie, Depends, Response
from sqlalchemy.orm import Session

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
from backend.schemas import CurrentUserRead, LoginRequest, MessageRead


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
    response: Response,
    db: Session = Depends(get_db),
) -> CurrentUserRead:
    user = authenticate_credentials(db, payload.username, payload.password)
    token = create_auth_session(db, user)
    set_auth_cookie(response, token)
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
