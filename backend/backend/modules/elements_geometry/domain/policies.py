"""Domain policies for element geometry workflows."""

from __future__ import annotations

import math
from typing import Any, Callable

from backend.errors import AppError
from backend.fire_alarm_placement import locate_fire_alarm_metadata


class StairGeometryPolicy:
    """Normalizes stair payload geometry."""

    @staticmethod
    def normalize(data: dict[str, Any]) -> dict[str, Any]:
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


class RoomGeometryPolicy:
    """Refreshes room-derived geometric values."""

    @staticmethod
    def refresh(room, scale_factor: float) -> None:
        if room.boundary_points:
            room.calculate_center()
            room.calculate_length_width(scale_factor)
            room.calculate_area(scale_factor)
            room.calculate_perimeter(scale_factor)
            return

        room.length_m = None
        room.width_m = None
        room.area_sqm = 0.0
        room.perimeter_m = 0.0


class OpeningNormalizationPolicy:
    """Normalizes doors and windows against the closest valid wall."""

    @staticmethod
    def normalize(
        data: dict[str, Any],
        *,
        floor_plan_scale_factor: float,
        walls: list[Any],
        strict: bool = True,
    ) -> dict[str, Any] | None:
        wall = OpeningNormalizationPolicy.resolve_wall(
            floor_plan_id=int(data["floor_plan_id"]),
            x=float(data["x"]),
            y=float(data["y"]),
            width=float(data["width"]),
            height=float(data.get("height", data["width"])),
            wall_id=data.get("wall_id"),
            walls=walls,
            scale_factor=floor_plan_scale_factor,
            strict=strict,
        )
        if wall is None:
            return None

        dx = wall.x2 - wall.x1
        dy = wall.y2 - wall.y1
        wall_length = math.hypot(dx, dy)
        if wall_length < 1e-6:
            raise AppError(422, "opening_outside_wall", "Opening must be located on a wall")

        axis_x = dx / wall_length
        axis_y = dy / wall_length
        normal_x = -axis_y
        normal_y = axis_x
        rotation_deg = math.degrees(math.atan2(dy, dx))
        thickness_px = max(1.0, float(wall.thickness or 1.0) / floor_plan_scale_factor)
        positive_offset, negative_offset = OpeningNormalizationPolicy.wall_normal_offsets_px(
            wall,
            floor_plan_scale_factor,
        )
        center_shift = (positive_offset - negative_offset) / 2.0

        width = max(4.0, min(float(data["width"]), wall_length))
        center_x = float(data["x"]) + float(data["width"]) / 2.0
        center_y = float(data["y"]) + float(data.get("height", thickness_px)) / 2.0
        projected = ((center_x - wall.x1) * dx + (center_y - wall.y1) * dy) / wall_length
        half_width = width / 2.0
        along = min(max(projected, half_width), max(half_width, wall_length - half_width))
        normalized_center_x = wall.x1 + axis_x * along + normal_x * center_shift
        normalized_center_y = wall.y1 + axis_y * along + normal_y * center_shift

        return {
            **data,
            "x": normalized_center_x - width / 2.0,
            "y": normalized_center_y - thickness_px / 2.0,
            "width": width,
            "height": thickness_px,
            "rotation_deg": rotation_deg,
            "wall_id": wall.id,
        }

    @staticmethod
    def resolve_wall(
        *,
        floor_plan_id: int,
        x: float,
        y: float,
        width: float,
        height: float,
        wall_id: int | None,
        walls: list[Any],
        scale_factor: float,
        strict: bool = True,
    ):
        if not walls:
            if strict:
                raise AppError(422, "wall_not_found_for_opening", "No walls available for opening placement")
            return None

        center_x = float(x) + float(width) / 2.0
        center_y = float(y) + float(height) / 2.0
        projection_margin = max(float(width), float(height), 1.0)

        def distance_to_wall(wall) -> tuple[float, bool]:
            dx = wall.x2 - wall.x1
            dy = wall.y2 - wall.y1
            length = math.hypot(dx, dy)
            if length < 1e-6:
                return float("inf"), False

            axis_x = dx / length
            axis_y = dy / length
            normal_x = -axis_y
            normal_y = axis_x
            along = ((center_x - wall.x1) * axis_x) + ((center_y - wall.y1) * axis_y)
            signed = ((center_x - wall.x1) * normal_x) + ((center_y - wall.y1) * normal_y)
            positive_offset, negative_offset = OpeningNormalizationPolicy.wall_normal_offsets_px(wall, scale_factor)
            thickness_px = max(1.0, (wall.thickness or 1.0) / scale_factor)
            max_distance = max(thickness_px, min(float(width), float(height), 40.0))
            within_projection = -projection_margin <= along <= (length + projection_margin)
            within_thickness = (
                signed >= (-negative_offset - max_distance)
                and signed <= (positive_offset + max_distance)
            )
            if signed < -negative_offset:
                distance = abs(signed + negative_offset)
            elif signed > positive_offset:
                distance = abs(signed - positive_offset)
            else:
                distance = 0.0
            return distance, within_projection and within_thickness

        if wall_id is not None:
            matching_wall = next((wall for wall in walls if wall.id == wall_id), None)
            if matching_wall is not None:
                if matching_wall.floor_plan_id != floor_plan_id:
                    if strict:
                        raise AppError(422, "opening_wall_mismatch", "Opening wall must belong to the same floor plan")
                else:
                    _distance, fits = distance_to_wall(matching_wall)
                    if fits:
                        return matching_wall

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

    @staticmethod
    def wall_normal_offsets_px(wall, scale_factor: float) -> tuple[float, float]:
        thickness_px = max(1.0, float(wall.thickness or 1.0) / max(scale_factor, 1e-6))
        alignment = str(getattr(wall, "alignment", "center") or "center").lower()
        if alignment == "left":
            return thickness_px, 0.0
        if alignment == "right":
            return 0.0, thickness_px
        half = thickness_px / 2.0
        return half, half


