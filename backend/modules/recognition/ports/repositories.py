"""Repository and adapter contracts for recognition."""

from __future__ import annotations

from typing import Protocol


class RecognitionRepository(Protocol):
    """Persistence contract for recognition workflows."""

    def get_floor_plan(self, floor_plan_id: int):
        """Return a floor plan model."""

    def get_recognition(self, floor_plan_id: int):
        """Return a recognition record or None."""

    def create_recognition(self, data: dict):
        """Create a recognition persistence entity."""

    def get_feedback_sample(self, recognition_id: int):
        """Return an existing feedback sample for the recognition or None."""

    def list_feedback_samples_for_export(self) -> list:
        """List approved, not-yet-exported feedback samples."""

    def create_feedback_sample(self, data: dict):
        """Create a feedback persistence entity."""

    def list_existing_rooms(self, floor_plan_id: int) -> list:
        """List current rooms before re-recognition."""

    def replace_detection_result(self, floor_plan_id: int, *, walls, doors, windows, rooms, dimensions) -> None:
        """Replace the current detection result for a floor plan."""

    def add(self, entity) -> None:
        """Track a persistence entity for insertion."""

    def flush(self) -> None:
        """Flush the current unit of work."""


class RecognitionAdapterPort(Protocol):
    """Adapter contract for external recognition engine."""

    def recognize(self, image_path: str, *, floor_plan_id: int, debug_dir: str | None):
        """Run recognition and return raw integration output."""
