"""Authentication, sessions, and access-control helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import base64
import hashlib
import hmac
import os
import secrets
from typing import Any

from fastapi import Cookie, Depends, Response
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import get_db
from backend.errors import AppError
from backend.models import (
    AuthSession,
    CableRoute,
    Dimension,
    Door,
    FireAlarm,
    FloorPlan,
    Project,
    Room,
    SignalInstrument,
    SoueDevice,
    Stair,
    User,
    Wall,
    Window,
)


PASSWORD_ALGORITHM = "pbkdf2_sha256"
PASSWORD_ITERATIONS = 600_000
SESSION_LAST_SEEN_TOUCH_SECONDS = 300


@dataclass(slots=True)
class AuthenticatedUser:
    id: int
    username: str
    full_name: str
    role: str
    is_active: bool = True

    @property
    def is_developer(self) -> bool:
        return self.role == "developer"

    @property
    def is_engineer(self) -> bool:
        return self.role == "engineer"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "full_name": self.full_name,
            "role": self.role,
            "is_active": self.is_active,
        }

    @classmethod
    def from_model(cls, user: User) -> "AuthenticatedUser":
        return cls(
            id=int(user.id),
            username=str(user.username),
            full_name=str(user.full_name),
            role=str(user.role),
            is_active=bool(user.is_active),
        )


def normalize_username(username: str) -> str:
    normalized = username.strip().lower()
    if not normalized:
        raise AppError(400, "username_required", "Username is required")
    return normalized


def normalize_full_name(full_name: str) -> str:
    normalized = full_name.strip()
    if not normalized:
        raise AppError(400, "full_name_required", "Full name is required")
    return normalized


def validate_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in {"developer", "engineer"}:
        raise AppError(400, "invalid_user_role", "Role must be developer or engineer")
    return normalized


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def hash_password(password: str) -> str:
    if not password:
        raise AppError(400, "password_required", "Password is required")
    salt = os.urandom(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PASSWORD_ITERATIONS,
    )
    salt_b64 = base64.b64encode(salt).decode("ascii")
    hash_b64 = base64.b64encode(derived).decode("ascii")
    return f"{PASSWORD_ALGORITHM}${PASSWORD_ITERATIONS}${salt_b64}${hash_b64}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, raw_iterations, salt_b64, hash_b64 = password_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != PASSWORD_ALGORITHM:
        return False
    try:
        iterations = int(raw_iterations)
        salt = base64.b64decode(salt_b64.encode("ascii"))
        expected = base64.b64decode(hash_b64.encode("ascii"))
    except (TypeError, ValueError):
        return False
    actual = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations,
    )
    return hmac.compare_digest(actual, expected)


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_expiry() -> datetime:
    return _utcnow() + timedelta(hours=settings.auth_session_ttl_hours)


def set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        max_age=settings.auth_session_ttl_hours * 3600,
        expires=settings.auth_session_ttl_hours * 3600,
        path="/",
    )


def clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.auth_cookie_name,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )


def _load_user_by_username(db: Session, username: str) -> User | None:
    return db.query(User).filter(User.username == normalize_username(username)).first()


def bootstrap_first_developer(db: Session) -> None:
    if db.query(User.id).first() is not None:
        return
    if not (
        settings.bootstrap_developer_username
        and settings.bootstrap_developer_full_name
        and settings.bootstrap_developer_password
    ):
        raise RuntimeError(
            "BOOTSTRAP_DEVELOPER_USERNAME, BOOTSTRAP_DEVELOPER_FULL_NAME, and "
            "BOOTSTRAP_DEVELOPER_PASSWORD must be configured before first startup"
        )
    user = User(
        username=normalize_username(settings.bootstrap_developer_username),
        full_name=normalize_full_name(settings.bootstrap_developer_full_name),
        role="developer",
        password_hash=hash_password(settings.bootstrap_developer_password),
        is_active=True,
    )
    db.add(user)
    db.commit()


def authenticate_credentials(db: Session, username: str, password: str) -> User:
    user = _load_user_by_username(db, username)
    if user is None or not verify_password(password, user.password_hash):
        raise AppError(401, "invalid_credentials", "Invalid username or password")
    if not user.is_active:
        raise AppError(403, "user_inactive", "User account is deactivated")
    return user


def create_auth_session(db: Session, user: User) -> str:
    token = generate_session_token()
    session = AuthSession(
        user_id=user.id,
        token_hash=hash_session_token(token),
        expires_at=session_expiry(),
        last_seen_at=_utcnow(),
    )
    db.add(session)
    db.commit()
    return token


def invalidate_session_by_token(db: Session, raw_token: str | None) -> None:
    if not raw_token:
        return
    session = db.query(AuthSession).filter(AuthSession.token_hash == hash_session_token(raw_token)).first()
    if session is None:
        return
    db.delete(session)
    db.commit()


def _touch_session(db: Session, session: AuthSession) -> None:
    now = _utcnow()
    last_seen = _as_utc(session.last_seen_at)
    if last_seen is not None:
        delta = (now - last_seen).total_seconds()
        if delta < SESSION_LAST_SEEN_TOUCH_SECONDS:
            return
    session.last_seen_at = now
    db.commit()


def current_user_from_cookie(db: Session, raw_token: str | None) -> AuthenticatedUser:
    if not raw_token:
        raise AppError(401, "auth_required", "Authentication is required")
    session = db.query(AuthSession).filter(AuthSession.token_hash == hash_session_token(raw_token)).first()
    if session is None:
        raise AppError(401, "auth_required", "Authentication is required")
    expires_at = _as_utc(session.expires_at)
    if expires_at is None or expires_at <= _utcnow():
        db.delete(session)
        db.commit()
        raise AppError(401, "session_expired", "Authentication session has expired")
    user = session.user
    if user is None or not user.is_active:
        db.delete(session)
        db.commit()
        raise AppError(401, "auth_required", "Authentication is required")
    _touch_session(db, session)
    return AuthenticatedUser.from_model(user)


def require_current_user(
    db: Session = Depends(get_db),
    raw_token: str | None = Cookie(
        default=None,
        alias=settings.auth_cookie_name,
        description="Cookie с идентификатором серверной сессии авторизованного пользователя.",
    ),
) -> AuthenticatedUser:
    return current_user_from_cookie(db, raw_token)


def require_developer(current_user: AuthenticatedUser = Depends(require_current_user)) -> AuthenticatedUser:
    if not current_user.is_developer:
        raise AppError(403, "developer_role_required", "Developer role is required")
    return current_user


def ensure_project_access(db: Session, current_user: AuthenticatedUser, project_id: int) -> Project:
    project = db.query(Project).filter(Project.id == project_id).first()
    if project is None:
        raise AppError(404, "project_not_found", "Project not found")
    if current_user.is_developer:
        return project
    if project.owner_user_id != current_user.id:
        raise AppError(403, "project_access_denied", "You do not have access to this project")
    return project


def require_project_access(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
) -> AuthenticatedUser:
    ensure_project_access(db, current_user, project_id)
    return current_user


def ensure_floor_plan_access(db: Session, current_user: AuthenticatedUser, floor_plan_id: int) -> FloorPlan:
    floor_plan = db.query(FloorPlan).filter(FloorPlan.id == floor_plan_id).first()
    if floor_plan is None:
        raise AppError(404, "floor_plan_not_found", "Floor plan not found")
    ensure_project_access(db, current_user, int(floor_plan.project_id))
    return floor_plan


def require_floor_plan_access(
    floor_plan_id: int,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
) -> AuthenticatedUser:
    ensure_floor_plan_access(db, current_user, floor_plan_id)
    return current_user


def _entity_project_id(db: Session, model: Any, entity_id: int, not_found_code: str, not_found_detail: str) -> int:
    entity = db.query(model).filter(model.id == entity_id).first()
    if entity is None:
        raise AppError(404, not_found_code, not_found_detail)
    floor_plan = db.query(FloorPlan).filter(FloorPlan.id == entity.floor_plan_id).first()
    if floor_plan is None:
        raise AppError(404, "floor_plan_not_found", "Floor plan not found")
    return int(floor_plan.project_id)


def ensure_entity_access(
    db: Session,
    current_user: AuthenticatedUser,
    model: Any,
    entity_id: int,
    not_found_code: str,
    not_found_detail: str,
) -> None:
    project_id = _entity_project_id(db, model, entity_id, not_found_code, not_found_detail)
    ensure_project_access(db, current_user, project_id)


def require_wall_access(
    wall_id: int,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
) -> AuthenticatedUser:
    ensure_entity_access(db, current_user, Wall, wall_id, "wall_not_found", "Wall not found")
    return current_user


def require_door_access(
    door_id: int,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
) -> AuthenticatedUser:
    ensure_entity_access(db, current_user, Door, door_id, "door_not_found", "Door not found")
    return current_user


def require_window_access(
    window_id: int,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
) -> AuthenticatedUser:
    ensure_entity_access(db, current_user, Window, window_id, "window_not_found", "Window not found")
    return current_user


def require_stair_access(
    stair_id: int,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
) -> AuthenticatedUser:
    ensure_entity_access(db, current_user, Stair, stair_id, "stair_not_found", "Stair not found")
    return current_user


def require_room_access(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
) -> AuthenticatedUser:
    ensure_entity_access(db, current_user, Room, room_id, "room_not_found", "Room not found")
    return current_user


def require_dimension_access(
    dimension_id: int,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
) -> AuthenticatedUser:
    ensure_entity_access(db, current_user, Dimension, dimension_id, "dimension_not_found", "Dimension not found")
    return current_user


def require_fire_alarm_access(
    fire_alarm_id: int,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
) -> AuthenticatedUser:
    ensure_entity_access(
        db,
        current_user,
        FireAlarm,
        fire_alarm_id,
        "fire_alarm_not_found",
        "Fire alarm not found",
    )
    return current_user


def require_soue_device_access(
    soue_device_id: int,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
) -> AuthenticatedUser:
    ensure_entity_access(
        db,
        current_user,
        SoueDevice,
        soue_device_id,
        "soue_device_not_found",
        "SOUE device not found",
    )
    return current_user


def require_signal_instrument_access(
    instrument_id: int,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
) -> AuthenticatedUser:
    ensure_entity_access(
        db,
        current_user,
        SignalInstrument,
        instrument_id,
        "signal_instrument_not_found",
        "Signal instrument not found",
    )
    return current_user


def require_cable_route_access(
    route_id: int,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
) -> AuthenticatedUser:
    ensure_entity_access(db, current_user, CableRoute, route_id, "cable_route_not_found", "Cable route not found")
    return current_user


def ensure_owner_user_can_be_assigned(db: Session, owner_user_id: int | None) -> User | None:
    if owner_user_id is None:
        return None
    owner = db.query(User).filter(User.id == owner_user_id).first()
    if owner is None:
        raise AppError(400, "owner_user_not_found", "Owner user not found")
    if not owner.is_active:
        raise AppError(400, "owner_user_inactive", "Owner user must be active")
    if owner.role != "engineer":
        raise AppError(400, "owner_user_must_be_engineer", "Owner user must have engineer role")
    return owner


def count_active_developers(db: Session, *, exclude_user_id: int | None = None) -> int:
    query = db.query(User).filter(User.role == "developer", User.is_active.is_(True))
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return int(query.count())
