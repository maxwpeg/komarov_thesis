"""Floor-plan application use cases."""

from __future__ import annotations

from fastapi import UploadFile

from backend.modules.floor_plans.domain.entities import FloorPlanRecord
from backend.modules.floor_plans.ports.repositories import FloorPlanRepository
from backend.modules.shared.application.unit_of_work import UnitOfWork
from backend.schemas import FloorPlanCreate, FloorPlanUpdate


class FloorPlanUseCases:
    """Application facade for floor-plan operations."""

    def __init__(self, repository: FloorPlanRepository, uow: UnitOfWork):
        self.repository = repository
        self.uow = uow

    def create_floor_plan(self, payload: FloorPlanCreate, upload_file: UploadFile | None = None) -> FloorPlanRecord:
        return self._write(lambda: self.repository.create(payload, upload_file=upload_file))

    def get_floor_plan(self, floor_plan_id: int, include_elements: bool = True) -> FloorPlanRecord:
        return self.repository.get(floor_plan_id, include_elements=include_elements)

    def list_project_floor_plans(self, project_id: int) -> list[FloorPlanRecord]:
        return self.repository.list_for_project(project_id)

    def update_floor_plan(self, floor_plan_id: int, payload: FloorPlanUpdate) -> FloorPlanRecord:
        return self._write(lambda: self.repository.update(floor_plan_id, payload))

    def delete_floor_plan(self, floor_plan_id: int) -> None:
        self._write(lambda: self.repository.delete(floor_plan_id))

    def _write(self, operation):
        try:
            result = operation()
            self.uow.commit()
            return result
        except Exception:
            self.uow.rollback()
            raise
