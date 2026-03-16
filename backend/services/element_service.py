"""Architectural element application service."""

from __future__ import annotations

import math
from typing import Any

from sqlalchemy.orm import Session

from backend.errors import AppError
from backend.fire_alarm_placement import locate_fire_alarm_metadata
from backend.models import (
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
from backend.schemas import (
    BatchSaveRequest,
    DimensionCreate,
    DoorCreate,
    DoorUpdate,
    FireAlarmCreate,
    FireAlarmUpdate,
    RoomCreate,
    RoomUpdate,
    StairCreate,
    StairUpdate,
    WallCreate,
    WallUpdate,
    WindowCreate,
    WindowUpdate,
)
from backend.services.pipeline_state_helpers import update_signal_branch_state


class ElementService:
    """CRUD service for floor plan elements."""

    def __init__(self, db: Session):
        self.db = db

    def list_walls(self, floor_plan_id: int) -> list[WallModel]:
        return self.db.query(WallModel).filter(WallModel.floor_plan_id == floor_plan_id).all()

    def create_wall(self, payload: WallCreate) -> WallModel:
        wall = WallModel(**payload.model_dump())
        self.db.add(wall)
        self.db.commit()
        self.db.refresh(wall)
        return wall

    def update_wall(self, wall_id: int, payload: WallUpdate) -> WallModel:
        wall = self._get_or_404(WallModel, wall_id, "wall_not_found", "Wall not found")
        self._apply_update(wall, payload.model_dump(exclude_unset=True))
        self.relink_or_prune_openings(wall.floor_plan_id, delete_invalid=True)
        self.db.commit()
        self.db.refresh(wall)
        return wall

    def delete_wall(self, wall_id: int) -> None:
        wall = self._get_or_404(WallModel, wall_id, "wall_not_found", "Wall not found")
        floor_plan_id = wall.floor_plan_id
        self.db.delete(wall)
        self.db.flush()
        self.relink_or_prune_openings(floor_plan_id, delete_invalid=True)
        self.db.commit()

    def list_doors(self, floor_plan_id: int) -> list[DoorModel]:
        return self.db.query(DoorModel).filter(DoorModel.floor_plan_id == floor_plan_id).all()

    def create_door(self, payload: DoorCreate) -> DoorModel:
        data = self._normalize_opening_payload(payload.model_dump())
        door = DoorModel(**data)
        self.db.add(door)
        self.db.commit()
        self.db.refresh(door)
        return door

    def update_door(self, door_id: int, payload: DoorUpdate) -> DoorModel:
        door = self._get_or_404(DoorModel, door_id, "door_not_found", "Door not found")
        updates = payload.model_dump(exclude_unset=True)
        merged = self._normalize_opening_payload({
            "floor_plan_id": updates.get("floor_plan_id", door.floor_plan_id),
            "x": updates.get("x", door.x),
            "y": updates.get("y", door.y),
            "width": updates.get("width", door.width),
            "height": updates.get("height", door.height),
            "wall_id": updates.get("wall_id", door.wall_id),
            "rotation_deg": updates.get("rotation_deg", door.rotation_deg),
        })
        updates.update(merged)
        self._apply_update(door, updates)
        self.db.commit()
        self.db.refresh(door)
        return door

    def delete_door(self, door_id: int) -> None:
        self._delete(DoorModel, door_id, "door_not_found", "Door not found")

    def list_windows(self, floor_plan_id: int) -> list[WindowModel]:
        return self.db.query(WindowModel).filter(WindowModel.floor_plan_id == floor_plan_id).all()

    def create_window(self, payload: WindowCreate) -> WindowModel:
        data = self._normalize_opening_payload(payload.model_dump())
        window = WindowModel(**data)
        self.db.add(window)
        self.db.commit()
        self.db.refresh(window)
        return window

    def update_window(self, window_id: int, payload: WindowUpdate) -> WindowModel:
        window = self._get_or_404(WindowModel, window_id, "window_not_found", "Window not found")
        updates = payload.model_dump(exclude_unset=True)
        merged = self._normalize_opening_payload({
            "floor_plan_id": updates.get("floor_plan_id", window.floor_plan_id),
            "x": updates.get("x", window.x),
            "y": updates.get("y", window.y),
            "width": updates.get("width", window.width),
            "height": updates.get("height", window.height),
            "wall_id": updates.get("wall_id", window.wall_id),
            "rotation_deg": updates.get("rotation_deg", window.rotation_deg),
        })
        updates.update(merged)
        self._apply_update(window, updates)
        self.db.commit()
        self.db.refresh(window)
        return window

    def delete_window(self, window_id: int) -> None:
        self._delete(WindowModel, window_id, "window_not_found", "Window not found")

    def list_stairs(self, floor_plan_id: int) -> list[StairModel]:
        return self.db.query(StairModel).filter(StairModel.floor_plan_id == floor_plan_id).all()

    def create_stair(self, payload: StairCreate) -> StairModel:
        data = self._normalize_stair_payload(payload.model_dump())
        stair = StairModel(**data)
        self.db.add(stair)
        self.db.commit()
        self.db.refresh(stair)
        return stair

    def update_stair(self, stair_id: int, payload: StairUpdate) -> StairModel:
        stair = self._get_or_404(StairModel, stair_id, "stair_not_found", "Stair not found")
        updates = self._normalize_stair_payload({
            "floor_plan_id": payload.floor_plan_id if payload.floor_plan_id is not None else stair.floor_plan_id,
            "x": payload.x if payload.x is not None else stair.x,
            "y": payload.y if payload.y is not None else stair.y,
            "width": payload.width if payload.width is not None else stair.width,
            "height": payload.height if payload.height is not None else stair.height,
            "rotation_deg": payload.rotation_deg if payload.rotation_deg is not None else stair.rotation_deg,
            "step_count": payload.step_count if payload.step_count is not None else stair.step_count,
            "step_axis": payload.step_axis,
        })
        self._apply_update(stair, updates)
        self.db.commit()
        self.db.refresh(stair)
        return stair

    def delete_stair(self, stair_id: int) -> None:
        self._delete(StairModel, stair_id, "stair_not_found", "Stair not found")

    def list_rooms(self, floor_plan_id: int) -> list[RoomModel]:
        return self.db.query(RoomModel).filter(RoomModel.floor_plan_id == floor_plan_id).all()

    def create_room(self, payload: RoomCreate) -> RoomModel:
        floor_plan = self._get_or_404(
            FloorPlanModel,
            payload.floor_plan_id,
            "floor_plan_not_found",
            "Floor plan not found",
        )
        room = RoomModel(**payload.model_dump())
        self._refresh_room_geometry(room, floor_plan.scale_factor)
        self.db.add(room)
        self.db.flush()
        self._refresh_fire_alarm_metadata_for_floor_plan(payload.floor_plan_id)
        self.db.commit()
        self.db.refresh(room)
        return room

    def update_room(self, room_id: int, payload: RoomUpdate) -> RoomModel:
        room = self._get_or_404(RoomModel, room_id, "room_not_found", "Room not found")
        floor_plan = self._get_or_404(
            FloorPlanModel,
            room.floor_plan_id,
            "floor_plan_not_found",
            "Floor plan not found",
        )
        self._apply_update(room, payload.model_dump(exclude_unset=True))
        self._refresh_room_geometry(room, floor_plan.scale_factor)
        self._refresh_fire_alarm_metadata_for_floor_plan(room.floor_plan_id)
        self.db.commit()
        self.db.refresh(room)
        return room

    def delete_room(self, room_id: int) -> None:
        room = self._get_or_404(RoomModel, room_id, "room_not_found", "Room not found")
        floor_plan_id = room.floor_plan_id
        self.db.delete(room)
        self.db.flush()
        self._refresh_fire_alarm_metadata_for_floor_plan(floor_plan_id)
        self.db.commit()

    def list_dimensions(self, floor_plan_id: int) -> list[DimensionModel]:
        return self.db.query(DimensionModel).filter(DimensionModel.floor_plan_id == floor_plan_id).all()

    def create_dimension(self, payload: DimensionCreate) -> DimensionModel:
        dimension = DimensionModel(**payload.model_dump())
        self.db.add(dimension)
        self.db.commit()
        self.db.refresh(dimension)
        return dimension

    def delete_dimension(self, dimension_id: int) -> None:
        self._delete(DimensionModel, dimension_id, "dimension_not_found", "Dimension not found")

    def list_fire_alarms(self, floor_plan_id: int) -> list[FireAlarmModel]:
        return self.db.query(FireAlarmModel).filter(FireAlarmModel.floor_plan_id == floor_plan_id).all()

    def create_fire_alarm(self, payload: FireAlarmCreate) -> FireAlarmModel:
        data = payload.model_dump()
        floor_plan_id = int(data["floor_plan_id"])
        normalized = self._normalize_fire_alarm_payload(floor_plan_id, data)
        fire_alarm = FireAlarmModel(**normalized)
        self.db.add(fire_alarm)
        self.db.commit()
        self.db.refresh(fire_alarm)
        return fire_alarm

    def update_fire_alarm(self, fire_alarm_id: int, payload: FireAlarmUpdate) -> FireAlarmModel:
        fire_alarm = self._get_or_404(
            FireAlarmModel,
            fire_alarm_id,
            "fire_alarm_not_found",
            "Fire alarm not found",
        )
        updates = payload.model_dump(exclude_unset=True)
        floor_plan_id = int(updates.get("floor_plan_id", fire_alarm.floor_plan_id))
        merged = {
            "floor_plan_id": floor_plan_id,
            "x": updates.get("x", fire_alarm.x),
            "y": updates.get("y", fire_alarm.y),
            "device_type": updates.get("device_type", fire_alarm.device_type),
            "device_model": updates.get("device_model", fire_alarm.device_model),
            "coverage_radius": updates.get("coverage_radius", fire_alarm.coverage_radius),
            "mounting_height": updates.get("mounting_height", fire_alarm.mounting_height),
            "system_type": updates.get("system_type", fire_alarm.system_type),
            "zkspc_zone_id": updates.get("zkspc_zone_id", fire_alarm.zkspc_zone_id),
            "loop_kind": updates.get("loop_kind", fire_alarm.loop_kind),
            "loop_number": updates.get("loop_number", fire_alarm.loop_number),
            "device_number": updates.get("device_number", fire_alarm.device_number),
            "zone": updates.get("zone", fire_alarm.zone),
            "address": updates.get("address", fire_alarm.address),
        }
        self._apply_update(fire_alarm, self._normalize_fire_alarm_payload(floor_plan_id, merged))
        self.db.commit()
        self.db.refresh(fire_alarm)
        return fire_alarm

    def delete_fire_alarm(self, fire_alarm_id: int) -> None:
        self._delete(FireAlarmModel, fire_alarm_id, "fire_alarm_not_found", "Fire alarm not found")

    def batch_save(self, floor_plan_id: int, payload: BatchSaveRequest, commit: bool = True) -> FloorPlanModel:
        floor_plan = self._get_or_404(
            FloorPlanModel,
            floor_plan_id,
            "floor_plan_not_found",
            "Floor plan not found",
        )
        walls_changed = False
        touched_fire_alarm_systems: set[str] = set()
        for item in payload.deleted:
            if item.element_type == "walls":
                walls_changed = True
            if item.element_type == "fire-alarms":
                fire_alarm = self.db.query(FireAlarmModel).filter(FireAlarmModel.id == item.id).first()
                if fire_alarm is not None:
                    touched_fire_alarm_systems.add(
                        fire_alarm.system_type if fire_alarm.system_type in {"addressable", "non_addressable"} else "non_addressable"
                    )
            self._delete_by_type(
                item.element_type,
                item.id,
                commit=False,
                missing_ok=item.element_type in {"doors", "windows"},
            )
        for wall_payload in payload.create_walls:
            wall = WallModel(**wall_payload.model_dump())
            wall.floor_plan_id = floor_plan_id
            self.db.add(wall)
            walls_changed = True
        for stair_payload in payload.create_stairs:
            data = self._normalize_stair_payload(stair_payload.model_dump())
            data["floor_plan_id"] = floor_plan_id
            self.db.add(StairModel(**data))
        self.db.flush()
        for door_payload in payload.create_doors:
            data = self._normalize_opening_payload(door_payload.model_dump(), strict=True)
            data["floor_plan_id"] = floor_plan_id
            self.db.add(DoorModel(**data))
        for window_payload in payload.create_windows:
            data = self._normalize_opening_payload(window_payload.model_dump(), strict=True)
            data["floor_plan_id"] = floor_plan_id
            self.db.add(WindowModel(**data))
        for fire_alarm_payload in payload.create_fire_alarms:
            data = self._normalize_fire_alarm_payload(floor_plan_id, fire_alarm_payload.model_dump())
            data["floor_plan_id"] = floor_plan_id
            touched_fire_alarm_systems.add(data["system_type"])
            self.db.add(FireAlarmModel(**data))
        for command in payload.update_walls:
            wall = self._get_or_404(WallModel, command.id, "wall_not_found", "Wall not found")
            self._apply_update(wall, command.data.model_dump(exclude_unset=True))
            walls_changed = True
        for command in payload.update_stairs:
            stair = self._get_or_404(StairModel, command.id, "stair_not_found", "Stair not found")
            updates = self._normalize_stair_payload({
                "floor_plan_id": command.data.floor_plan_id if command.data.floor_plan_id is not None else stair.floor_plan_id,
                "x": command.data.x if command.data.x is not None else stair.x,
                "y": command.data.y if command.data.y is not None else stair.y,
                "width": command.data.width if command.data.width is not None else stair.width,
                "height": command.data.height if command.data.height is not None else stair.height,
                "rotation_deg": command.data.rotation_deg if command.data.rotation_deg is not None else stair.rotation_deg,
                "step_count": command.data.step_count if command.data.step_count is not None else stair.step_count,
                "step_axis": command.data.step_axis,
            })
            self._apply_update(stair, updates)
        for command in payload.update_doors:
            door = self._get_or_stale(DoorModel, command.id, "door")
            updates = self._normalize_opening_payload({
                "floor_plan_id": command.data.floor_plan_id if command.data.floor_plan_id is not None else door.floor_plan_id,
                "x": command.data.x if command.data.x is not None else door.x,
                "y": command.data.y if command.data.y is not None else door.y,
                "width": command.data.width if command.data.width is not None else door.width,
                "height": command.data.height if command.data.height is not None else door.height,
                "wall_id": command.data.wall_id if command.data.wall_id is not None else door.wall_id,
                "rotation_deg": command.data.rotation_deg if command.data.rotation_deg is not None else door.rotation_deg,
            }, strict=True)
            self._apply_update(door, updates)
        for command in payload.update_windows:
            window = self._get_or_stale(WindowModel, command.id, "window")
            updates = self._normalize_opening_payload({
                "floor_plan_id": command.data.floor_plan_id if command.data.floor_plan_id is not None else window.floor_plan_id,
                "x": command.data.x if command.data.x is not None else window.x,
                "y": command.data.y if command.data.y is not None else window.y,
                "width": command.data.width if command.data.width is not None else window.width,
                "height": command.data.height if command.data.height is not None else window.height,
                "wall_id": command.data.wall_id if command.data.wall_id is not None else window.wall_id,
                "rotation_deg": command.data.rotation_deg if command.data.rotation_deg is not None else window.rotation_deg,
            }, strict=True)
            self._apply_update(window, updates)
        for command in payload.update_rooms:
            room = self._get_or_404(RoomModel, command.id, "room_not_found", "Room not found")
            floor_plan_for_room = self._get_or_404(
                FloorPlanModel,
                room.floor_plan_id,
                "floor_plan_not_found",
                "Floor plan not found",
            )
            self._apply_update(room, command.data.model_dump(exclude_unset=True))
            self._refresh_room_geometry(room, floor_plan_for_room.scale_factor)
        for command in payload.update_fire_alarms:
            fire_alarm = self._get_or_404(
                FireAlarmModel,
                command.id,
                "fire_alarm_not_found",
                "Fire alarm not found",
            )
            updates = command.data.model_dump(exclude_unset=True)
            floor_plan_id_for_alarm = int(updates.get("floor_plan_id", fire_alarm.floor_plan_id))
            merged = {
                "floor_plan_id": floor_plan_id_for_alarm,
                "x": updates.get("x", fire_alarm.x),
                "y": updates.get("y", fire_alarm.y),
                "device_type": updates.get("device_type", fire_alarm.device_type),
                "device_model": updates.get("device_model", fire_alarm.device_model),
                "coverage_radius": updates.get("coverage_radius", fire_alarm.coverage_radius),
                "mounting_height": updates.get("mounting_height", fire_alarm.mounting_height),
                "system_type": updates.get("system_type", fire_alarm.system_type),
                "zkspc_zone_id": updates.get("zkspc_zone_id", fire_alarm.zkspc_zone_id),
                "loop_kind": updates.get("loop_kind", fire_alarm.loop_kind),
                "loop_number": updates.get("loop_number", fire_alarm.loop_number),
                "device_number": updates.get("device_number", fire_alarm.device_number),
                "zone": updates.get("zone", fire_alarm.zone),
                "address": updates.get("address", fire_alarm.address),
            }
            normalized_alarm = self._normalize_fire_alarm_payload(floor_plan_id_for_alarm, merged)
            touched_fire_alarm_systems.add(normalized_alarm["system_type"])
            self._apply_update(fire_alarm, normalized_alarm)
        if walls_changed:
            self.relink_or_prune_openings(floor_plan_id, delete_invalid=True)
        self._refresh_fire_alarm_metadata_for_floor_plan(floor_plan_id)
        for system_type in touched_fire_alarm_systems:
            update_signal_branch_state(
                floor_plan,
                system_type,
                fire_alarms_status="validated",
                devices_cables_status="draft",
                active_step="devices_cables",
            )
        if commit:
            self.db.commit()
            self.db.refresh(floor_plan)
        else:
            self.db.flush()
        return floor_plan

    def replace_fire_alarms(
        self,
        floor_plan_id: int,
        fire_alarm_payloads: list[dict[str, Any]],
        system_type: str | None = None,
    ) -> None:
        normalized_system = system_type if system_type in {"addressable", "non_addressable"} else None
        delete_query = self.db.query(FireAlarmModel).filter(FireAlarmModel.floor_plan_id == floor_plan_id)
        if normalized_system is not None:
            delete_query = delete_query.filter(FireAlarmModel.system_type == normalized_system)
        delete_query.delete()
        for payload in fire_alarm_payloads:
            normalized = self._normalize_fire_alarm_payload(
                floor_plan_id,
                {
                    "floor_plan_id": floor_plan_id,
                    "system_type": normalized_system or payload.get("system_type") or "non_addressable",
                    **payload,
                },
            )
            self.db.add(FireAlarmModel(**normalized))
        self.db.commit()

    def _delete(self, model, entity_id: int, code: str, detail: str) -> None:
        entity = self._get_or_404(model, entity_id, code, detail)
        self.db.delete(entity)
        self.db.commit()

    def _delete_by_type(
        self,
        element_type: str,
        entity_id: int,
        commit: bool = True,
        missing_ok: bool = False,
    ) -> None:
        model_map = {
            "walls": (WallModel, "wall_not_found", "Wall not found"),
            "stairs": (StairModel, "stair_not_found", "Stair not found"),
            "doors": (DoorModel, "door_not_found", "Door not found"),
            "windows": (WindowModel, "window_not_found", "Window not found"),
            "fire-alarms": (FireAlarmModel, "fire_alarm_not_found", "Fire alarm not found"),
            "rooms": (RoomModel, "room_not_found", "Room not found"),
            "dimensions": (DimensionModel, "dimension_not_found", "Dimension not found"),
        }
        model, code, detail = model_map[element_type]
        entity = self.db.query(model).filter(model.id == entity_id).first()
        if entity is None:
            if missing_ok:
                return
            raise AppError(404, code, detail)
        self.db.delete(entity)
        if commit:
            self.db.commit()

    def _get_or_404(self, model, entity_id: int, code: str, detail: str):
        entity = self.db.query(model).filter(model.id == entity_id).first()
        if entity is None:
            raise AppError(404, code, detail)
        return entity

    def _get_or_stale(self, model, entity_id: int, entity_name: str):
        entity = self.db.query(model).filter(model.id == entity_id).first()
        if entity is None:
            raise AppError(
                409,
                "stale_editor_state",
                f"{entity_name.capitalize()} is out of date. Reload the floor plan and try again.",
            )
        return entity

    @staticmethod
    def _apply_update(entity, data: dict[str, Any]) -> None:
        for field, value in data.items():
            setattr(entity, field, value)

    @staticmethod
    def _refresh_room_geometry(room: RoomModel, scale_factor: float) -> None:
        if room.boundary_points:
            room.calculate_center()
            if room.length_m is None or room.width_m is None:
                room.calculate_length_width(scale_factor)

        if room.length_m is not None and room.width_m is not None:
            room.area_sqm = room.length_m * room.width_m
            room.perimeter_m = 2.0 * (room.length_m + room.width_m)
        elif room.boundary_points:
            room.calculate_area(scale_factor)
            room.calculate_perimeter(scale_factor)

    @staticmethod
    def _normalize_stair_payload(data: dict[str, Any]) -> dict[str, Any]:
        width = max(4.0, float(data["width"]))
        height = max(4.0, float(data["height"]))
        step_axis = data.get("step_axis")
        if step_axis not in {"horizontal", "vertical"}:
            step_axis = "horizontal" if width >= height else "vertical"
        return {
            **data,
            "width": width,
            "height": height,
            "step_count": max(2, int(data.get("step_count", 5))),
            "step_axis": step_axis,
        }

    def relink_or_prune_openings(self, floor_plan_id: int, delete_invalid: bool = True) -> None:
        for door in self.list_doors(floor_plan_id):
            normalized = self._normalize_opening_payload({
                "floor_plan_id": door.floor_plan_id,
                "x": door.x,
                "y": door.y,
                "width": door.width,
                "height": door.height,
                "wall_id": door.wall_id,
                "rotation_deg": door.rotation_deg,
            }, strict=False)
            if normalized is None:
                if delete_invalid:
                    self.db.delete(door)
                continue
            self._apply_update(door, normalized)
        for window in self.list_windows(floor_plan_id):
            normalized = self._normalize_opening_payload({
                "floor_plan_id": window.floor_plan_id,
                "x": window.x,
                "y": window.y,
                "width": window.width,
                "height": window.height,
                "wall_id": window.wall_id,
                "rotation_deg": window.rotation_deg,
            }, strict=False)
            if normalized is None:
                if delete_invalid:
                    self.db.delete(window)
                continue
            self._apply_update(window, normalized)

    def _normalize_floor_plan_openings(self, floor_plan_id: int) -> None:
        for door in self.list_doors(floor_plan_id):
            normalized = self._normalize_opening_payload({
                "floor_plan_id": door.floor_plan_id,
                "x": door.x,
                "y": door.y,
                "width": door.width,
                "height": door.height,
                "wall_id": door.wall_id,
                "rotation_deg": door.rotation_deg,
            }, strict=True)
            self._apply_update(door, normalized)
        for window in self.list_windows(floor_plan_id):
            normalized = self._normalize_opening_payload({
                "floor_plan_id": window.floor_plan_id,
                "x": window.x,
                "y": window.y,
                "width": window.width,
                "height": window.height,
                "wall_id": window.wall_id,
                "rotation_deg": window.rotation_deg,
            }, strict=True)
            self._apply_update(window, normalized)

    def _normalize_opening_payload(self, data: dict[str, Any], *, strict: bool = True) -> dict[str, Any] | None:
        wall = self._resolve_opening_wall(
            floor_plan_id=int(data["floor_plan_id"]),
            x=float(data["x"]),
            y=float(data["y"]),
            width=float(data["width"]),
            height=float(data.get("height", data["width"])),
            wall_id=data.get("wall_id"),
            strict=strict,
        )
        if wall is None:
            return None
        floor_plan = self._get_or_404(
            FloorPlanModel,
            int(data["floor_plan_id"]),
            "floor_plan_not_found",
            "Floor plan not found",
        )
        scale_factor = floor_plan.scale_factor or 1.0
        dx = wall.x2 - wall.x1
        dy = wall.y2 - wall.y1
        wall_length = math.hypot(dx, dy)
        if wall_length < 1e-6:
            raise AppError(422, "opening_outside_wall", "Opening must be located on a wall")

        axis_x = dx / wall_length
        axis_y = dy / wall_length
        rotation_deg = math.degrees(math.atan2(dy, dx))
        thickness_px = max(1.0, float(wall.thickness or 1.0) / scale_factor)

        width = max(4.0, min(float(data["width"]), wall_length))
        center_x = float(data["x"]) + float(data["width"]) / 2.0
        center_y = float(data["y"]) + float(data.get("height", thickness_px)) / 2.0
        projected = ((center_x - wall.x1) * dx + (center_y - wall.y1) * dy) / wall_length
        half_width = width / 2.0
        along = min(max(projected, half_width), max(half_width, wall_length - half_width))
        normalized_center_x = wall.x1 + axis_x * along
        normalized_center_y = wall.y1 + axis_y * along

        return {
            **data,
            "x": normalized_center_x - width / 2.0,
            "y": normalized_center_y - thickness_px / 2.0,
            "width": width,
            "height": thickness_px,
            "rotation_deg": rotation_deg,
            "wall_id": wall.id,
        }

    def _resolve_opening_wall(
        self,
        floor_plan_id: int,
        x: float,
        y: float,
        width: float,
        height: float,
        wall_id: int | None = None,
        strict: bool = True,
    ) -> WallModel | None:
        walls = self.db.query(WallModel).filter(WallModel.floor_plan_id == floor_plan_id).all()
        if not walls:
            if strict:
                raise AppError(422, "wall_not_found_for_opening", "No walls available for opening placement")
            return None

        floor_plan = self._get_or_404(
            FloorPlanModel,
            floor_plan_id,
            "floor_plan_not_found",
            "Floor plan not found",
        )
        scale_factor = floor_plan.scale_factor or 1.0

        center_x = float(x) + float(width) / 2.0
        center_y = float(y) + float(height) / 2.0
        projection_margin = max(float(width), float(height), 1.0)

        def distance_to_wall(wall: WallModel) -> tuple[float, bool]:
            dx = wall.x2 - wall.x1
            dy = wall.y2 - wall.y1
            length = math.hypot(dx, dy)
            if length < 1e-6:
                return float("inf"), False

            t = ((center_x - wall.x1) * dx + (center_y - wall.y1) * dy) / (length * length)
            along = t * length
            signed = ((center_x - wall.x1) * dy - (center_y - wall.y1) * dx) / length
            distance = abs(signed)

            thickness_px = max(1.0, (wall.thickness or 1.0) / scale_factor)
            max_distance = max(thickness_px * 1.5, min(float(width), float(height), 40.0))
            within_projection = -projection_margin <= along <= (length + projection_margin)
            within_thickness = distance <= max_distance
            return distance, within_projection and within_thickness

        if wall_id is not None:
            wall = self.db.query(WallModel).filter(WallModel.id == wall_id).first()
            if wall is not None:
                if wall.floor_plan_id != floor_plan_id:
                    if strict:
                        raise AppError(422, "opening_wall_mismatch", "Opening wall must belong to the same floor plan")
                else:
                    _distance, fits = distance_to_wall(wall)
                    if fits:
                        return wall

        best_wall = None
        best_distance = float("inf")
        for wall in walls:
            distance, fits = distance_to_wall(wall)
            if not fits:
                continue
            if distance < best_distance:
                best_distance = distance
                best_wall = wall

        if best_wall is None:
            if strict:
                raise AppError(422, "opening_outside_wall", "Opening must be located on a wall")
            return None
        return best_wall

    def _normalize_fire_alarm_payload(self, floor_plan_id: int, data: dict[str, Any]) -> dict[str, Any]:
        floor_plan = self._get_or_404(
            FloorPlanModel,
            floor_plan_id,
            "floor_plan_not_found",
            "Floor plan not found",
        )
        rooms = [
            room.to_dict()
            for room in self.db.query(RoomModel).filter(RoomModel.floor_plan_id == floor_plan_id).all()
        ]
        x = float(data["x"])
        y = float(data["y"])
        metadata = locate_fire_alarm_metadata(x, y, rooms, floor_plan.scale_factor or 1.0)
        zkspc_zone_id = data.get("zkspc_zone_id")
        zone_number = data.get("zone")
        if metadata.get("room_id") is not None:
            room_zone = self._find_zkspc_zone_for_room(floor_plan_id, int(metadata["room_id"]))
            if room_zone is not None:
                zkspc_zone_id = room_zone.id
                zone_number = str(room_zone.zone_number)
        normalized = {
            **data,
            "floor_plan_id": floor_plan_id,
            "x": x,
            "y": y,
            "coverage_radius": float(data["coverage_radius"]) if data.get("coverage_radius") is not None else None,
            "mounting_height": float(data["mounting_height"]) if data.get("mounting_height") is not None else None,
            "system_type": data.get("system_type") if data.get("system_type") in {"addressable", "non_addressable"} else "non_addressable",
            "zkspc_zone_id": int(zkspc_zone_id) if zkspc_zone_id is not None else None,
            "loop_kind": data.get("loop_kind"),
            "loop_number": int(data["loop_number"]) if data.get("loop_number") is not None else None,
            "device_number": int(data["device_number"]) if data.get("device_number") is not None else None,
            "zone": zone_number,
            **metadata,
        }
        return normalized

    def _refresh_fire_alarm_metadata_for_floor_plan(self, floor_plan_id: int) -> None:
        floor_plan = self._get_or_404(
            FloorPlanModel,
            floor_plan_id,
            "floor_plan_not_found",
            "Floor plan not found",
        )
        rooms = [
            room.to_dict()
            for room in self.db.query(RoomModel).filter(RoomModel.floor_plan_id == floor_plan_id).all()
        ]
        scale_factor = floor_plan.scale_factor or 1.0
        for fire_alarm in self.list_fire_alarms(floor_plan_id):
            metadata = locate_fire_alarm_metadata(fire_alarm.x, fire_alarm.y, rooms, scale_factor)
            fire_alarm.room_id = metadata["room_id"]
            fire_alarm.offset_left_m = metadata["offset_left_m"]
            fire_alarm.offset_top_m = metadata["offset_top_m"]
            if fire_alarm.room_id is not None:
                zone = self._find_zkspc_zone_for_room(floor_plan_id, int(fire_alarm.room_id))
                fire_alarm.zkspc_zone_id = zone.id if zone is not None else None
                fire_alarm.zone = str(zone.zone_number) if zone is not None else fire_alarm.zone

    def _find_zkspc_zone_for_room(self, floor_plan_id: int, room_id: int) -> ZkspcZoneModel | None:
        for zone in (
            self.db.query(ZkspcZoneModel)
            .filter(ZkspcZoneModel.floor_plan_id == floor_plan_id)
            .order_by(ZkspcZoneModel.zone_number.asc())
            .all()
        ):
            if any(link.room_id == room_id for link in zone.room_links):
                return zone
        return None