class FireAlarmMetadataPolicy:
    """Normalizes fire alarm placement metadata."""

    @staticmethod
    def normalize(
        *,
        floor_plan_id: int,
        data: dict[str, Any],
        scale_factor: float,
        rooms: list[dict[str, Any]],
        zone_lookup: Callable[[int], Any | None],
    ) -> dict[str, Any]:
        x = float(data["x"])
        y = float(data["y"])
        metadata = locate_fire_alarm_metadata(x, y, rooms, scale_factor)
        zkspc_zone_id = data.get("zkspc_zone_id")
        zone_number = data.get("zone")
        if metadata.get("room_id") is not None:
            zone = zone_lookup(int(metadata["room_id"]))
            if zone is not None:
                zkspc_zone_id = zone.id
                zone_number = str(zone.zone_number)

        return {
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


class SoueDeviceMetadataPolicy:
    """Normalizes SOUE device placement metadata."""

    @staticmethod
    def normalize(
        *,
        floor_plan_id: int,
        data: dict[str, Any],
        scale_factor: float,
        rooms: list[dict[str, Any]],
    ) -> dict[str, Any]:
        x = float(data["x"])
        y = float(data["y"])
        metadata = locate_fire_alarm_metadata(x, y, rooms, scale_factor)
        device_type = str(data.get("device_type") or "siren")
        default_model = "Комптид-1" if device_type == "siren" else "Выход-12"
        default_sound_pressure = 98.0 if device_type == "siren" else None
        default_height = 2.3 if device_type == "exit_sign" else 2.4

        return {
            **data,
            "floor_plan_id": floor_plan_id,
            "x": x,
            "y": y,
            "device_type": device_type if device_type in {"siren", "exit_sign"} else "siren",
            "device_model": (data.get("device_model") or default_model),
            "sound_pressure_db": (
                float(data["sound_pressure_db"])
                if data.get("sound_pressure_db") is not None
                else default_sound_pressure
            ),
            "mounting_height": (
                float(data["mounting_height"])
                if data.get("mounting_height") is not None
                else default_height
            ),
            "system_type": data.get("system_type") if data.get("system_type") in {"addressable", "non_addressable", "common"} else "common",
            "loop_kind": data.get("loop_kind"),
            "loop_number": int(data["loop_number"]) if data.get("loop_number") is not None else None,
            "device_number": int(data["device_number"]) if data.get("device_number") is not None else None,
            "label_dx": float(data["label_dx"]) if data.get("label_dx") is not None else None,
            "label_dy": float(data["label_dy"]) if data.get("label_dy") is not None else None,
            **metadata,
        }
