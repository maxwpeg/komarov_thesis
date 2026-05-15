"""Cross-cutting ports used by the modular monolith."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from fastapi import UploadFile

from backend.modules.shared.infrastructure.storage import SavedUpload


class FileStoragePort(Protocol):
    """Abstraction over persistent file storage."""

    def save_upload(self, upload: UploadFile, project_id: int, floor_number: int) -> SavedUpload:
        """Persist an uploaded floor plan image."""

    def delete_relative_path(self, relative_path: str | None) -> None:
        """Delete a previously stored relative path if it exists."""

    def absolute_path(self, relative_path: str | None) -> Path | None:
        """Resolve a persisted relative path to an absolute file-system path."""

    def debug_dir(self, floor_plan_id: int) -> Path:
        """Return or create the per-floor-plan debug directory."""

    def list_debug_images(self, relative_dir: str | None) -> list[dict[str, str]]:
        """List debug images for a persisted debug directory."""


class EventPublisherPort(Protocol):
    """Publishes domain or audit events."""

    def publish(self, event_name: str, payload: dict[str, Any]) -> None:
        """Publish a structured event."""


class TaskDispatcherPort(Protocol):
    """Dispatches expensive work asynchronously or in-process."""

    def dispatch(self, task_name: str, payload: dict[str, Any]) -> None:
        """Schedule work for execution."""
