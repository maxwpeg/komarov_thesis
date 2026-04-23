"""Shared application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")
load_dotenv(PROJECT_ROOT / ".env.local", override=True)


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_csv(name: str, default: list[str]) -> list[str]:
    raw = os.getenv(name)
    if raw is None:
        return default
    values = [item.strip() for item in raw.split(",")]
    return [item for item in values if item]


@dataclass(frozen=True)
class AppConfig:
    project_root: Path = PROJECT_ROOT
    uploads_dir: Path = PROJECT_ROOT / "uploads"
    outputs_dir: Path = PROJECT_ROOT / "outputs"
    debug_output_dir: Path = PROJECT_ROOT / "debug_output"
    object_storage_dir: Path = PROJECT_ROOT / "storage_objects"
    database_file: Path = PROJECT_ROOT / "floor_plans.db"
    feedback_file: Path = PROJECT_ROOT / "user_feedback.json"
    regular_font_path: Path = PROJECT_ROOT / "GOST_A.TTF"
    bold_font_path: Path = PROJECT_ROOT / "GOST_A_Bold.ttf"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    auth_cookie_name: str = os.getenv("AUTH_COOKIE_NAME", "auth_session")
    auth_session_ttl_hours: int = int(os.getenv("AUTH_SESSION_TTL_HOURS", "12"))
    auth_cookie_secure: bool = _env_flag("AUTH_COOKIE_SECURE", False)
    cors_allowed_origins: tuple[str, ...] = tuple(
        _env_csv(
            "CORS_ALLOWED_ORIGINS",
            ["http://127.0.0.1:3000", "http://localhost:3000"],
        )
    )
    bootstrap_developer_username: str | None = os.getenv("BOOTSTRAP_DEVELOPER_USERNAME")
    bootstrap_developer_full_name: str | None = os.getenv("BOOTSTRAP_DEVELOPER_FULL_NAME")
    bootstrap_developer_password: str | None = os.getenv("BOOTSTRAP_DEVELOPER_PASSWORD")
    asset_public_base_url: str | None = os.getenv("ASSET_PUBLIC_BASE_URL")
    worker_poll_interval_seconds: float = float(os.getenv("WORKER_POLL_INTERVAL_SECONDS", "2.0"))
    worker_max_attempts: int = int(os.getenv("WORKER_MAX_ATTEMPTS", "3"))
    run_inline_worker: bool = os.getenv("RUN_INLINE_WORKER", "1").lower() not in {"0", "false", "no"}

    @property
    def database_url(self) -> str:
        return os.getenv("DATABASE_URL", f"sqlite:///{self.database_file.as_posix()}")


settings = AppConfig()
