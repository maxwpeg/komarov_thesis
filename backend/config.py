"""Shared application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class AppConfig:
    project_root: Path = PROJECT_ROOT
    uploads_dir: Path = PROJECT_ROOT / "uploads"
    outputs_dir: Path = PROJECT_ROOT / "outputs"
    debug_output_dir: Path = PROJECT_ROOT / "debug_output"
    database_file: Path = PROJECT_ROOT / "floor_plans.db"
    feedback_file: Path = PROJECT_ROOT / "user_feedback.json"
    regular_font_path: Path = PROJECT_ROOT / "GOST_A.TTF"
    bold_font_path: Path = PROJECT_ROOT / "GOST_A_Bold.ttf"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @property
    def database_url(self) -> str:
        return os.getenv("DATABASE_URL", f"sqlite:///{self.database_file.as_posix()}")


settings = AppConfig()

