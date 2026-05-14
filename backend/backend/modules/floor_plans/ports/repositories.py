"""Repository contracts for floor plans."""

from __future__ import annotations

from typing import Protocol

from fastapi import UploadFile

from backend.modules.floor_plans.domain.entities import FloorPlanRecord
from backend.schemas import FloorPlanCreate, FloorPlanUpdate


class FloorPlanRepository(Protocol):
    """Persistence contract for floor-plan aggregates."""

    def create(self, payload: FloorPlanCreate, upload_file: UploadFile | None = None) -> FloorPlanRecord:
        """Create a floor plan."""

    def get(self, floor_plan_id: int, include_elements: bool = True) -> FloorPlanRecord:
        """Return a floor plan aggregate snapshot."""

    def list_for_project(self, project_id: int) -> list[FloorPlanRecord]:
        """Return floor plans for a project."""

    def update(self, floor_plan_id: int, payload: FloorPlanUpdate) -> FloorPlanRecord:
        """Update a floor plan."""

    def delete(self, floor_plan_id: int) -> None:
        """Delete a floor plan."""
