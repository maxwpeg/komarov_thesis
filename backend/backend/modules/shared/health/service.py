"""Health/readiness probes for runtime dependencies."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.config import AppConfig
from backend.schemas import HealthRead


class HealthService:
    """Evaluates runtime readiness of the backend."""

    def __init__(self, *, engine: Engine, settings: AppConfig):
        self.engine = engine
        self.settings = settings

    def live(self) -> HealthRead:
        return HealthRead(status="ok", message="Floor Plan API is running")

    def ready(self) -> dict[str, object]:
        checks = {
            "database": self._database_check(),
            "storage": self._storage_check(),
            "pdf_fonts": self._pdf_check(),
        }
        overall = "ok" if all(item["status"] == "ok" for item in checks.values()) else "degraded"
        return {
            "status": overall,
            "message": "Runtime dependencies checked",
            "checks": checks,
        }

    def _database_check(self) -> dict[str, object]:
        try:
            with self.engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except Exception as exc:  # pragma: no cover - exercised in runtime failures
            return {"status": "error", "detail": str(exc)}
        return {"status": "ok"}

    def _storage_check(self) -> dict[str, object]:
        required_paths = (
            self.settings.uploads_dir,
            self.settings.outputs_dir,
            self.settings.debug_output_dir,
        )
        missing = [str(path) for path in required_paths if not Path(path).exists()]
        if missing:
            return {"status": "error", "detail": f"Missing paths: {', '.join(missing)}"}
        return {"status": "ok"}

    def _pdf_check(self) -> dict[str, object]:
        missing = [
            str(path)
            for path in (self.settings.regular_font_path, self.settings.bold_font_path)
            if not path.exists()
        ]
        if missing:
            return {"status": "degraded", "detail": f"Missing font files: {', '.join(missing)}"}
        return {"status": "ok"}
