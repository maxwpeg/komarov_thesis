"""SQLAlchemy repositories for element geometry."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.errors import AppError
from backend.modules.shared.infrastructure.persistence.models import (
    Dimension as DimensionModel,
    Door as DoorModel,
    FireAlarm as FireAlarmModel,
    FloorPlan as FloorPlanModel,
    Room as RoomModel,
    Stair as StairModel,
    Wall as WallModel,
    Window as WindowModel,
    ZkspcZone as ZkspcZoneModel,
)
from backend.modules.elements_geometry.ports.repositories import ElementsRepository


class SqlAlchemyElementsRepository(ElementsRepository):
    """SQLAlchemy-backed repository for element geometry aggregates."""

    def __init__(self, session: Session):
        self.session = session

    def get_floor_plan(self, floor_plan_id: int) -> FloorPlanModel:
        floor_plan = self.session.query(FloorPlanModel).filter(FloorPlanModel.id == floor_plan_id).first()
        if floor_plan is None:
            raise AppError(404, "floor_plan_not_found", "Floor plan not found")
        return floor_plan

    def get_wall(self, wall_id: int) -> WallModel:
        return self._get_or_404(WallModel, wall_id, "wall_not_found", "Wall not found")

    def get_door(self, door_id: int) -> DoorModel:
        return self._get_or_404(DoorModel, door_id, "door_not_found", "Door not found")

    def get_window(self, window_id: int) -> WindowModel:
        return self._get_or_404(WindowModel, window_id, "window_not_found", "Window not found")

    def get_stair(self, stair_id: int) -> StairModel:
        return self._get_or_404(StairModel, stair_id, "stair_not_found", "Stair not found")

    def get_room(self, room_id: int) -> RoomModel:
        return self._get_or_404(RoomModel, room_id, "room_not_found", "Room not found")

    def get_dimension(self, dimension_id: int) -> DimensionModel:
        return self._get_or_404(DimensionModel, dimension_id, "dimension_not_found", "Dimension not found")

    def get_fire_alarm(self, fire_alarm_id: int) -> FireAlarmModel:
        return self._get_or_404(FireAlarmModel, fire_alarm_id, "fire_alarm_not_found", "Fire alarm not found")

    def list_walls(self, floor_plan_id: int) -> list[WallModel]:
        return self.session.query(WallModel).filter(WallModel.floor_plan_id == floor_plan_id).all()

    def list_doors(self, floor_plan_id: int) -> list[DoorModel]:
        return self.session.query(DoorModel).filter(DoorModel.floor_plan_id == floor_plan_id).all()

    def list_windows(self, floor_plan_id: int) -> list[WindowModel]:
        return self.session.query(WindowModel).filter(WindowModel.floor_plan_id == floor_plan_id).all()

    def list_stairs(self, floor_plan_id: int) -> list[StairModel]:
        return self.session.query(StairModel).filter(StairModel.floor_plan_id == floor_plan_id).all()

    def list_rooms(self, floor_plan_id: int) -> list[RoomModel]:
        return self.session.query(RoomModel).filter(RoomModel.floor_plan_id == floor_plan_id).all()

    def list_dimensions(self, floor_plan_id: int) -> list[DimensionModel]:
        return self.session.query(DimensionModel).filter(DimensionModel.floor_plan_id == floor_plan_id).all()

    def list_fire_alarms(self, floor_plan_id: int) -> list[FireAlarmModel]:
        return self.session.query(FireAlarmModel).filter(FireAlarmModel.floor_plan_id == floor_plan_id).all()

    def list_zkspc_zones(self, floor_plan_id: int) -> list[ZkspcZoneModel]:
        return (
            self.session.query(ZkspcZoneModel)
            .filter(ZkspcZoneModel.floor_plan_id == floor_plan_id)
            .order_by(ZkspcZoneModel.zone_number.asc())
            .all()
        )

    def create_wall(self, data: dict) -> WallModel:
        return WallModel(**data)

    def create_door(self, data: dict) -> DoorModel:
        return DoorModel(**data)

    def create_window(self, data: dict) -> WindowModel:
        return WindowModel(**data)

    def create_stair(self, data: dict) -> StairModel:
        return StairModel(**data)

    def create_room(self, data: dict) -> RoomModel:
        return RoomModel(**data)

    def create_dimension(self, data: dict) -> DimensionModel:
        return DimensionModel(**data)

    def create_fire_alarm(self, data: dict) -> FireAlarmModel:
        return FireAlarmModel(**data)

    def add(self, entity) -> None:
        self.session.add(entity)

    def delete(self, entity) -> None:
        self.session.delete(entity)

    def flush(self) -> None:
        self.session.flush()

    def refresh(self, entity) -> None:
        self.session.refresh(entity)

    def get_optional_by_type(self, element_type: str, entity_id: int):
        model_map = {
            "wall": WallModel,
            "stair": StairModel,
            "door": DoorModel,
            "window": WindowModel,
            "fire_alarm": FireAlarmModel,
            "room": RoomModel,
            "dimension": DimensionModel,
        }
        model = model_map[element_type]
        return self.session.query(model).filter(model.id == entity_id).first()

    def _get_or_404(self, model, entity_id: int, code: str, detail: str):
        entity = self.session.query(model).filter(model.id == entity_id).first()
        if entity is None:
            raise AppError(404, code, detail)
        return entity
