"""SQLAlchemy-backed floor-plan repository."""

from __future__ import annotations

from fastapi import UploadFile
from sqlalchemy.orm import Session, selectinload

from backend.errors import AppError
from backend.modules.shared.infrastructure.persistence.models import (
    FloorPlan as FloorPlanModel,
    Project as ProjectModel,
    ZkspcZone as ZkspcZoneModel,
)
from backend.modules.floor_plans.domain.entities import FloorPlanRecord
from backend.modules.floor_plans.ports.repositories import FloorPlanRepository
from backend.modules.shared.application.ports import FileStoragePort
from backend.schemas import FloorPlanCreate, FloorPlanUpdate


class SqlAlchemyFloorPlanRepository(FloorPlanRepository):
    """Repository implementation over the current floor-plan schema."""

    def __init__(self, session: Session, storage: FileStoragePort):
        self.session = session
        self.storage = storage

    def create(self, payload: FloorPlanCreate, upload_file: UploadFile | None = None) -> FloorPlanRecord:
        project = self.session.query(ProjectModel).filter(ProjectModel.id == payload.project_id).first()
        if project is None:
            raise AppError(404, "project_not_found", "Project not found")

        floor_plan = FloorPlanModel(
            project_id=payload.project_id,
            floor_number=payload.floor_number,
            name=payload.name or f"Floor {payload.floor_number}",
            scale_factor=payload.scale_factor,
            ceiling_height_mm=payload.ceiling_height_mm,
            active_signal_system_type=payload.active_signal_system_type,
        )
        if upload_file is not None:
            saved = self.storage.save_upload(upload_file, payload.project_id, payload.floor_number)
            floor_plan.original_image_path = saved.relative_path
            floor_plan.image_width = saved.width
            floor_plan.image_height = saved.height

        self.session.add(floor_plan)
        self.session.flush()
        return FloorPlanRecord.from_model(floor_plan, include_elements=True)

    def get(self, floor_plan_id: int, include_elements: bool = True) -> FloorPlanRecord:
        return FloorPlanRecord.from_model(
            self._get_model(floor_plan_id, include_elements=include_elements),
            include_elements=include_elements,
        )

    def list_for_project(self, project_id: int) -> list[FloorPlanRecord]:
        floor_plans = (
            self.session.query(FloorPlanModel)
            .filter(FloorPlanModel.project_id == project_id)
            .order_by(FloorPlanModel.floor_number.asc())
            .all()
        )
        return [FloorPlanRecord.from_model(item, include_elements=False) for item in floor_plans]

    def update(self, floor_plan_id: int, payload: FloorPlanUpdate) -> FloorPlanRecord:
        floor_plan = self._get_model(floor_plan_id, include_elements=False)
        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(floor_plan, field, value)
        if "scale_factor" in updates and updates["scale_factor"] is not None:
            floor_plan.scale_source = "manual"
        self.session.flush()
        return FloorPlanRecord.from_model(floor_plan, include_elements=True)

    def delete(self, floor_plan_id: int) -> None:
        floor_plan = self._get_model(floor_plan_id, include_elements=False)
        self.storage.delete_relative_path(floor_plan.original_image_path)
        self.session.delete(floor_plan)
        self.session.flush()

    def _get_model(self, floor_plan_id: int, *, include_elements: bool) -> FloorPlanModel:
        query = self.session.query(FloorPlanModel)
        if include_elements:
            query = query.options(
                selectinload(FloorPlanModel.walls),
                selectinload(FloorPlanModel.stairs),
                selectinload(FloorPlanModel.doors),
                selectinload(FloorPlanModel.windows),
                selectinload(FloorPlanModel.rooms),
                selectinload(FloorPlanModel.dimensions),
                selectinload(FloorPlanModel.fire_alarms),
                selectinload(FloorPlanModel.zkspc_zones).selectinload(ZkspcZoneModel.room_links),
                selectinload(FloorPlanModel.signal_instruments),
                selectinload(FloorPlanModel.cable_routes),
            )
        floor_plan = query.filter(FloorPlanModel.id == floor_plan_id).first()
        if floor_plan is None:
            raise AppError(404, "floor_plan_not_found", "Floor plan not found")
        return floor_plan
