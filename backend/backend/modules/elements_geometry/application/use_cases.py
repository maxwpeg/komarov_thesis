"""Explicit application use cases for element geometry."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from backend.errors import AppError
from backend.modules.equipment.domain.bindings import resolve_project_equipment_id
from backend.modules.equipment.domain.constants import FIRE_ALARM_DEVICE_CATEGORY_MAP, SOUE_DEVICE_CATEGORY_MAP
from backend.modules.elements_geometry.domain.policies import (
    FireAlarmMetadataPolicy,
    OpeningNormalizationPolicy,
    RoomGeometryPolicy,
    SoueDeviceMetadataPolicy,
    StairGeometryPolicy,
)
from backend.modules.elements_geometry.domain.records import (
    DimensionRecord,
    DoorRecord,
    FireAlarmRecord,
    RoomRecord,
    SoueDeviceRecord,
    StairRecord,
    WallRecord,
    WindowRecord,
)
from backend.modules.elements_geometry.ports.repositories import ElementsRepository
from backend.modules.floor_plans.domain.entities import FloorPlanRecord
from backend.modules.pipeline.application.branch_state import update_signal_branch_state
from backend.modules.shared.application.unit_of_work import UnitOfWork
from backend.modules.shared.infrastructure.runtime import NoOpEventPublisher


def _model_to_payload(model: Any) -> dict[str, Any]:
    if isinstance(model, dict):
        return dict(model)
    if hasattr(model, "to_dict"):
        return model.to_dict()
    return {
        "id": getattr(model, "id", None),
        "name": getattr(model, "name", None),
        "room_type": getattr(model, "room_type", None),
        "room_number": getattr(model, "room_number", None),
        "max_occupancy": getattr(model, "max_occupancy", None),
        "boundary_points": getattr(model, "boundary_points", None),
    }


def _point_on_segment(point: tuple[float, float], start: tuple[float, float], end: tuple[float, float]) -> bool:
    px, py = point
    x1, y1 = start
    x2, y2 = end
    cross = (px - x1) * (y2 - y1) - (py - y1) * (x2 - x1)
    if abs(cross) > 1e-6:
        return False
    dot = (px - x1) * (px - x2) + (py - y1) * (py - y2)
    return dot <= 1e-6


def _point_in_polygon(point: tuple[float, float], polygon: list[list[float]] | None) -> bool:
    if not polygon or len(polygon) < 3:
        return False
    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = float(previous[0]), float(previous[1])
        x2, y2 = float(current[0]), float(current[1])
        if _point_on_segment(point, (x1, y1), (x2, y2)):
            return True
        intersects = ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9) + x1)
        if intersects:
            inside = not inside
        previous = current
    return inside


def _room_text(room: dict[str, Any] | None) -> str:
    if room is None:
        return ""
    return " ".join(
        [
            str(room.get("name") or ""),
            str(room.get("room_type") or ""),
            str(room.get("room_number") or ""),
        ]
    ).lower()


def _is_path_like_room(room: dict[str, Any] | None) -> bool:
    text = _room_text(room)
    keywords = ("лест", "corridor", "коридор", "холл", "hall", "фойе", "тамбур", "вестиб", "эвак", "выход", "безопас")
    return any(keyword in text for keyword in keywords)


def _is_large_public_room(room: dict[str, Any] | None) -> bool:
    if room is None:
        return False
    occupancy = room.get("max_occupancy")
    if occupancy is not None and int(occupancy) >= 50:
        return True
    text = _room_text(room)
    keywords = ("зал", "демонстр", "выстав", "auditor", "showroom")
    return any(keyword in text for keyword in keywords)


def _door_adjacent_room_ids(door: dict[str, Any], rooms: list[dict[str, Any]]) -> list[int]:
    center = (
        float(door.get("x") or 0.0) + (float(door.get("width") or 0.0) / 2.0),
        float(door.get("y") or 0.0) + (float(door.get("height") or 0.0) / 2.0),
    )
    rotation_rad = math.radians(float(door.get("rotation_deg") or 0.0))
    normal = (-math.sin(rotation_rad), math.cos(rotation_rad))
    sample_offset = max(10.0, float(door.get("height") or 0.0) * 1.5)
    candidates = [
        (center[0] + normal[0] * sample_offset, center[1] + normal[1] * sample_offset),
        (center[0] - normal[0] * sample_offset, center[1] - normal[1] * sample_offset),
        center,
    ]

    room_ids: list[int] = []
    for point in candidates:
        for room in rooms:
            polygon = room.get("boundary_points") or []
            room_id = room.get("id")
            if room_id is None or not polygon or not _point_in_polygon(point, polygon):
                continue
            safe_room_id = int(room_id)
            if safe_room_id not in room_ids:
                room_ids.append(safe_room_id)
    return room_ids


def _infer_door_evacuation_exit(door: dict[str, Any], rooms: list[dict[str, Any]]) -> bool:
    rooms_by_id = {
        int(room["id"]): room
        for room in rooms
        if room.get("id") is not None
    }
    adjacent_rooms = [rooms_by_id[room_id] for room_id in _door_adjacent_room_ids(door, rooms) if room_id in rooms_by_id]
    if len(adjacent_rooms) <= 1:
        return True
    if any(_is_path_like_room(room) for room in adjacent_rooms):
        return True
    if any(_is_large_public_room(room) for room in adjacent_rooms):
        return True
    return False


@dataclass(slots=True)
class WallUseCases:
    repository: ElementsRepository
    uow: UnitOfWork
    events: Any

    def list_walls(self, floor_plan_id: int) -> list[WallRecord]:
        return [WallRecord.from_model(wall) for wall in self.repository.list_walls(floor_plan_id)]

    def create_wall(self, payload) -> WallRecord:
        wall = self.repository.create_wall(payload.model_dump())
        self.repository.add(wall)
        self.uow.commit()
        self.repository.refresh(wall)
        self.events.publish(
            "wall_created",
            {"category": "elements", "use_case": "CreateWall", "floor_plan_id": wall.floor_plan_id, "payload": {"wall_id": wall.id}},
        )
        return WallRecord.from_model(wall)

    def update_wall(self, wall_id: int, payload) -> WallRecord:
        wall = self.repository.get_wall(wall_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(wall, field, value)
        self._relink_or_prune_openings(wall.floor_plan_id, delete_invalid=True)
        self.uow.commit()
        self.repository.refresh(wall)
        self.events.publish(
            "wall_updated",
            {"category": "elements", "use_case": "UpdateWall", "floor_plan_id": wall.floor_plan_id, "payload": {"wall_id": wall.id}},
        )
        return WallRecord.from_model(wall)

    def delete_wall(self, wall_id: int) -> None:
        wall = self.repository.get_wall(wall_id)
        floor_plan_id = wall.floor_plan_id
        self.repository.delete(wall)
        self.repository.flush()
        self._relink_or_prune_openings(floor_plan_id, delete_invalid=True)
        self.uow.commit()
        self.events.publish(
            "wall_deleted",
            {"category": "elements", "use_case": "DeleteWall", "floor_plan_id": floor_plan_id, "payload": {"wall_id": wall_id}},
        )

    def _relink_or_prune_openings(self, floor_plan_id: int, delete_invalid: bool) -> None:
        openings = OpeningUseCases(self.repository, self.uow, self.events)
        openings.relink_or_prune_openings(floor_plan_id, delete_invalid=delete_invalid)


@dataclass(slots=True)
class OpeningUseCases:
    repository: ElementsRepository
    uow: UnitOfWork
    events: Any

    def list_doors(self, floor_plan_id: int) -> list[DoorRecord]:
        return [DoorRecord.from_model(item) for item in self.repository.list_doors(floor_plan_id)]

    def create_door(self, payload) -> DoorRecord:
        floor_plan = self.repository.get_floor_plan(payload.floor_plan_id)
        normalized = OpeningNormalizationPolicy.normalize(
            payload.model_dump(),
            floor_plan_scale_factor=floor_plan.scale_factor or 1.0,
            walls=self.repository.list_walls(payload.floor_plan_id),
            strict=True,
        )
        if payload.is_evacuation_exit is None:
            normalized["is_evacuation_exit"] = _infer_door_evacuation_exit(
                normalized,
                [_model_to_payload(room) for room in self.repository.list_rooms(payload.floor_plan_id)],
            )
        door = self.repository.create_door(normalized)
        self.repository.add(door)
        self.uow.commit()
        self.repository.refresh(door)
        return DoorRecord.from_model(door)

    def update_door(self, door_id: int, payload) -> DoorRecord:
        door = self.repository.get_door(door_id)
        floor_plan_id = payload.floor_plan_id if payload.floor_plan_id is not None else door.floor_plan_id
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        merged = OpeningNormalizationPolicy.normalize(
            {
                "floor_plan_id": floor_plan_id,
                "x": payload.x if payload.x is not None else door.x,
                "y": payload.y if payload.y is not None else door.y,
                "width": payload.width if payload.width is not None else door.width,
                "height": payload.height if payload.height is not None else door.height,
                "wall_id": payload.wall_id if payload.wall_id is not None else door.wall_id,
                "rotation_deg": payload.rotation_deg if payload.rotation_deg is not None else door.rotation_deg,
                "door_type": payload.door_type if payload.door_type is not None else door.door_type,
                "swing_angle": payload.swing_angle if payload.swing_angle is not None else door.swing_angle,
                "swing_direction": payload.swing_direction if payload.swing_direction is not None else door.swing_direction,
                "is_evacuation_exit": (
                    payload.is_evacuation_exit
                    if payload.is_evacuation_exit is not None
                    else door.is_evacuation_exit
                ),
            },
            floor_plan_scale_factor=floor_plan.scale_factor or 1.0,
            walls=self.repository.list_walls(floor_plan_id),
            strict=True,
        )
        for field, value in merged.items():
            setattr(door, field, value)
        self.uow.commit()
        self.repository.refresh(door)
        return DoorRecord.from_model(door)

    def delete_door(self, door_id: int) -> None:
        self.repository.delete(self.repository.get_door(door_id))
        self.uow.commit()

    def list_windows(self, floor_plan_id: int) -> list[WindowRecord]:
        return [WindowRecord.from_model(item) for item in self.repository.list_windows(floor_plan_id)]

    def create_window(self, payload) -> WindowRecord:
        floor_plan = self.repository.get_floor_plan(payload.floor_plan_id)
        normalized = OpeningNormalizationPolicy.normalize(
            payload.model_dump(),
            floor_plan_scale_factor=floor_plan.scale_factor or 1.0,
            walls=self.repository.list_walls(payload.floor_plan_id),
            strict=True,
        )
        window = self.repository.create_window(normalized)
        self.repository.add(window)
        self.uow.commit()
        self.repository.refresh(window)
        return WindowRecord.from_model(window)

    def update_window(self, window_id: int, payload) -> WindowRecord:
        window = self.repository.get_window(window_id)
        floor_plan_id = payload.floor_plan_id if payload.floor_plan_id is not None else window.floor_plan_id
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        merged = OpeningNormalizationPolicy.normalize(
            {
                "floor_plan_id": floor_plan_id,
                "x": payload.x if payload.x is not None else window.x,
                "y": payload.y if payload.y is not None else window.y,
                "width": payload.width if payload.width is not None else window.width,
                "height": payload.height if payload.height is not None else window.height,
                "wall_id": payload.wall_id if payload.wall_id is not None else window.wall_id,
                "rotation_deg": payload.rotation_deg if payload.rotation_deg is not None else window.rotation_deg,
                "window_type": payload.window_type if payload.window_type is not None else window.window_type,
            },
            floor_plan_scale_factor=floor_plan.scale_factor or 1.0,
            walls=self.repository.list_walls(floor_plan_id),
            strict=True,
        )
        for field, value in merged.items():
            setattr(window, field, value)
        self.uow.commit()
        self.repository.refresh(window)
        return WindowRecord.from_model(window)

    def delete_window(self, window_id: int) -> None:
        self.repository.delete(self.repository.get_window(window_id))
        self.uow.commit()

    def relink_or_prune_openings(self, floor_plan_id: int, delete_invalid: bool = True) -> None:
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        walls = self.repository.list_walls(floor_plan_id)
        for door in self.repository.list_doors(floor_plan_id):
            normalized = OpeningNormalizationPolicy.normalize(
                {
                    "floor_plan_id": door.floor_plan_id,
                    "x": door.x,
                    "y": door.y,
                    "width": door.width,
                    "height": door.height,
                    "wall_id": door.wall_id,
                    "rotation_deg": door.rotation_deg,
                    "door_type": door.door_type,
                    "swing_angle": door.swing_angle,
                    "swing_direction": door.swing_direction,
                    "is_evacuation_exit": door.is_evacuation_exit,
                },
                floor_plan_scale_factor=floor_plan.scale_factor or 1.0,
                walls=walls,
                strict=False,
            )
            if normalized is None:
                if delete_invalid:
                    self.repository.delete(door)
                continue
            for field, value in normalized.items():
                setattr(door, field, value)
        for window in self.repository.list_windows(floor_plan_id):
            normalized = OpeningNormalizationPolicy.normalize(
                {
                    "floor_plan_id": window.floor_plan_id,
                    "x": window.x,
                    "y": window.y,
                    "width": window.width,
                    "height": window.height,
                    "wall_id": window.wall_id,
                    "rotation_deg": window.rotation_deg,
                    "window_type": window.window_type,
                },
                floor_plan_scale_factor=floor_plan.scale_factor or 1.0,
                walls=walls,
                strict=False,
            )
            if normalized is None:
                if delete_invalid:
                    self.repository.delete(window)
                continue
            for field, value in normalized.items():
                setattr(window, field, value)

    def normalize_floor_plan_openings(self, floor_plan_id: int) -> None:
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        walls = self.repository.list_walls(floor_plan_id)
        for door in self.repository.list_doors(floor_plan_id):
            normalized = OpeningNormalizationPolicy.normalize(
                {
                    "floor_plan_id": door.floor_plan_id,
                    "x": door.x,
                    "y": door.y,
                    "width": door.width,
                    "height": door.height,
                    "wall_id": door.wall_id,
                    "rotation_deg": door.rotation_deg,
                    "door_type": door.door_type,
                    "swing_angle": door.swing_angle,
                    "swing_direction": door.swing_direction,
                    "is_evacuation_exit": door.is_evacuation_exit,
                },
                floor_plan_scale_factor=floor_plan.scale_factor or 1.0,
                walls=walls,
                strict=True,
            )
            for field, value in normalized.items():
                setattr(door, field, value)
        for window in self.repository.list_windows(floor_plan_id):
            normalized = OpeningNormalizationPolicy.normalize(
                {
                    "floor_plan_id": window.floor_plan_id,
                    "x": window.x,
                    "y": window.y,
                    "width": window.width,
                    "height": window.height,
                    "wall_id": window.wall_id,
                    "rotation_deg": window.rotation_deg,
                    "window_type": window.window_type,
                },
                floor_plan_scale_factor=floor_plan.scale_factor or 1.0,
                walls=walls,
                strict=True,
            )
            for field, value in normalized.items():
                setattr(window, field, value)


@dataclass(slots=True)
class StairUseCases:
    repository: ElementsRepository
    uow: UnitOfWork
    events: Any

    def list_stairs(self, floor_plan_id: int) -> list[StairRecord]:
        return [StairRecord.from_model(item) for item in self.repository.list_stairs(floor_plan_id)]

    def create_stair(self, payload) -> StairRecord:
        stair = self.repository.create_stair(StairGeometryPolicy.normalize(payload.model_dump()))
        self.repository.add(stair)
        self.uow.commit()
        self.repository.refresh(stair)
        return StairRecord.from_model(stair)

    def update_stair(self, stair_id: int, payload) -> StairRecord:
        stair = self.repository.get_stair(stair_id)
        normalized = StairGeometryPolicy.normalize(
            {
                "floor_plan_id": payload.floor_plan_id if payload.floor_plan_id is not None else stair.floor_plan_id,
                "x": payload.x if payload.x is not None else stair.x,
                "y": payload.y if payload.y is not None else stair.y,
                "width": payload.width if payload.width is not None else stair.width,
                "height": payload.height if payload.height is not None else stair.height,
                "rotation_deg": payload.rotation_deg if payload.rotation_deg is not None else stair.rotation_deg,
                "step_count": payload.step_count if payload.step_count is not None else stair.step_count,
                "step_axis": payload.step_axis,
            }
        )
        for field, value in normalized.items():
            setattr(stair, field, value)
        self.uow.commit()
        self.repository.refresh(stair)
        return StairRecord.from_model(stair)

    def delete_stair(self, stair_id: int) -> None:
        self.repository.delete(self.repository.get_stair(stair_id))
        self.uow.commit()


@dataclass(slots=True)
class RoomUseCases:
    repository: ElementsRepository
    uow: UnitOfWork
    events: Any

    def list_rooms(self, floor_plan_id: int) -> list[RoomRecord]:
        return [RoomRecord.from_model(item) for item in self.repository.list_rooms(floor_plan_id)]

    def create_room(self, payload) -> RoomRecord:
        floor_plan = self.repository.get_floor_plan(payload.floor_plan_id)
        room = self.repository.create_room(payload.model_dump())
        RoomGeometryPolicy.refresh(room, floor_plan.scale_factor)
        self.repository.add(room)
        self.repository.flush()
        FireAlarmCrudUseCases(self.repository, self.uow, self.events).refresh_metadata_for_floor_plan(payload.floor_plan_id)
        SoueDeviceCrudUseCases(self.repository, self.uow, self.events).refresh_metadata_for_floor_plan(payload.floor_plan_id)
        self.uow.commit()
        self.repository.refresh(room)
        return RoomRecord.from_model(room)

    def update_room(self, room_id: int, payload) -> RoomRecord:
        room = self.repository.get_room(room_id)
        floor_plan = self.repository.get_floor_plan(room.floor_plan_id)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(room, field, value)
        RoomGeometryPolicy.refresh(room, floor_plan.scale_factor)
        FireAlarmCrudUseCases(self.repository, self.uow, self.events).refresh_metadata_for_floor_plan(room.floor_plan_id)
        SoueDeviceCrudUseCases(self.repository, self.uow, self.events).refresh_metadata_for_floor_plan(room.floor_plan_id)
        self.uow.commit()
        self.repository.refresh(room)
        return RoomRecord.from_model(room)

    def delete_room(self, room_id: int) -> None:
        room = self.repository.get_room(room_id)
        floor_plan_id = room.floor_plan_id
        self.repository.delete(room)
        self.repository.flush()
        FireAlarmCrudUseCases(self.repository, self.uow, self.events).refresh_metadata_for_floor_plan(floor_plan_id)
        SoueDeviceCrudUseCases(self.repository, self.uow, self.events).refresh_metadata_for_floor_plan(floor_plan_id)
        self.uow.commit()


@dataclass(slots=True)
class DimensionUseCases:
    repository: ElementsRepository
    uow: UnitOfWork
    events: Any

    def list_dimensions(self, floor_plan_id: int) -> list[DimensionRecord]:
        return [DimensionRecord.from_model(item) for item in self.repository.list_dimensions(floor_plan_id)]

    def create_dimension(self, payload) -> DimensionRecord:
        dimension = self.repository.create_dimension(payload.model_dump())
        self.repository.add(dimension)
        self.uow.commit()
        self.repository.refresh(dimension)
        return DimensionRecord.from_model(dimension)

    def delete_dimension(self, dimension_id: int) -> None:
        self.repository.delete(self.repository.get_dimension(dimension_id))
        self.uow.commit()


@dataclass(slots=True)
class FireAlarmCrudUseCases:
    repository: ElementsRepository
    uow: UnitOfWork
    events: Any

    def list_fire_alarms(self, floor_plan_id: int) -> list[FireAlarmRecord]:
        return [FireAlarmRecord.from_model(item) for item in self.repository.list_fire_alarms(floor_plan_id)]

    def create_fire_alarm(self, payload) -> FireAlarmRecord:
        normalized = self._normalize_fire_alarm_payload(payload.floor_plan_id, payload.model_dump())
        fire_alarm = self.repository.create_fire_alarm(normalized)
        self.repository.add(fire_alarm)
        self.uow.commit()
        self.repository.refresh(fire_alarm)
        return FireAlarmRecord.from_model(fire_alarm)

    def update_fire_alarm(self, fire_alarm_id: int, payload) -> FireAlarmRecord:
        fire_alarm = self.repository.get_fire_alarm(fire_alarm_id)
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
            "equipment_id": updates.get("equipment_id", fire_alarm.equipment_id),
            "zkspc_zone_id": updates.get("zkspc_zone_id", fire_alarm.zkspc_zone_id),
            "loop_kind": updates.get("loop_kind", fire_alarm.loop_kind),
            "loop_number": updates.get("loop_number", fire_alarm.loop_number),
            "device_number": updates.get("device_number", fire_alarm.device_number),
            "zone": updates.get("zone", fire_alarm.zone),
            "address": updates.get("address", fire_alarm.address),
            "label_dx": updates.get("label_dx", fire_alarm.label_dx),
            "label_dy": updates.get("label_dy", fire_alarm.label_dy),
        }
        normalized = self._normalize_fire_alarm_payload(floor_plan_id, merged)
        for field, value in normalized.items():
            setattr(fire_alarm, field, value)
        self.uow.commit()
        self.repository.refresh(fire_alarm)
        return FireAlarmRecord.from_model(fire_alarm)

    def delete_fire_alarm(self, fire_alarm_id: int) -> None:
        self.repository.delete(self.repository.get_fire_alarm(fire_alarm_id))
        self.uow.commit()

    def replace_fire_alarms(
        self,
        floor_plan_id: int,
        fire_alarm_payloads: list[dict[str, Any]],
        system_type: str | None = None,
    ) -> None:
        normalized_system = system_type if system_type in {"addressable", "non_addressable"} else None
        for alarm in list(self.repository.list_fire_alarms(floor_plan_id)):
            if normalized_system is None or alarm.system_type == normalized_system:
                self.repository.delete(alarm)
        self.repository.flush()
        for payload in fire_alarm_payloads:
            normalized = self._normalize_fire_alarm_payload(
                floor_plan_id,
                {
                    "floor_plan_id": floor_plan_id,
                    "system_type": normalized_system or payload.get("system_type") or "non_addressable",
                    **payload,
                },
            )
            self.repository.add(self.repository.create_fire_alarm(normalized))
        self.uow.commit()
        self.events.publish(
            "branch_fire_alarms_replaced",
            {"category": "signal_design", "use_case": "ReplaceFireAlarms", "floor_plan_id": floor_plan_id, "system_type": normalized_system or "mixed"},
        )

    def refresh_metadata_for_floor_plan(self, floor_plan_id: int) -> None:
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        rooms = [room.to_dict() for room in self.repository.list_rooms(floor_plan_id)]
        scale_factor = floor_plan.scale_factor or 1.0
        for fire_alarm in self.repository.list_fire_alarms(floor_plan_id):
            metadata = FireAlarmMetadataPolicy.normalize(
                floor_plan_id=floor_plan_id,
                data={
                    "x": fire_alarm.x,
                    "y": fire_alarm.y,
                    "coverage_radius": fire_alarm.coverage_radius,
                    "mounting_height": fire_alarm.mounting_height,
                    "system_type": fire_alarm.system_type,
                    "zkspc_zone_id": fire_alarm.zkspc_zone_id,
                    "loop_kind": fire_alarm.loop_kind,
                    "loop_number": fire_alarm.loop_number,
                    "device_number": fire_alarm.device_number,
                    "zone": fire_alarm.zone,
                    "address": fire_alarm.address,
                    "label_dx": fire_alarm.label_dx,
                    "label_dy": fire_alarm.label_dy,
                },
                scale_factor=scale_factor,
                rooms=rooms,
                zone_lookup=lambda room_id: self._find_zkspc_zone_for_room(floor_plan_id, room_id),
            )
            fire_alarm.room_id = metadata["room_id"]
            fire_alarm.offset_left_m = metadata["offset_left_m"]
            fire_alarm.offset_top_m = metadata["offset_top_m"]
            if fire_alarm.room_id is not None:
                zone = self._find_zkspc_zone_for_room(floor_plan_id, int(fire_alarm.room_id))
                fire_alarm.zkspc_zone_id = zone.id if zone is not None else None
                fire_alarm.zone = str(zone.zone_number) if zone is not None else fire_alarm.zone

    def _normalize_fire_alarm_payload(self, floor_plan_id: int, data: dict[str, Any]) -> dict[str, Any]:
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        rooms = [room.to_dict() for room in self.repository.list_rooms(floor_plan_id)]
        return FireAlarmMetadataPolicy.normalize(
            floor_plan_id=floor_plan_id,
            data=data,
            scale_factor=floor_plan.scale_factor or 1.0,
            rooms=rooms,
            zone_lookup=lambda room_id: self._find_zkspc_zone_for_room(floor_plan_id, room_id),
        ) | {
            "equipment_id": resolve_project_equipment_id(
                floor_plan,
                FIRE_ALARM_DEVICE_CATEGORY_MAP.get(str(data.get("device_type") or ""), ()),
                data.get("equipment_id"),
                entity_label="fire alarm device",
            )
        }

    def _find_zkspc_zone_for_room(self, floor_plan_id: int, room_id: int):
        for zone in self.repository.list_zkspc_zones(floor_plan_id):
            if any(link.room_id == room_id for link in zone.room_links):
                return zone
        return None


@dataclass(slots=True)
class SoueDeviceCrudUseCases:
    repository: ElementsRepository
    uow: UnitOfWork
    events: Any

    def list_soue_devices(self, floor_plan_id: int) -> list[SoueDeviceRecord]:
        return [SoueDeviceRecord.from_model(item) for item in self.repository.list_soue_devices(floor_plan_id)]

    def create_soue_device(self, payload) -> SoueDeviceRecord:
        normalized = self._normalize_soue_device_payload(payload.floor_plan_id, payload.model_dump())
        device = self.repository.create_soue_device(normalized)
        self.repository.add(device)
        self.uow.commit()
        self.repository.refresh(device)
        return SoueDeviceRecord.from_model(device)

    def update_soue_device(self, soue_device_id: int, payload) -> SoueDeviceRecord:
        device = self.repository.get_soue_device(soue_device_id)
        updates = payload.model_dump(exclude_unset=True)
        floor_plan_id = int(updates.get("floor_plan_id", device.floor_plan_id))
        merged = {
            "floor_plan_id": floor_plan_id,
            "x": updates.get("x", device.x),
            "y": updates.get("y", device.y),
            "device_type": updates.get("device_type", device.device_type),
            "device_model": updates.get("device_model", device.device_model),
            "sound_pressure_db": updates.get("sound_pressure_db", device.sound_pressure_db),
            "mounting_height": updates.get("mounting_height", device.mounting_height),
            "system_type": updates.get("system_type", device.system_type),
            "equipment_id": updates.get("equipment_id", device.equipment_id),
            "loop_kind": updates.get("loop_kind", device.loop_kind),
            "loop_number": updates.get("loop_number", device.loop_number),
            "device_number": updates.get("device_number", device.device_number),
            "room_id": updates.get("room_id", device.room_id),
            "offset_left_m": updates.get("offset_left_m", device.offset_left_m),
            "offset_top_m": updates.get("offset_top_m", device.offset_top_m),
            "label_dx": updates.get("label_dx", device.label_dx),
            "label_dy": updates.get("label_dy", device.label_dy),
        }
        normalized = self._normalize_soue_device_payload(floor_plan_id, merged)
        for field, value in normalized.items():
            setattr(device, field, value)
        self.uow.commit()
        self.repository.refresh(device)
        return SoueDeviceRecord.from_model(device)

    def delete_soue_device(self, soue_device_id: int) -> None:
        self.repository.delete(self.repository.get_soue_device(soue_device_id))
        self.uow.commit()

    def refresh_metadata_for_floor_plan(self, floor_plan_id: int) -> None:
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        rooms = [room.to_dict() for room in self.repository.list_rooms(floor_plan_id)]
        scale_factor = floor_plan.scale_factor or 1.0
        for device in self.repository.list_soue_devices(floor_plan_id):
            metadata = SoueDeviceMetadataPolicy.normalize(
                floor_plan_id=floor_plan_id,
                data={
                    "x": device.x,
                    "y": device.y,
                    "device_type": device.device_type,
                    "device_model": device.device_model,
                    "sound_pressure_db": device.sound_pressure_db,
                    "mounting_height": device.mounting_height,
                    "system_type": device.system_type,
                    "loop_kind": device.loop_kind,
                    "loop_number": device.loop_number,
                    "device_number": device.device_number,
                    "label_dx": device.label_dx,
                    "label_dy": device.label_dy,
                },
                scale_factor=scale_factor,
                rooms=rooms,
            )
            device.room_id = metadata["room_id"]
            device.offset_left_m = metadata["offset_left_m"]
            device.offset_top_m = metadata["offset_top_m"]

    def _normalize_soue_device_payload(self, floor_plan_id: int, data: dict[str, Any]) -> dict[str, Any]:
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        rooms = [room.to_dict() for room in self.repository.list_rooms(floor_plan_id)]
        return SoueDeviceMetadataPolicy.normalize(
            floor_plan_id=floor_plan_id,
            data=data,
            scale_factor=floor_plan.scale_factor or 1.0,
            rooms=rooms,
        ) | {
            "equipment_id": resolve_project_equipment_id(
                floor_plan,
                SOUE_DEVICE_CATEGORY_MAP.get(str(data.get("device_type") or ""), ()),
                data.get("equipment_id"),
                entity_label="SOUE device",
            )
        }


@dataclass(slots=True)
class BatchSaveFloorPlanUseCase:
    repository: ElementsRepository
    uow: UnitOfWork
    events: Any

    def execute(self, floor_plan_id: int, payload) -> FloorPlanRecord:
        floor_plan = self.repository.get_floor_plan(floor_plan_id)
        wall_use_cases = WallUseCases(self.repository, self.uow, self.events)
        fire_alarms = FireAlarmCrudUseCases(self.repository, self.uow, self.events)
        soue_devices = SoueDeviceCrudUseCases(self.repository, self.uow, self.events)
        walls_changed = False
        touched_fire_alarm_systems: set[str] = set()
        touched_soue_systems: set[str] = set()
        deleted_ids_by_type: dict[str, set[int]] = {
            "walls": set(),
            "stairs": set(),
            "doors": set(),
            "windows": set(),
            "fire-alarms": set(),
            "soue-devices": set(),
            "rooms": set(),
            "dimensions": set(),
        }

        for item in payload.deleted:
            deleted_ids_by_type.setdefault(item.element_type, set()).add(int(item.id))
            if item.element_type == "walls":
                walls_changed = True
            if item.element_type == "fire-alarms":
                alarm = self.repository.get_optional_by_type("fire_alarm", item.id)
                if alarm is not None:
                    touched_fire_alarm_systems.add(alarm.system_type if alarm.system_type in {"addressable", "non_addressable"} else "non_addressable")
            if item.element_type == "soue-devices":
                device = self.repository.get_optional_by_type("soue_device", item.id)
                if device is not None:
                    touched_soue_systems.add(device.system_type if device.system_type in {"addressable", "non_addressable"} else "non_addressable")
            self._delete_by_type(item.element_type, item.id, missing_ok=item.element_type in {"doors", "windows"})

        for wall_payload in payload.create_walls:
            wall = self.repository.create_wall(wall_payload.model_dump())
            wall.floor_plan_id = floor_plan_id
            self.repository.add(wall)
            walls_changed = True
        for stair_payload in payload.create_stairs:
            data = StairGeometryPolicy.normalize(stair_payload.model_dump())
            data["floor_plan_id"] = floor_plan_id
            self.repository.add(self.repository.create_stair(data))
        self.repository.flush()
        floor_plan_scale = self.repository.get_floor_plan(floor_plan_id).scale_factor or 1.0
        walls = self.repository.list_walls(floor_plan_id)
        room_payloads = [_model_to_payload(room) for room in self.repository.list_rooms(floor_plan_id)]
        for door_payload in payload.create_doors:
            data = OpeningNormalizationPolicy.normalize(
                {**door_payload.model_dump(), "floor_plan_id": floor_plan_id},
                floor_plan_scale_factor=floor_plan_scale,
                walls=walls,
                strict=True,
            )
            if door_payload.is_evacuation_exit is None:
                data["is_evacuation_exit"] = _infer_door_evacuation_exit(data, room_payloads)
            self.repository.add(self.repository.create_door(data))
        for window_payload in payload.create_windows:
            data = OpeningNormalizationPolicy.normalize(
                {**window_payload.model_dump(), "floor_plan_id": floor_plan_id},
                floor_plan_scale_factor=floor_plan_scale,
                walls=walls,
                strict=True,
            )
            self.repository.add(self.repository.create_window(data))
        for fire_alarm_payload in payload.create_fire_alarms:
            data = fire_alarms._normalize_fire_alarm_payload(floor_plan_id, fire_alarm_payload.model_dump())
            data["floor_plan_id"] = floor_plan_id
            touched_fire_alarm_systems.add(data["system_type"])
            self.repository.add(self.repository.create_fire_alarm(data))
        for soue_payload in payload.create_soue_devices:
            data = soue_devices._normalize_soue_device_payload(floor_plan_id, soue_payload.model_dump())
            data["floor_plan_id"] = floor_plan_id
            touched_soue_systems.add(data["system_type"])
            self.repository.add(self.repository.create_soue_device(data))
        for command in payload.update_walls:
            if command.id in deleted_ids_by_type["walls"]:
                continue
            wall = self.repository.get_wall(command.id)
            for field, value in command.data.model_dump(exclude_unset=True).items():
                setattr(wall, field, value)
            walls_changed = True
        for command in payload.update_stairs:
            if command.id in deleted_ids_by_type["stairs"]:
                continue
            stair = self.repository.get_stair(command.id)
            normalized = StairGeometryPolicy.normalize(
                {
                    "floor_plan_id": command.data.floor_plan_id if command.data.floor_plan_id is not None else stair.floor_plan_id,
                    "x": command.data.x if command.data.x is not None else stair.x,
                    "y": command.data.y if command.data.y is not None else stair.y,
                    "width": command.data.width if command.data.width is not None else stair.width,
                    "height": command.data.height if command.data.height is not None else stair.height,
                    "rotation_deg": command.data.rotation_deg if command.data.rotation_deg is not None else stair.rotation_deg,
                    "step_count": command.data.step_count if command.data.step_count is not None else stair.step_count,
                    "step_axis": command.data.step_axis,
                }
            )
            for field, value in normalized.items():
                setattr(stair, field, value)
        for command in payload.update_doors:
            if command.id in deleted_ids_by_type["doors"]:
                continue
            door = self._get_or_stale("door", command.id, "door")
            normalized = OpeningNormalizationPolicy.normalize(
                {
                    "floor_plan_id": command.data.floor_plan_id if command.data.floor_plan_id is not None else door.floor_plan_id,
                    "x": command.data.x if command.data.x is not None else door.x,
                    "y": command.data.y if command.data.y is not None else door.y,
                    "width": command.data.width if command.data.width is not None else door.width,
                    "height": command.data.height if command.data.height is not None else door.height,
                    "wall_id": command.data.wall_id if command.data.wall_id is not None else door.wall_id,
                    "rotation_deg": command.data.rotation_deg if command.data.rotation_deg is not None else door.rotation_deg,
                    "door_type": command.data.door_type if command.data.door_type is not None else door.door_type,
                    "swing_angle": command.data.swing_angle if command.data.swing_angle is not None else door.swing_angle,
                    "swing_direction": (
                        command.data.swing_direction
                        if command.data.swing_direction is not None
                        else door.swing_direction
                    ),
                    "is_evacuation_exit": (
                        command.data.is_evacuation_exit
                        if command.data.is_evacuation_exit is not None
                        else door.is_evacuation_exit
                    ),
                },
                floor_plan_scale_factor=floor_plan_scale,
                walls=walls,
                strict=True,
            )
            for field, value in normalized.items():
                setattr(door, field, value)
        for command in payload.update_windows:
            if command.id in deleted_ids_by_type["windows"]:
                continue
            window = self._get_or_stale("window", command.id, "window")
            normalized = OpeningNormalizationPolicy.normalize(
                {
                    "floor_plan_id": command.data.floor_plan_id if command.data.floor_plan_id is not None else window.floor_plan_id,
                    "x": command.data.x if command.data.x is not None else window.x,
                    "y": command.data.y if command.data.y is not None else window.y,
                    "width": command.data.width if command.data.width is not None else window.width,
                    "height": command.data.height if command.data.height is not None else window.height,
                    "wall_id": command.data.wall_id if command.data.wall_id is not None else window.wall_id,
                    "rotation_deg": command.data.rotation_deg if command.data.rotation_deg is not None else window.rotation_deg,
                    "window_type": window.window_type,
                },
                floor_plan_scale_factor=floor_plan_scale,
                walls=walls,
                strict=True,
            )
            for field, value in normalized.items():
                setattr(window, field, value)
        for command in payload.update_rooms:
            if command.id in deleted_ids_by_type["rooms"]:
                continue
            room = self.repository.get_room(command.id)
            floor_plan_for_room = self.repository.get_floor_plan(room.floor_plan_id)
            for field, value in command.data.model_dump(exclude_unset=True).items():
                setattr(room, field, value)
            RoomGeometryPolicy.refresh(room, floor_plan_for_room.scale_factor)
        for command in payload.update_fire_alarms:
            if command.id in deleted_ids_by_type["fire-alarms"]:
                continue
            fire_alarm = self.repository.get_fire_alarm(command.id)
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
                "equipment_id": updates.get("equipment_id", fire_alarm.equipment_id),
                "zkspc_zone_id": updates.get("zkspc_zone_id", fire_alarm.zkspc_zone_id),
                "loop_kind": updates.get("loop_kind", fire_alarm.loop_kind),
                "loop_number": updates.get("loop_number", fire_alarm.loop_number),
                "device_number": updates.get("device_number", fire_alarm.device_number),
                "zone": updates.get("zone", fire_alarm.zone),
                "address": updates.get("address", fire_alarm.address),
                "label_dx": updates.get("label_dx", fire_alarm.label_dx),
                "label_dy": updates.get("label_dy", fire_alarm.label_dy),
            }
            normalized_alarm = fire_alarms._normalize_fire_alarm_payload(floor_plan_id_for_alarm, merged)
            touched_fire_alarm_systems.add(normalized_alarm["system_type"])
            for field, value in normalized_alarm.items():
                setattr(fire_alarm, field, value)
        for command in payload.update_soue_devices:
            if command.id in deleted_ids_by_type["soue-devices"]:
                continue
            device = self.repository.get_soue_device(command.id)
            updates = command.data.model_dump(exclude_unset=True)
            floor_plan_id_for_device = int(updates.get("floor_plan_id", device.floor_plan_id))
            merged = {
                "floor_plan_id": floor_plan_id_for_device,
                "x": updates.get("x", device.x),
                "y": updates.get("y", device.y),
                "device_type": updates.get("device_type", device.device_type),
                "device_model": updates.get("device_model", device.device_model),
                "sound_pressure_db": updates.get("sound_pressure_db", device.sound_pressure_db),
                "mounting_height": updates.get("mounting_height", device.mounting_height),
                "system_type": updates.get("system_type", device.system_type),
                "equipment_id": updates.get("equipment_id", device.equipment_id),
                "loop_kind": updates.get("loop_kind", device.loop_kind),
                "loop_number": updates.get("loop_number", device.loop_number),
                "device_number": updates.get("device_number", device.device_number),
                "label_dx": updates.get("label_dx", device.label_dx),
                "label_dy": updates.get("label_dy", device.label_dy),
            }
            normalized_device = soue_devices._normalize_soue_device_payload(floor_plan_id_for_device, merged)
            touched_soue_systems.add(normalized_device["system_type"])
            for field, value in normalized_device.items():
                setattr(device, field, value)

        if walls_changed:
            wall_use_cases._relink_or_prune_openings(floor_plan_id, delete_invalid=True)
            touched_fire_alarm_systems.update(
                alarm.system_type if alarm.system_type in {"addressable", "non_addressable"} else "non_addressable"
                for alarm in self.repository.list_fire_alarms(floor_plan_id)
            )
            touched_soue_systems.update(
                device.system_type if device.system_type in {"addressable", "non_addressable"} else "non_addressable"
                for device in self.repository.list_soue_devices(floor_plan_id)
            )
        fire_alarms.refresh_metadata_for_floor_plan(floor_plan_id)
        soue_devices.refresh_metadata_for_floor_plan(floor_plan_id)
        for system_type in touched_fire_alarm_systems:
            self.repository.delete_routes_for_branch(floor_plan_id, system_type, subsystem_type="sps")
            branch_alarm_models = [
                alarm
                for alarm in self.repository.list_fire_alarms(floor_plan_id)
                if alarm.system_type == system_type
            ]
            for alarm in branch_alarm_models:
                alarm.loop_kind = None
                alarm.loop_number = None
                alarm.device_number = None
                alarm.address = None
            update_signal_branch_state(
                floor_plan,
                system_type,
                fire_alarms_status="validated",
                devices_cables_status="draft" if branch_alarm_models else "validated",
                active_step="devices_cables",
            )
        for system_type in touched_soue_systems:
            self.repository.delete_routes_for_branch(floor_plan_id, system_type, subsystem_type="soue")
            branch_soue_models = [
                device
                for device in self.repository.list_soue_devices(floor_plan_id)
                if device.system_type == system_type
            ]
            for device in branch_soue_models:
                device.loop_kind = None
                device.loop_number = None
                device.device_number = None
            update_signal_branch_state(
                floor_plan,
                system_type,
                soue_devices_status="validated",
                soue_cables_status="draft" if branch_soue_models else "validated",
                active_step="soue_cables",
            )
        self.uow.commit()
        self.repository.refresh(floor_plan)
        self.events.publish(
            "batch_save_completed",
            {"category": "elements", "use_case": "BatchSaveFloorPlan", "floor_plan_id": floor_plan_id, "payload": {"walls_changed": walls_changed}},
        )
        return FloorPlanRecord.from_model(floor_plan, include_elements=True)

    def _delete_by_type(self, element_type: str, entity_id: int, *, missing_ok: bool = False) -> None:
        lookup_map = {
            "walls": ("wall", "wall_not_found", "Wall not found"),
            "stairs": ("stair", "stair_not_found", "Stair not found"),
            "doors": ("door", "door_not_found", "Door not found"),
            "windows": ("window", "window_not_found", "Window not found"),
            "fire-alarms": ("fire_alarm", "fire_alarm_not_found", "Fire alarm not found"),
            "soue-devices": ("soue_device", "soue_device_not_found", "SOUe device not found"),
            "rooms": ("room", "room_not_found", "Room not found"),
            "dimensions": ("dimension", "dimension_not_found", "Dimension not found"),
        }
        entity_type, code, detail = lookup_map[element_type]
        entity = self.repository.get_optional_by_type(entity_type, entity_id)
        if entity is None:
            if missing_ok:
                return
            raise AppError(404, code, detail)
        self.repository.delete(entity)

    def _get_or_stale(self, entity_type: str, entity_id: int, entity_name: str):
        entity = self.repository.get_optional_by_type(entity_type, entity_id)
        if entity is None:
            raise AppError(
                409,
                "stale_editor_state",
                f"{entity_name.capitalize()} is out of date. Reload the floor plan and try again.",
            )
        return entity


class ElementsGeometryUseCases:
    """Composition root for explicit element geometry use cases."""

    def __init__(self, repository: ElementsRepository, uow: UnitOfWork, events: Any | None = None):
        publisher = events or NoOpEventPublisher()
        self.walls = WallUseCases(repository, uow, publisher)
        self.openings = OpeningUseCases(repository, uow, publisher)
        self.stairs = StairUseCases(repository, uow, publisher)
        self.rooms = RoomUseCases(repository, uow, publisher)
        self.dimensions = DimensionUseCases(repository, uow, publisher)
        self.fire_alarms = FireAlarmCrudUseCases(repository, uow, publisher)
        self.soue_devices = SoueDeviceCrudUseCases(repository, uow, publisher)
        self.batch = BatchSaveFloorPlanUseCase(repository, uow, publisher)

    def list_walls(self, floor_plan_id: int) -> list[WallRecord]:
        return self.walls.list_walls(floor_plan_id)

    def create_wall(self, payload) -> WallRecord:
        return self.walls.create_wall(payload)

    def update_wall(self, wall_id: int, payload) -> WallRecord:
        return self.walls.update_wall(wall_id, payload)

    def delete_wall(self, wall_id: int) -> None:
        self.walls.delete_wall(wall_id)

    def list_doors(self, floor_plan_id: int) -> list[DoorRecord]:
        return self.openings.list_doors(floor_plan_id)

    def create_door(self, payload) -> DoorRecord:
        return self.openings.create_door(payload)

    def update_door(self, door_id: int, payload) -> DoorRecord:
        return self.openings.update_door(door_id, payload)

    def delete_door(self, door_id: int) -> None:
        self.openings.delete_door(door_id)

    def list_windows(self, floor_plan_id: int) -> list[WindowRecord]:
        return self.openings.list_windows(floor_plan_id)

    def create_window(self, payload) -> WindowRecord:
        return self.openings.create_window(payload)

    def update_window(self, window_id: int, payload) -> WindowRecord:
        return self.openings.update_window(window_id, payload)

    def delete_window(self, window_id: int) -> None:
        self.openings.delete_window(window_id)

    def relink_or_prune_openings(self, floor_plan_id: int, delete_invalid: bool = True) -> None:
        self.openings.relink_or_prune_openings(floor_plan_id, delete_invalid=delete_invalid)

    def normalize_floor_plan_openings(self, floor_plan_id: int) -> None:
        self.openings.normalize_floor_plan_openings(floor_plan_id)

    def list_stairs(self, floor_plan_id: int) -> list[StairRecord]:
        return self.stairs.list_stairs(floor_plan_id)

    def create_stair(self, payload) -> StairRecord:
        return self.stairs.create_stair(payload)

    def update_stair(self, stair_id: int, payload) -> StairRecord:
        return self.stairs.update_stair(stair_id, payload)

    def delete_stair(self, stair_id: int) -> None:
        self.stairs.delete_stair(stair_id)

    def list_rooms(self, floor_plan_id: int) -> list[RoomRecord]:
        return self.rooms.list_rooms(floor_plan_id)

    def create_room(self, payload) -> RoomRecord:
        return self.rooms.create_room(payload)

    def update_room(self, room_id: int, payload) -> RoomRecord:
        return self.rooms.update_room(room_id, payload)

    def delete_room(self, room_id: int) -> None:
        self.rooms.delete_room(room_id)

    def list_dimensions(self, floor_plan_id: int) -> list[DimensionRecord]:
        return self.dimensions.list_dimensions(floor_plan_id)

    def create_dimension(self, payload) -> DimensionRecord:
        return self.dimensions.create_dimension(payload)

    def delete_dimension(self, dimension_id: int) -> None:
        self.dimensions.delete_dimension(dimension_id)

    def list_fire_alarms(self, floor_plan_id: int) -> list[FireAlarmRecord]:
        return self.fire_alarms.list_fire_alarms(floor_plan_id)

    def create_fire_alarm(self, payload) -> FireAlarmRecord:
        return self.fire_alarms.create_fire_alarm(payload)

    def update_fire_alarm(self, fire_alarm_id: int, payload) -> FireAlarmRecord:
        return self.fire_alarms.update_fire_alarm(fire_alarm_id, payload)

    def delete_fire_alarm(self, fire_alarm_id: int) -> None:
        self.fire_alarms.delete_fire_alarm(fire_alarm_id)

    def replace_fire_alarms(self, floor_plan_id: int, fire_alarm_payloads: list[dict[str, Any]], system_type: str | None = None) -> None:
        self.fire_alarms.replace_fire_alarms(floor_plan_id, fire_alarm_payloads, system_type=system_type)

    def refresh_fire_alarm_metadata_for_floor_plan(self, floor_plan_id: int) -> None:
        self.fire_alarms.refresh_metadata_for_floor_plan(floor_plan_id)

    def list_soue_devices(self, floor_plan_id: int) -> list[SoueDeviceRecord]:
        return self.soue_devices.list_soue_devices(floor_plan_id)

    def create_soue_device(self, payload) -> SoueDeviceRecord:
        return self.soue_devices.create_soue_device(payload)

    def update_soue_device(self, soue_device_id: int, payload) -> SoueDeviceRecord:
        return self.soue_devices.update_soue_device(soue_device_id, payload)

    def delete_soue_device(self, soue_device_id: int) -> None:
        self.soue_devices.delete_soue_device(soue_device_id)

    def refresh_soue_device_metadata_for_floor_plan(self, floor_plan_id: int) -> None:
        self.soue_devices.refresh_metadata_for_floor_plan(floor_plan_id)

    def batch_save(self, floor_plan_id: int, payload) -> FloorPlanRecord:
        return self.batch.execute(floor_plan_id, payload)
