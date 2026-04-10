"""Floor plan application service."""

from __future__ import annotations

from sqlalchemy.orm import Session, selectinload

from backend.errors import AppError
from backend.models import (
    CableRoute as CableRouteModel,
    FloorPlan as FloorPlanModel,
    Project as ProjectModel,
    SignalInstrument as SignalInstrumentModel,
    ZkspcZone as ZkspcZoneModel,
)
from backend.schemas import FloorPlanCreate, FloorPlanUpdate
from backend.services.storage_service import StorageService


class FloorPlanService:
    """Application service for floor plan operations."""

    def __init__(self, db: Session, storage: StorageService):
        self.db = db
        self.storage = storage

    def create_floor_plan(
        self,
        payload: FloorPlanCreate,
        upload_file=None,
    ) -> FloorPlanModel:
        project = self.db.query(ProjectModel).filter(ProjectModel.id == payload.project_id).first()
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

        self.db.add(floor_plan)
        self.db.commit()
        self.db.refresh(floor_plan)
        return floor_plan

    def get_floor_plan(self, floor_plan_id: int, include_elements: bool = True) -> FloorPlanModel:
        query = self.db.query(FloorPlanModel)
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

    def list_project_floor_plans(self, project_id: int) -> list[FloorPlanModel]:
        return (
            self.db.query(FloorPlanModel)
            .filter(FloorPlanModel.project_id == project_id)
            .order_by(FloorPlanModel.floor_number.asc())
            .all()
        )

    def delete_floor_plan(self, floor_plan_id: int) -> None:
        floor_plan = self.get_floor_plan(floor_plan_id, include_elements=False)
        self.storage.delete_relative_path(floor_plan.original_image_path)
        self.db.delete(floor_plan)
        self.db.commit()

    def update_floor_plan(self, floor_plan_id: int, payload: FloorPlanUpdate) -> FloorPlanModel:
        floor_plan = self.get_floor_plan(floor_plan_id, include_elements=False)
        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(floor_plan, field, value)
        if "scale_factor" in updates and updates["scale_factor"] is not None:
            floor_plan.scale_source = "manual"
        self.db.commit()
        self.db.refresh(floor_plan)
        return floor_plan
