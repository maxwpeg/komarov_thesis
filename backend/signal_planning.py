"""Signal planning helpers for ZKSPC grouping and cable routing."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


SYSTEM_TYPES = {"addressable", "non_addressable", "common"}
MERGE_CAPABLE_INSTRUMENTS = {"control_panel", "loop_controller"}
DETECTOR_SYMBOL_HALF_SIZE_PX = 14.0
DEVICE_SIDE_ANCHOR_OFFSET_PX = DETECTOR_SYMBOL_HALF_SIZE_PX
ZC_SYMBOL_HALF_SIZE_PX = 5.4
ZC_ROUTE_OFFSET_PX = DEVICE_SIDE_ANCHOR_OFFSET_PX + ZC_SYMBOL_HALF_SIZE_PX
SINGLE_RING_DETOUR_PX = 18.0
SPS_SUBSYSTEM = "sps"
SOUE_SUBSYSTEM = "soue"
SIREN_DEFAULT_MODEL = "Комптид-1"
EXIT_SIGN_DEFAULT_MODEL = "Выход-12"
SIREN_DEFAULT_SOUND_PRESSURE_DB = 98.0
CONCRETE_WALL_LOSS_DB = 12.0
MIN_SOUE_SOUND_DB = 75.0
MAX_SOUE_SOUND_DB = 120.0
ROUTE_KIND_ORDER = {
    "ring": 0,
    "zone_loop": 1,
    "manual_line": 2,
    "siren_loop": 3,
    "exit_sign_loop": 4,
}

DEVICE_SIDE_VECTORS: dict[str, tuple[float, float]] = {
    "east": (1.0, 0.0),
    "west": (-1.0, 0.0),
    "north": (0.0, -1.0),
    "south": (0.0, 1.0),
}


def should_show_zc_terminator(route: dict[str, Any]) -> bool:
    if str(route.get("subsystem_type") or SPS_SUBSYSTEM) != SPS_SUBSYSTEM:
        return False
    system_type = str(route.get("system_type") or "non_addressable")
    route_kind = str(route.get("route_kind") or "")
    return system_type == "non_addressable" and route_kind in {"zone_loop", "manual_line"}


def _safe_scale(scale_factor: float | None) -> float:
    return float(scale_factor) if scale_factor and scale_factor > 0 else 1.0


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _alarm_identity(alarm: dict[str, Any], fallback_index: int) -> tuple[Any, ...]:
    alarm_id = alarm.get("id")
    if alarm_id is not None:
        return ("id", int(alarm_id))
    return (
        "coord",
        alarm.get("device_type"),
        int(alarm.get("loop_number") or 0),
        int(alarm.get("device_number") or fallback_index),
        round(float(alarm.get("x") or 0.0), 4),
        round(float(alarm.get("y") or 0.0), 4),
    )


def _point_signature(point: tuple[float, float]) -> tuple[float, float]:
    return round(float(point[0]), 3), round(float(point[1]), 3)


def _device_side_anchor(point: tuple[float, float], side: str, offset: float = DEVICE_SIDE_ANCHOR_OFFSET_PX) -> tuple[float, float]:
    vector = DEVICE_SIDE_VECTORS.get(side, (1.0, 0.0))
    return (
        round(float(point[0]) + (vector[0] * offset), 3),
        round(float(point[1]) + (vector[1] * offset), 3),
    )


def _zc_terminal_point(point: tuple[float, float], side: str) -> tuple[float, float]:
    vector = DEVICE_SIDE_VECTORS.get(side, (1.0, 0.0))
    return (
        round(float(point[0]) + (vector[0] * ZC_ROUTE_OFFSET_PX), 3),
        round(float(point[1]) + (vector[1] * ZC_ROUTE_OFFSET_PX), 3),
    )


def _side_order_for_vector(dx: float, dy: float) -> list[str]:
    if abs(dx) <= 1e-6 and abs(dy) <= 1e-6:
        return ["east", "north", "south", "west"]
    return [
        side
        for side, _score in sorted(
            (
                (side, -((vector[0] * dx) + (vector[1] * dy)))
                for side, vector in DEVICE_SIDE_VECTORS.items()
            ),
            key=lambda item: (item[1], item[0]),
        )
    ]


def _device_rect(point: tuple[float, float], half_size: float = DETECTOR_SYMBOL_HALF_SIZE_PX) -> tuple[float, float, float, float]:
    return (
        float(point[0]) - half_size,
        float(point[1]) - half_size,
        float(point[0]) + half_size,
        float(point[1]) + half_size,
    )


def _polyline_obstacle_rects(points: list[tuple[float, float]], padding: float = 3.0) -> list[tuple[float, float, float, float]]:
    obstacles: list[tuple[float, float, float, float]] = []
    for start, end in zip(points, points[1:]):
        x1, y1 = float(start[0]), float(start[1])
        x2, y2 = float(end[0]), float(end[1])
        obstacles.append(
            (
                min(x1, x2) - padding,
                min(y1, y2) - padding,
                max(x1, x2) + padding,
                max(y1, y2) + padding,
            )
        )
    return obstacles


def _range_overlaps(a1: float, a2: float, b1: float, b2: float) -> bool:
    return max(min(a1, a2), min(b1, b2)) <= min(max(a1, a2), max(b1, b2))


def _segment_intersects_rect(
    start: tuple[float, float],
    end: tuple[float, float],
    rect: tuple[float, float, float, float],
) -> bool:
    left, top, right, bottom = rect
    x1, y1 = float(start[0]), float(start[1])
    x2, y2 = float(end[0]), float(end[1])
    if max(x1, x2) < left or min(x1, x2) > right or max(y1, y2) < top or min(y1, y2) > bottom:
        return False
    if abs(y1 - y2) <= 1e-6:
        return top <= y1 <= bottom and _range_overlaps(x1, x2, left, right)
    if abs(x1 - x2) <= 1e-6:
        return left <= x1 <= right and _range_overlaps(y1, y2, top, bottom)
    return not (
        max(x1, x2) < left
        or min(x1, x2) > right
        or max(y1, y2) < top
        or min(y1, y2) > bottom
    )


def _polyline_rect_collision_count(
    polyline: list[tuple[float, float]],
    rects: list[tuple[float, float, float, float]],
) -> int:
    collision_count = 0
    for start, end in zip(polyline, polyline[1:]):
        if any(_segment_intersects_rect(start, end, rect) for rect in rects):
            collision_count += 1
    return collision_count


def _dedupe_alarms(alarms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for index, alarm in enumerate(alarms, start=1):
        identity = _alarm_identity(alarm, index)
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(alarm)
    return unique


def _bounding_box(points: list[list[float]]) -> tuple[float, float, float, float]:
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _boxes_touch(a: tuple[float, float, float, float], b: tuple[float, float, float, float], margin: float = 12.0) -> bool:
    return not (
        a[2] + margin < b[0]
        or b[2] + margin < a[0]
        or a[3] + margin < b[1]
        or b[3] + margin < a[1]
    )


def _normalize_zone_name(zone_number: int, explicit: str | None = None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    return f"ЗКСПС {zone_number}"


def calculate_zkspc_layout(rooms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a conservative common ZKSPC layout from detected rooms."""
    valid_rooms = [
        room
        for room in rooms
        if (
            room.get("id") is not None
            and (room.get("boundary_points") or [])
            and room.get("room_type") != "необслуживаемое"
        )
    ]
    if not valid_rooms:
        return []

    room_boxes = {
        int(room["id"]): _bounding_box(room["boundary_points"])
        for room in valid_rooms
        if len(room.get("boundary_points") or []) >= 3
    }
    adjacency: dict[int, set[int]] = {int(room["id"]): set() for room in valid_rooms}
    for room in valid_rooms:
        room_id = int(room["id"])
        box = room_boxes.get(room_id)
        if box is None:
            continue
        for other in valid_rooms:
            other_id = int(other["id"])
            if other_id <= room_id:
                continue
            other_box = room_boxes.get(other_id)
            if other_box is None:
                continue
            if _boxes_touch(box, other_box):
                adjacency[room_id].add(other_id)
                adjacency[other_id].add(room_id)

    components: list[list[dict[str, Any]]] = []
    visited: set[int] = set()
    rooms_by_id = {int(room["id"]): room for room in valid_rooms}
    for room_id in rooms_by_id:
        if room_id in visited:
            continue
        queue = [room_id]
        component_ids: list[int] = []
        visited.add(room_id)
        while queue:
            current = queue.pop()
            component_ids.append(current)
            for neighbor in adjacency.get(current, set()):
                if neighbor in visited:
                    continue
                visited.add(neighbor)
                queue.append(neighbor)
        components.append([rooms_by_id[item_id] for item_id in sorted(component_ids)])

    zones: list[dict[str, Any]] = []
    zone_number = 1
    for component in components:
        current_rooms: list[dict[str, Any]] = []
        current_area = 0.0
        for room in component:
            room_area = float(room.get("area_sqm") or 0.0)
            if current_rooms and (len(current_rooms) >= 5 or current_area + room_area > 2000.0):
                zones.append(
                    _build_zone_definition(
                        zone_number=zone_number,
                        rooms=current_rooms,
                        is_manual=False,
                        is_locked=False,
                    )
                )
                zone_number += 1
                current_rooms = []
                current_area = 0.0
            current_rooms.append(room)
            current_area += room_area
        if current_rooms:
            zones.append(
                _build_zone_definition(
                    zone_number=zone_number,
                    rooms=current_rooms,
                    is_manual=False,
                    is_locked=False,
                )
            )
            zone_number += 1
    return zones


def _build_zone_definition(
    *,
    zone_number: int,
    rooms: list[dict[str, Any]],
    is_manual: bool,
    is_locked: bool,
    explicit_name: str | None = None,
) -> dict[str, Any]:
    area_sqm = round(sum(float(room.get("area_sqm") or 0.0) for room in rooms), 2)
    warnings = [
        "Пожарные отсеки, гостиничные номера и расстояния между изолированными выходами требуют ручной проверки.",
    ]
    if len(rooms) > 5:
        warnings.append("В ЗКСПС более 5 помещений.")
    if area_sqm > 2000.0:
        warnings.append("Площадь ЗКСПС превышает 2000 м2.")
    return {
        "zone_number": zone_number,
        "name": _normalize_zone_name(zone_number, explicit_name),
        "area_sqm": area_sqm,
        "room_count": len(rooms),
        "room_ids": [int(room["id"]) for room in rooms],
        "is_manual": is_manual,
        "is_locked": is_locked,
        "compliance_warnings": warnings,
    }


def route_length_m(polyline_points: list[list[float]], scale_factor: float | None) -> float:
    if len(polyline_points) < 2:
        return 0.0
    scale = _safe_scale(scale_factor)
    length_px = 0.0
    for start, end in zip(polyline_points, polyline_points[1:]):
        length_px += math.hypot(float(end[0]) - float(start[0]), float(end[1]) - float(start[1]))
    return round(length_px * scale / 1000.0, 3)


def build_alarm_route_metadata(routes: list[dict[str, Any]], *, system_type: str) -> dict[int, dict[str, Any]]:
    return build_device_route_metadata(routes, system_type=system_type)


def build_device_route_metadata(routes: list[dict[str, Any]], *, system_type: str) -> dict[int, dict[str, Any]]:
    system = system_type if system_type in SYSTEM_TYPES else "non_addressable"
    metadata: dict[int, dict[str, Any]] = {}
    branch_address = 1
    for route in sorted(
        routes,
        key=lambda item: (
            ROUTE_KIND_ORDER.get(str(item.get("route_kind") or ""), 99),
            int(item.get("route_number") or 0),
            int(item.get("instrument_id") or 0),
        ),
    ):
        route_kind = str(route.get("route_kind") or ("ring" if system == "addressable" else "zone_loop"))
        route_number = int(route.get("route_number") or 1)
        for index, device_id in enumerate(route.get("device_ids") or [], start=1):
            safe_device_id = int(device_id)
            if safe_device_id <= 0 or safe_device_id in metadata:
                continue
            metadata[safe_device_id] = {
                "loop_kind": route_kind,
                "loop_number": route_number,
                "device_number": index,
                "address": str(branch_address),
            }
            branch_address += 1
    return metadata


def build_soue_route_metadata(routes: list[dict[str, Any]], *, system_type: str) -> dict[int, dict[str, Any]]:
    return build_device_route_metadata(routes, system_type=system_type)


def calculate_soue_layout(
    floor_plan_data: dict[str, Any],
    *,
    scale_factor: float,
    system_type: str,
) -> dict[str, Any]:
    scale = _safe_scale(scale_factor)
    rooms = [room for room in (floor_plan_data.get("rooms") or []) if room.get("id") is not None]
    doors = floor_plan_data.get("doors") or []
    walls = floor_plan_data.get("walls") or []
    exit_signs, exit_warnings = _auto_layout_exit_signs(rooms, doors, scale, system_type)
    sirens, siren_warnings, uncovered_points = _auto_layout_sirens(rooms, walls, scale, system_type)
    devices = [*exit_signs, *sirens]
    return {
        "devices": devices,
        "summary": {
            "total_devices": len(devices),
            "sirens": len(sirens),
            "exit_signs": len(exit_signs),
            "uncovered_control_points": uncovered_points,
        },
        "warnings": [*exit_warnings, *siren_warnings],
    }


def recalculate_soue_cable_routes(
    floor_plan_data: dict[str, Any],
    *,
    system_type: str,
    instrument: dict[str, Any],
    devices: list[dict[str, Any]],
    use_shared_trunk: bool = False,
) -> list[dict[str, Any]]:
    system = system_type if system_type in SYSTEM_TYPES else "non_addressable"
    scale_factor = floor_plan_data.get("scale_factor")
    walls = floor_plan_data.get("walls") or []
    normalized_devices = _dedupe_alarms(devices)
    _ = use_shared_trunk
    grouped: list[tuple[str, list[dict[str, Any]]]] = [
        ("siren_loop", [device for device in normalized_devices if str(device.get("device_type") or "") == "siren"]),
        ("exit_sign_loop", [device for device in normalized_devices if str(device.get("device_type") or "") == "exit_sign"]),
    ]

    routes: list[dict[str, Any]] = []
    for route_number, (route_kind, group_devices) in enumerate(grouped, start=1):
        ordered = _optimize_alarm_order(
            (float(instrument["x"]), float(instrument["y"])),
            group_devices,
            walls,
            close_ring=False,
        )
        if not ordered:
            continue
        polyline = _build_polyline(
            start=(float(instrument["x"]), float(instrument["y"])),
            targets=[(float(item["x"]), float(item["y"])) for item in ordered],
            walls=walls,
            close_ring=False,
            trunk_anchor=None,
        )
        routes.append(
            {
                "system_type": system,
                "subsystem_type": SOUE_SUBSYSTEM,
                "instrument_id": instrument["id"],
                "route_kind": route_kind,
                "route_number": route_number,
                "polyline_points": polyline,
                "device_ids": [int(item["id"]) for item in ordered if item.get("id") is not None],
                "warnings": [],
                "length_m": route_length_m(polyline, scale_factor),
                "is_manual": False,
            }
        )
    return routes


def sort_branch_routes(routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        routes,
        key=lambda item: (
            ROUTE_KIND_ORDER.get(str(item.get("route_kind") or ""), 99),
            int(item.get("instrument_id") or 0),
            int(item.get("route_number") or 0),
            int(item.get("id") or 0),
        ),
    )


def normalize_branch_route_numbers(routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for route_number, route in enumerate(sort_branch_routes(routes), start=1):
        next_route = {
            **route,
            "route_number": route_number,
        }
        normalized.append(next_route)
    return normalized


def recalculate_cable_routes(
    floor_plan_data: dict[str, Any],
    *,
    system_type: str,
    instrument: dict[str, Any],
    alarms: list[dict[str, Any]],
    use_shared_trunk: bool = False,
) -> list[dict[str, Any]]:
    system = system_type if system_type in SYSTEM_TYPES else "non_addressable"
    scale_factor = floor_plan_data.get("scale_factor")
    walls = floor_plan_data.get("walls") or []
    normalized_alarms = _dedupe_alarms(alarms)
    _ = use_shared_trunk
    trunk_anchor = None
    all_device_rects = {
        _alarm_identity(alarm, index): _device_rect(_alarm_point(alarm))
        for index, alarm in enumerate(normalized_alarms, start=1)
    }
    occupied_side_usage: dict[tuple[Any, ...], dict[str, int]] = {}

    if system == "addressable":
        if not normalized_alarms:
            return []
        ordered = _optimize_alarm_order((float(instrument["x"]), float(instrument["y"])), normalized_alarms, walls, close_ring=True)
        polyline = _build_device_route_polyline(
            start=(float(instrument["x"]), float(instrument["y"])),
            devices=ordered,
            walls=walls,
            close_ring=True,
            append_zc=False,
            all_device_rects=all_device_rects,
            occupied_side_usage=occupied_side_usage,
        )
        return [
            {
                "system_type": system,
                "subsystem_type": SPS_SUBSYSTEM,
                "instrument_id": instrument["id"],
                "route_kind": "ring",
                "route_number": 1,
                "polyline_points": polyline,
                "device_ids": [int(item["id"]) for item in ordered if item.get("id") is not None],
                "warnings": [],
                "length_m": route_length_m(polyline, scale_factor),
                "is_manual": False,
            }
        ]

    grouped: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for alarm in normalized_alarms:
        if alarm.get("device_type") == "manual_call_point":
            route_number = int(alarm.get("loop_number") or len(grouped) + 1)
            grouped[("manual_line", route_number)].append(alarm)
            continue
        route_number = int(alarm.get("loop_number") or alarm.get("zkspc_zone_id") or 1)
        grouped[("zone_loop", route_number)].append(alarm)

    routes: list[dict[str, Any]] = []
    assigned_device_ids: set[int] = set()
    for index, ((route_kind, route_number), group_alarms) in enumerate(sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1]))):
        filtered_group = []
        for alarm in group_alarms:
            alarm_id = alarm.get("id")
            if alarm_id is not None and int(alarm_id) in assigned_device_ids:
                continue
            filtered_group.append(alarm)
        ordered = _optimize_alarm_order((float(instrument["x"]), float(instrument["y"])), filtered_group, walls, close_ring=False)
        if not ordered:
            continue
        for alarm in ordered:
            if alarm.get("id") is not None:
                assigned_device_ids.add(int(alarm["id"]))
        close_ring = False
        polyline = _build_device_route_polyline(
            start=(float(instrument["x"]), float(instrument["y"])),
            devices=ordered,
            walls=walls,
            close_ring=close_ring,
            append_zc=bool(ordered),
            all_device_rects=all_device_rects,
            occupied_side_usage=occupied_side_usage,
        )
        routes.append(
            {
                "system_type": system,
                "subsystem_type": SPS_SUBSYSTEM,
                "instrument_id": instrument["id"],
                "route_kind": route_kind,
                "route_number": route_number if route_number > 0 else index + 1,
                "polyline_points": polyline,
                "device_ids": [
                    int(item.get("id")) if item.get("id") is not None else -(device_index + 1)
                    for device_index, item in enumerate(ordered)
                ],
                "warnings": [],
                "length_m": route_length_m(polyline, scale_factor),
                "is_manual": False,
            }
        )
    return routes


def _auto_layout_exit_signs(
    rooms: list[dict[str, Any]],
    doors: list[dict[str, Any]],
    scale_factor: float,
    system_type: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    devices: list[dict[str, Any]] = []
    warnings: list[str] = []
    rooms_by_id = {int(room["id"]): room for room in rooms if room.get("id") is not None}

    for door in doors:
        adjacent_room_ids = _door_adjacent_room_ids(door, rooms)
        adjacent_rooms = [rooms_by_id[room_id] for room_id in adjacent_room_ids if room_id in rooms_by_id]
        if not _is_evacuation_exit_door(door, adjacent_rooms):
            continue
        placement_room = _choose_exit_sign_room(adjacent_rooms)
        if placement_room is None:
            warnings.append(f"Не удалось определить помещение для табло у двери {door.get('id') or '?'}")
            continue
        position = _offset_point_inside_room_from_door(door, placement_room, scale_factor)
        devices.append(_build_soue_preview_device(position, placement_room, rooms, scale_factor, system_type, device_type="exit_sign"))

    deduped_devices: list[dict[str, Any]] = []
    seen: set[tuple[int | None, int, int]] = set()
    for device in devices:
        identity = (
            int(device.get("room_id")) if device.get("room_id") is not None else None,
            int(round(float(device["x"]) * 10.0)),
            int(round(float(device["y"]) * 10.0)),
        )
        if identity in seen:
            continue
        seen.add(identity)
        deduped_devices.append(device)
    return deduped_devices, warnings


def _auto_layout_sirens(
    rooms: list[dict[str, Any]],
    walls: list[dict[str, Any]],
    scale_factor: float,
    system_type: str,
) -> tuple[list[dict[str, Any]], list[str], int]:
    serviceable_rooms = [
        room
        for room in rooms
        if (room.get("boundary_points") or []) and not _is_non_service_room(room)
    ]
    control_points: list[dict[str, Any]] = []
    for room in serviceable_rooms:
        for point in _room_sound_control_points(room, scale_factor):
            control_points.append({"room_id": int(room["id"]), "point": point})

    candidates: list[dict[str, Any]] = []
    for room in serviceable_rooms:
        for point in _room_siren_candidates(room, scale_factor):
            candidates.append(
                _build_soue_preview_device(
                    point,
                    room,
                    rooms,
                    scale_factor,
                    system_type,
                    device_type="siren",
                )
            )

    selected: list[dict[str, Any]] = []
    uncovered = set(range(len(control_points)))
    coverage_by_candidate = [
        _covered_control_point_ids(candidate, control_points, walls, scale_factor)
        for candidate in candidates
    ]

    while uncovered:
        best_index = -1
        best_gain = 0
        best_score = float("-inf")
        for index, covered_ids in enumerate(coverage_by_candidate):
            gain_ids = covered_ids & uncovered
            gain = len(gain_ids)
            if gain <= 0:
                continue
            score = gain - (0.001 * len(selected))
            if gain > best_gain or (gain == best_gain and score > best_score):
                best_index = index
                best_gain = gain
                best_score = score
        if best_index < 0:
            break
        selected.append(candidates[best_index])
        uncovered -= coverage_by_candidate[best_index]

    warnings: list[str] = []
    if uncovered:
        uncovered_room_ids = sorted({control_points[index]["room_id"] for index in uncovered})
        for room_id in uncovered_room_ids:
            room = next((item for item in serviceable_rooms if int(item["id"]) == room_id), None)
            room_label = (room or {}).get("name") or (room or {}).get("room_number") or f"помещение {room_id}"
            warnings.append(
                f"Не удалось автоматически обеспечить 75 дБА для {room_label}; проверьте расстановку сирен вручную."
            )
    return selected, warnings, len(uncovered)


def _build_soue_preview_device(
    point: tuple[float, float],
    room: dict[str, Any] | None,
    rooms: list[dict[str, Any]],
    scale_factor: float,
    system_type: str,
    *,
    device_type: str,
) -> dict[str, Any]:
    resolved_point = point if device_type == "exit_sign" else _resolve_soue_device_point(point, room, scale_factor, device_type)
    metadata = _device_room_metadata(resolved_point, rooms, scale_factor)
    return {
        "x": round(float(resolved_point[0]), 3),
        "y": round(float(resolved_point[1]), 3),
        "device_type": device_type,
        "device_model": SIREN_DEFAULT_MODEL if device_type == "siren" else EXIT_SIGN_DEFAULT_MODEL,
        "sound_pressure_db": SIREN_DEFAULT_SOUND_PRESSURE_DB if device_type == "siren" else None,
        "mounting_height": 2.4 if device_type == "siren" else 2.3,
        "system_type": system_type if system_type in SYSTEM_TYPES else "common",
        "loop_kind": None,
        "loop_number": None,
        "device_number": None,
        "room_id": metadata["room_id"] if metadata["room_id"] is not None else (room.get("id") if room else None),
        "offset_left_m": metadata["offset_left_m"],
        "offset_top_m": metadata["offset_top_m"],
        "label_dx": None,
        "label_dy": None,
    }


def _resolve_soue_device_point(
    point: tuple[float, float],
    room: dict[str, Any] | None,
    scale_factor: float,
    device_type: str,
) -> tuple[float, float]:
    polygon = room.get("boundary_points") if room else None
    if not polygon or len(polygon) < 3:
        return point
    center = _room_reference_center(room, polygon)
    current = (float(point[0]), float(point[1]))
    clearance_px = max(
        10.0 if device_type == "siren" else 12.0,
        (160.0 if device_type == "siren" else 220.0) / max(scale_factor, 1e-6),
    )
    for _ in range(8):
        min_distance = min(
            _distance(current, _project_point_to_segment(current, (float(start[0]), float(start[1])), (float(end[0]), float(end[1]))))
            for start, end in zip(polygon, polygon[1:] + polygon[:1])
        )
        if min_distance >= clearance_px and _point_in_polygon(current, polygon):
            return current
        vector_x = center[0] - current[0]
        vector_y = center[1] - current[1]
        vector_length = math.hypot(vector_x, vector_y)
        if vector_length <= 1e-6:
            break
        shift = max(2.0, clearance_px - min_distance + 2.0)
        current = (
            current[0] + (vector_x / vector_length) * shift,
            current[1] + (vector_y / vector_length) * shift,
        )
    return center if _point_in_polygon(center, polygon) else point


def _room_reference_center(
    room: dict[str, Any] | None,
    polygon: list[list[float]],
) -> tuple[float, float]:
    if room and room.get("center_x") is not None and room.get("center_y") is not None:
        return float(room["center_x"]), float(room["center_y"])
    return (
        sum(float(point[0]) for point in polygon) / len(polygon),
        sum(float(point[1]) for point in polygon) / len(polygon),
    )


def _device_room_metadata(
    point: tuple[float, float],
    rooms: list[dict[str, Any]],
    scale_factor: float,
) -> dict[str, float | int | None]:
    matched_room: dict[str, Any] | None = None
    for room in rooms:
        polygon = room.get("boundary_points") or []
        if polygon and _point_in_polygon(point, polygon):
            matched_room = room
            break
    if matched_room is None:
        return {"room_id": None, "offset_left_m": None, "offset_top_m": None}
    min_x, min_y, _max_x, _max_y = _bounding_box(matched_room["boundary_points"])
    return {
        "room_id": matched_room.get("id"),
        "offset_left_m": round(max(0.0, (point[0] - min_x) * scale_factor / 1000.0), 3),
        "offset_top_m": round(max(0.0, (point[1] - min_y) * scale_factor / 1000.0), 3),
    }


def _point_in_polygon(point: tuple[float, float], polygon: list[list[float]]) -> bool:
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


def _point_on_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
    tolerance: float = 1e-4,
) -> bool:
    px, py = point
    x1, y1 = start
    x2, y2 = end
    cross = abs((px - x1) * (y2 - y1) - (py - y1) * (x2 - x1))
    if cross > tolerance:
        return False
    dot = (px - x1) * (px - x2) + (py - y1) * (py - y2)
    return dot <= tolerance


def _is_non_service_room(room: dict[str, Any]) -> bool:
    return str(room.get("room_type") or "").strip().lower() == "необслуживаемое"


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
    keywords = ("зал", "демонстрац", "выстав", "auditor", "showroom")
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


def _is_evacuation_exit_door(door: dict[str, Any], adjacent_rooms: list[dict[str, Any]]) -> bool:
    if bool(door.get("is_evacuation_exit")):
        return True
    if len(adjacent_rooms) <= 1:
        return True
    if any(_is_path_like_room(room) for room in adjacent_rooms):
        return True
    if any(_is_large_public_room(room) for room in adjacent_rooms):
        return True
    return False


def _choose_exit_sign_room(adjacent_rooms: list[dict[str, Any]]) -> dict[str, Any] | None:
    for room in adjacent_rooms:
        if _is_large_public_room(room):
            return room
    for room in adjacent_rooms:
        if not _is_path_like_room(room):
            return room
    return adjacent_rooms[0] if adjacent_rooms else None


def _offset_point_inside_room_from_door(
    door: dict[str, Any],
    room: dict[str, Any],
    scale_factor: float,
) -> tuple[float, float]:
    center = (
        float(door.get("x") or 0.0) + (float(door.get("width") or 0.0) / 2.0),
        float(door.get("y") or 0.0) + (float(door.get("height") or 0.0) / 2.0),
    )
    return center


def _room_sound_control_points(room: dict[str, Any], scale_factor: float) -> list[tuple[float, float]]:
    polygon = room.get("boundary_points") or []
    if len(polygon) < 3:
        return []
    min_x, min_y, max_x, max_y = _bounding_box(polygon)
    step_px = max(16.0, 1000.0 / max(scale_factor, 1e-6))
    points: list[tuple[float, float]] = []
    y = min_y
    while y <= max_y + 1e-6:
        x = min_x
        while x <= max_x + 1e-6:
            point = (x, y)
            if _point_in_polygon(point, polygon):
                points.append(point)
            x += step_px
        y += step_px
    if room.get("center_x") is not None and room.get("center_y") is not None:
        points.append((float(room["center_x"]), float(room["center_y"])))
    for vertex in polygon:
        points.append((float(vertex[0]), float(vertex[1])))
    return _unique_layout_points(points)


def _room_siren_candidates(room: dict[str, Any], scale_factor: float) -> list[tuple[float, float]]:
    polygon = room.get("boundary_points") or []
    if len(polygon) < 3:
        return []
    center = (
        float(room.get("center_x") or sum(float(point[0]) for point in polygon) / len(polygon)),
        float(room.get("center_y") or sum(float(point[1]) for point in polygon) / len(polygon)),
    )
    step_px = max(30.0, 2500.0 / max(scale_factor, 1e-6))
    inset_px = max(16.0, 250.0 / max(scale_factor, 1e-6))
    candidates: list[tuple[float, float]] = []
    for index, start in enumerate(polygon):
        end = polygon[(index + 1) % len(polygon)]
        start_point = (float(start[0]), float(start[1]))
        end_point = (float(end[0]), float(end[1]))
        edge_length = _distance(start_point, end_point)
        steps = max(1, int(math.ceil(edge_length / step_px)))
        dx = end_point[0] - start_point[0]
        dy = end_point[1] - start_point[1]
        if edge_length <= 1e-6:
            continue
        normals = [(-dy / edge_length, dx / edge_length), (dy / edge_length, -dx / edge_length)]
        for step_index in range(steps + 1):
            factor = step_index / steps
            edge_point = (
                start_point[0] + dx * factor,
                start_point[1] + dy * factor,
            )
            for normal in normals:
                candidate = (
                    edge_point[0] + normal[0] * inset_px,
                    edge_point[1] + normal[1] * inset_px,
                )
                if not _point_in_polygon(candidate, polygon):
                    continue
                if _distance(candidate, center) <= _distance(edge_point, center) + inset_px:
                    candidates.append(candidate)
    if room.get("center_x") is not None and room.get("center_y") is not None:
        center_point = (float(room["center_x"]), float(room["center_y"]))
        if _point_in_polygon(center_point, polygon):
            candidates.append(center_point)
    return _unique_layout_points(candidates)


def _unique_layout_points(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    unique: list[tuple[float, float]] = []
    seen: set[tuple[int, int]] = set()
    for point in points:
        key = (int(round(point[0] * 10.0)), int(round(point[1] * 10.0)))
        if key in seen:
            continue
        seen.add(key)
        unique.append((round(point[0], 3), round(point[1], 3)))
    return unique


def _covered_control_point_ids(
    candidate: dict[str, Any],
    control_points: list[dict[str, Any]],
    walls: list[dict[str, Any]],
    scale_factor: float,
) -> set[int]:
    covered_ids: set[int] = set()
    source = (float(candidate["x"]), float(candidate["y"]))
    source_room_id = candidate.get("room_id")
    sound_pressure_db = float(candidate.get("sound_pressure_db") or SIREN_DEFAULT_SOUND_PRESSURE_DB)
    for index, control in enumerate(control_points):
        target = control["point"]
        wall_crossings = count_wall_crossings_between_points(source, target, walls)
        same_room = source_room_id is not None and control.get("room_id") == source_room_id
        effective_crossings = wall_crossings if not same_room else max(0, wall_crossings - 1)
        spl = _sound_pressure_at_point(sound_pressure_db, source, target, scale_factor, effective_crossings)
        if MIN_SOUE_SOUND_DB <= spl <= MAX_SOUE_SOUND_DB:
            covered_ids.add(index)
    return covered_ids


def _sound_pressure_at_point(
    sound_pressure_db: float,
    start: tuple[float, float],
    end: tuple[float, float],
    scale_factor: float,
    wall_crossings: int,
) -> float:
    distance_m = max((_distance(start, end) * scale_factor / 1000.0), 0.3)
    attenuation_db = 20.0 * math.log10(distance_m)
    return sound_pressure_db - attenuation_db - (CONCRETE_WALL_LOSS_DB * max(0, wall_crossings))


def _nearest_wall_anchor(point: tuple[float, float], walls: list[dict[str, Any]]) -> tuple[float, float] | None:
    best_anchor = None
    best_distance = float("inf")
    for wall in walls:
        projection = _project_point_to_segment(
            point,
            (float(wall.get("x1") or 0.0), float(wall.get("y1") or 0.0)),
            (float(wall.get("x2") or 0.0), float(wall.get("y2") or 0.0)),
        )
        distance = _distance(point, projection)
        if distance < best_distance:
            best_distance = distance
            best_anchor = projection
    return best_anchor


def _project_point_to_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[float, float]:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-9:
        return start
    factor = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_sq
    factor = min(1.0, max(0.0, factor))
    return start[0] + dx * factor, start[1] + dy * factor


def _normalized_segment_parameter(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-9:
        return 0.0
    factor = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_sq
    return min(1.0, max(0.0, factor))


def _segment_intersection_point(
    a1: tuple[float, float],
    a2: tuple[float, float],
    b1: tuple[float, float],
    b2: tuple[float, float],
) -> tuple[float, float] | None:
    if not _segments_intersect(a1, a2, b1, b2):
        return None

    denominator = ((a1[0] - a2[0]) * (b1[1] - b2[1])) - ((a1[1] - a2[1]) * (b1[0] - b2[0]))
    if abs(denominator) <= 1e-9:
        return None

    determinant_a = (a1[0] * a2[1]) - (a1[1] * a2[0])
    determinant_b = (b1[0] * b2[1]) - (b1[1] * b2[0])
    x = ((determinant_a * (b1[0] - b2[0])) - ((a1[0] - a2[0]) * determinant_b)) / denominator
    y = ((determinant_a * (b1[1] - b2[1])) - ((a1[1] - a2[1]) * determinant_b)) / denominator
    return (x, y)


def _wall_crossing_events(
    polyline: list[tuple[float, float]],
    walls: list[dict[str, Any]],
) -> list[tuple[int, float]]:
    events: list[tuple[int, float]] = []

    for segment_index, (start, end) in enumerate(zip(polyline, polyline[1:])):
        for wall_index, wall in enumerate(walls):
            wall_id = int(wall.get("id") or wall_index + 1)
            wall_start = (float(wall.get("x1") or 0.0), float(wall.get("y1") or 0.0))
            wall_end = (float(wall.get("x2") or 0.0), float(wall.get("y2") or 0.0))
            intersection = _segment_intersection_point(start, end, wall_start, wall_end)
            if intersection is None:
                continue
            events.append((wall_id, _normalized_segment_parameter(intersection, wall_start, wall_end)))
    return events


def _wall_crossing_summary(
    polyline: list[tuple[float, float]],
    walls: list[dict[str, Any]],
) -> tuple[int, float]:
    events = _wall_crossing_events(polyline, walls)
    positions_by_wall: dict[int, list[float]] = defaultdict(list)
    for wall_id, position in events:
        positions_by_wall[wall_id].append(position)

    repeated_crossing_spread = 0.0
    for positions in positions_by_wall.values():
        if len(positions) < 2:
            continue
        repeated_crossing_spread += max(positions) - min(positions)

    return len(events), round(repeated_crossing_spread, 6)


def _build_polyline(
    *,
    start: tuple[float, float],
    targets: list[tuple[float, float]],
    walls: list[dict[str, Any]],
    close_ring: bool,
    trunk_anchor: tuple[float, float] | None,
) -> list[list[float]]:
    if close_ring and len(targets) == 1:
        return _build_single_target_ring(start, targets[0], walls)

    points: list[tuple[float, float]] = [start]
    current = start
    if trunk_anchor and _distance(start, trunk_anchor) > 1e-6:
        points.extend(_connector_points(start, trunk_anchor, walls, preferred_axis=None, existing_points=points))
        current = points[-1]
    for target in targets:
        points.extend(
            _connector_points(
                current,
                target,
                walls,
                preferred_axis=_last_segment_axis(points),
                existing_points=points,
            )
        )
        current = points[-1]
    if close_ring and targets:
        points.extend(
            _connector_points(
                current,
                start,
                walls,
                preferred_axis=_last_segment_axis(points),
                existing_points=points,
            )
        )
    return _dedupe_polyline(points)


def _connector_points(
    start: tuple[float, float],
    end: tuple[float, float],
    walls: list[dict[str, Any]],
    preferred_axis: str | None = None,
    existing_points: list[tuple[float, float]] | None = None,
) -> list[tuple[float, float]]:
    best = _choose_connector_variant(
        start,
        end,
        walls,
        preferred_axis=preferred_axis,
        existing_points=existing_points,
    )
    return best[1:]


def _alarm_point(alarm: dict[str, Any]) -> tuple[float, float]:
    return float(alarm.get("x") or 0.0), float(alarm.get("y") or 0.0)


def _choose_device_side_pair(
    center: tuple[float, float],
    prev_point: tuple[float, float],
    next_point: tuple[float, float] | None,
    walls: list[dict[str, Any]],
    obstacle_rects: list[tuple[float, float, float, float]],
    occupied_sides: dict[str, int],
) -> tuple[str, str | None]:
    incoming_dx = float(prev_point[0]) - float(center[0])
    incoming_dy = float(prev_point[1]) - float(center[1])
    entry_sides = _side_order_for_vector(incoming_dx, incoming_dy)
    exit_sides = (
        _side_order_for_vector(float(next_point[0]) - float(center[0]), float(next_point[1]) - float(center[1]))
        if next_point is not None
        else [None]
    )
    preferred_axis = _axis_between(prev_point, center)
    best_choice: tuple[tuple[Any, ...], str, str | None] | None = None

    for entry_index, entry_side in enumerate(entry_sides):
        entry_anchor = _device_side_anchor(center, entry_side)
        entry_variant = _choose_connector_variant(
            prev_point,
            entry_anchor,
            walls,
            preferred_axis=preferred_axis,
        )
        entry_score = _polyline_score(entry_variant, walls)
        entry_collisions = _polyline_rect_collision_count(entry_variant, obstacle_rects)

        for exit_index, exit_side in enumerate(exit_sides):
            same_side_penalty = 1 if next_point is not None and exit_side == entry_side else 0
            if next_point is None:
                exit_score = (0, 0.0, 0.0)
                exit_collisions = 0
            else:
                exit_anchor = _device_side_anchor(center, str(exit_side))
                exit_variant = _choose_connector_variant(
                    exit_anchor,
                    next_point,
                    walls,
                    preferred_axis=_axis_between(center, next_point),
                )
                exit_score = _polyline_score(exit_variant, walls)
                exit_collisions = _polyline_rect_collision_count(exit_variant, obstacle_rects)

            occupancy_penalty = occupied_sides.get(entry_side, 0) + (occupied_sides.get(str(exit_side), 0) if exit_side else 0)
            choice_score = (
                same_side_penalty,
                entry_collisions + exit_collisions,
                entry_score[0] + exit_score[0],
                round(entry_score[1] + exit_score[1], 6),
                round(entry_score[2] + exit_score[2], 6),
                occupancy_penalty,
                entry_index,
                exit_index,
            )
            if best_choice is None or choice_score < best_choice[0]:
                best_choice = (choice_score, entry_side, exit_side)

    return best_choice[1], best_choice[2]


def _choose_zc_terminal_side(
    center: tuple[float, float],
    incoming_point: tuple[float, float],
    walls: list[dict[str, Any]],
    obstacle_rects: list[tuple[float, float, float, float]],
    occupied_sides: dict[str, int],
    blocked_side: str | None = None,
) -> str:
    preferred_dx = float(center[0]) - float(incoming_point[0])
    preferred_dy = float(center[1]) - float(incoming_point[1])
    ordered_sides = _side_order_for_vector(preferred_dx, preferred_dy)
    if blocked_side in ordered_sides and len(ordered_sides) > 1:
        ordered_sides = [side for side in ordered_sides if side != blocked_side] + [blocked_side]

    best_choice: tuple[tuple[Any, ...], str] | None = None
    for side_index, side in enumerate(ordered_sides):
        zc_point = _zc_terminal_point(center, side)
        tail_polyline = [center, zc_point]
        tail_score = _polyline_score(tail_polyline, walls)
        tail_collisions = _polyline_rect_collision_count(tail_polyline, obstacle_rects)
        endpoint_collisions = sum(1 for rect in obstacle_rects if _segment_intersects_rect(zc_point, zc_point, rect))
        choice_score = (
            1 if side == blocked_side else 0,
            tail_collisions + endpoint_collisions,
            tail_score[0],
            round(tail_score[1], 6),
            round(tail_score[2], 6),
            occupied_sides.get(side, 0),
            side_index,
        )
        if best_choice is None or choice_score < best_choice[0]:
            best_choice = (choice_score, side)
    return best_choice[1] if best_choice is not None else "east"


def _build_device_route_polyline(
    *,
    start: tuple[float, float],
    devices: list[dict[str, Any]],
    walls: list[dict[str, Any]],
    close_ring: bool,
    append_zc: bool,
    all_device_rects: dict[tuple[Any, ...], tuple[float, float, float, float]],
    occupied_side_usage: dict[tuple[Any, ...], dict[str, int]] | None = None,
) -> list[list[float]]:
    if not devices:
        return _dedupe_polyline([start])

    occupied_lookup = occupied_side_usage if occupied_side_usage is not None else {}
    points: list[tuple[float, float]] = [_point_signature(start)]
    current = points[0]

    for index, device in enumerate(devices):
        center = _point_signature(_alarm_point(device))
        device_key = _alarm_identity(device, index + 1)
        side_usage = occupied_lookup.setdefault(device_key, {})
        obstacle_rects = [
            rect
            for key, rect in all_device_rects.items()
            if key != device_key
        ] + _polyline_obstacle_rects(points, padding=2.5)

        next_point = _point_signature(_alarm_point(devices[index + 1])) if index + 1 < len(devices) else (_point_signature(start) if close_ring else None)
        entry_side, exit_side = _choose_device_side_pair(
            center,
            current,
            next_point,
            walls,
            obstacle_rects,
            side_usage,
        )
        entry_anchor = _device_side_anchor(center, entry_side)
        points.extend(
            _connector_points(
                current,
                entry_anchor,
                walls,
                preferred_axis=_last_segment_axis(points),
                existing_points=points,
            )
        )
        points = _dedupe_tuple_polyline(points)
        if _distance(points[-1], center) > 1e-6:
            points.append(center)
        side_usage[entry_side] = side_usage.get(entry_side, 0) + 1

        if next_point is not None and exit_side is not None:
            exit_anchor = _device_side_anchor(center, exit_side)
            if _distance(points[-1], exit_anchor) > 1e-6:
                points.append(exit_anchor)
            side_usage[exit_side] = side_usage.get(exit_side, 0) + 1
            current = exit_anchor
            continue

        current = center
        if append_zc:
            zc_side = _choose_zc_terminal_side(
                center,
                entry_anchor,
                walls,
                obstacle_rects,
                side_usage,
                blocked_side=entry_side,
            )
            zc_point = _zc_terminal_point(center, zc_side)
            if _distance(points[-1], zc_point) > 1e-6:
                points.append(zc_point)
            side_usage[zc_side] = side_usage.get(zc_side, 0) + 1
            current = zc_point

    if close_ring:
        points.extend(
            _connector_points(
                current,
                _point_signature(start),
                walls,
                preferred_axis=_last_segment_axis(points),
                existing_points=points,
            )
        )
    return _dedupe_polyline(points)


def _device_sort_key(alarm: dict[str, Any]) -> tuple[Any, ...]:
    address = alarm.get("address")
    address_text = str(address or "").strip()
    if address_text.isdigit():
        address_key: tuple[int, Any] = (0, int(address_text))
    else:
        address_key = (1, address_text)
    return (
        int(alarm.get("loop_number") or 0),
        int(alarm.get("device_number") or 0),
        address_key,
        float(alarm.get("x") or 0.0),
        float(alarm.get("y") or 0.0),
        int(alarm.get("id") or 0),
    )


def _optimize_alarm_order(
    start: tuple[float, float],
    alarms: list[dict[str, Any]],
    walls: list[dict[str, Any]],
    *,
    close_ring: bool,
) -> list[dict[str, Any]]:
    if len(alarms) <= 1:
        return list(alarms)

    remaining = sorted(alarms, key=_device_sort_key)
    ordered: list[dict[str, Any]] = []
    current = start
    while remaining:
        next_alarm = min(
            remaining,
            key=lambda item: _best_connector_score(current, _alarm_point(item), walls) + (_device_sort_key(item),),
        )
        ordered.append(next_alarm)
        remaining.remove(next_alarm)
        current = _alarm_point(next_alarm)

    best = list(ordered)
    best_score = _ordered_alarm_score(start, best, walls, close_ring=close_ring)
    improved = True
    while improved and len(best) >= 3:
        improved = False
        for left in range(len(best) - 1):
            for right in range(left + 1, len(best)):
                candidate = best[:left] + list(reversed(best[left : right + 1])) + best[right + 1 :]
                candidate_score = _ordered_alarm_score(start, candidate, walls, close_ring=close_ring)
                if candidate_score < best_score:
                    best = candidate
                    best_score = candidate_score
                    improved = True
                    break
            if improved:
                break
    return best


def _ordered_alarm_score(
    start: tuple[float, float],
    alarms: list[dict[str, Any]],
    walls: list[dict[str, Any]],
    *,
    close_ring: bool,
) -> tuple[int, float, float]:
    polyline = _build_polyline(
        start=start,
        targets=[_alarm_point(alarm) for alarm in alarms],
        walls=walls,
        close_ring=close_ring,
        trunk_anchor=None,
    )
    return _polyline_score([(float(point[0]), float(point[1])) for point in polyline], walls)


def _best_connector_score(
    start: tuple[float, float],
    end: tuple[float, float],
    walls: list[dict[str, Any]],
) -> tuple[int, float, float]:
    return min((_polyline_score(candidate, walls) for candidate in _connector_variants(start, end)), default=(0, 0.0, 0.0))


def _connector_variants(
    start: tuple[float, float],
    end: tuple[float, float],
) -> list[list[tuple[float, float]]]:
    if _distance(start, end) <= 1e-6:
        return [[start]]
    candidates = [
        _dedupe_tuple_polyline([start, (end[0], start[1]), end]),
        _dedupe_tuple_polyline([start, (start[0], end[1]), end]),
    ]
    unique: list[list[tuple[float, float]]] = []
    seen: set[tuple[tuple[float, float], ...]] = set()
    for candidate in candidates:
        signature = tuple((round(point[0], 3), round(point[1], 3)) for point in candidate)
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(candidate)
    return unique or [[start, end]]


def _choose_connector_variant(
    start: tuple[float, float],
    end: tuple[float, float],
    walls: list[dict[str, Any]],
    *,
    preferred_axis: str | None,
    existing_points: list[tuple[float, float]] | None = None,
) -> list[tuple[float, float]]:
    variants = _connector_variants(start, end)
    ranked = sorted(
        variants,
        key=lambda candidate: (
            *(_polyline_score(
                (existing_points or []) + candidate[1:] if existing_points else candidate,
                walls,
            )),
            0 if preferred_axis is None or _first_segment_axis(candidate) == preferred_axis else 1,
            tuple((round(point[0], 3), round(point[1], 3)) for point in candidate),
        ),
    )
    return ranked[0]


def _build_single_target_ring(
    start: tuple[float, float],
    target: tuple[float, float],
    walls: list[dict[str, Any]],
) -> list[list[float]]:
    outgoing_variants = sorted(
        _connector_variants(start, target),
        key=lambda candidate: (
            _polyline_score(candidate, walls)[0],
            _polyline_score(candidate, walls)[1],
            tuple((round(point[0], 3), round(point[1], 3)) for point in candidate),
        ),
    )
    return_variants = sorted(
        _connector_variants(target, start),
        key=lambda candidate: (
            _polyline_score(candidate, walls)[0],
            _polyline_score(candidate, walls)[1],
            tuple((round(point[0], 3), round(point[1], 3)) for point in candidate),
        ),
    )

    for outgoing in outgoing_variants:
        outgoing_segments = _segment_signature_set(outgoing)
        for returning in return_variants:
            if outgoing_segments.intersection(_segment_signature_set(returning)):
                continue
            return _dedupe_polyline(outgoing + returning[1:])
    return _dedupe_polyline(_single_target_ring_detour(start, target, walls))


def _single_target_ring_detour(
    start: tuple[float, float],
    target: tuple[float, float],
    walls: list[dict[str, Any]],
) -> list[tuple[float, float]]:
    dx = target[0] - start[0]
    dy = target[1] - start[1]
    candidates: list[list[tuple[float, float]]] = []
    if abs(dx) <= 1e-6:
        for sign in (-1.0, 1.0):
            offset = sign * SINGLE_RING_DETOUR_PX
            candidates.append(
                [
                    start,
                    (start[0] + offset, start[1]),
                    (start[0] + offset, target[1]),
                    target,
                    (start[0] - offset, target[1]),
                    (start[0] - offset, start[1]),
                    start,
                ]
            )
    elif abs(dy) <= 1e-6:
        for sign in (-1.0, 1.0):
            offset = sign * SINGLE_RING_DETOUR_PX
            candidates.append(
                [
                    start,
                    (start[0], start[1] + offset),
                    (target[0], start[1] + offset),
                    target,
                    (target[0], start[1] - offset),
                    (start[0], start[1] - offset),
                    start,
                ]
            )
    else:
        candidates.append([start, (target[0], start[1]), target, (start[0], target[1]), start])
        candidates.append([start, (start[0], target[1]), target, (target[0], start[1]), start])

    best = min(candidates, key=lambda candidate: _polyline_score(candidate, walls))
    return _dedupe_tuple_polyline(best)


def _append_zc_terminal(polyline: list[list[float]], walls: list[dict[str, Any]]) -> list[list[float]]:
    if len(polyline) < 2:
        return polyline
    last = (float(polyline[-1][0]), float(polyline[-1][1]))
    previous = (float(polyline[-2][0]), float(polyline[-2][1]))
    terminal = _select_zc_terminal(last, previous, walls)
    return _dedupe_polyline([*[(float(point[0]), float(point[1])) for point in polyline], terminal])


def _select_zc_terminal(
    last_point: tuple[float, float],
    previous_point: tuple[float, float],
    walls: list[dict[str, Any]],
) -> tuple[float, float]:
    dx = last_point[0] - previous_point[0]
    dy = last_point[1] - previous_point[1]
    directions: list[tuple[float, float]]
    if abs(dx) > abs(dy) and abs(dx) > 1e-6:
        forward = (1.0 if dx > 0 else -1.0, 0.0)
        directions = [forward, (0.0, -1.0), (0.0, 1.0), (-forward[0], 0.0)]
    elif abs(dy) > 1e-6:
        forward = (0.0, 1.0 if dy > 0 else -1.0)
        directions = [forward, (-1.0, 0.0), (1.0, 0.0), (0.0, -forward[1])]
    else:
        directions = [(1.0, 0.0), (0.0, -1.0), (0.0, 1.0), (-1.0, 0.0)]

    candidates = [
        (
            last_point[0] + (direction[0] * ZC_ROUTE_OFFSET_PX),
            last_point[1] + (direction[1] * ZC_ROUTE_OFFSET_PX),
        )
        for direction in directions
    ]
    best = min(candidates, key=lambda candidate: _polyline_score([last_point, candidate], walls))
    return best


def _last_segment_axis(points: list[tuple[float, float]]) -> str | None:
    if len(points) < 2:
        return None
    return _axis_between(points[-2], points[-1])


def _first_segment_axis(polyline: list[tuple[float, float]]) -> str | None:
    if len(polyline) < 2:
        return None
    return _axis_between(polyline[0], polyline[1])


def _axis_between(start: tuple[float, float], end: tuple[float, float]) -> str | None:
    if abs(end[0] - start[0]) > abs(end[1] - start[1]):
        return "horizontal"
    if abs(end[1] - start[1]) > 1e-6:
        return "vertical"
    return None


def _segment_signature_set(polyline: list[tuple[float, float]]) -> set[tuple[tuple[float, float], tuple[float, float]]]:
    signatures: set[tuple[tuple[float, float], tuple[float, float]]] = set()
    for start, end in zip(polyline, polyline[1:]):
        normalized = tuple(sorted(((round(start[0], 3), round(start[1], 3)), (round(end[0], 3), round(end[1], 3)))))
        signatures.add(normalized)  # type: ignore[arg-type]
    return signatures


def _dedupe_tuple_polyline(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    deduped: list[tuple[float, float]] = []
    for point in points:
        normalized = (round(float(point[0]), 3), round(float(point[1]), 3))
        if deduped and deduped[-1] == normalized:
            continue
        deduped.append(normalized)
    return deduped


def _polyline_score(polyline: list[tuple[float, float]], walls: list[dict[str, Any]]) -> tuple[int, float, float]:
    crossings, repeated_crossing_spread = _wall_crossing_summary(polyline, walls)
    return (
        crossings,
        round(sum(_distance(start, end) for start, end in zip(polyline, polyline[1:])), 6),
        repeated_crossing_spread,
    )


def _count_wall_crossings(polyline: list[tuple[float, float]], walls: list[dict[str, Any]]) -> int:
    return _wall_crossing_summary(polyline, walls)[0]


def count_wall_crossings_between_points(
    start: tuple[float, float],
    end: tuple[float, float],
    walls: list[dict[str, Any]],
) -> int:
    return _count_wall_crossings([start, end], walls)


def _segments_intersect(
    a1: tuple[float, float],
    a2: tuple[float, float],
    b1: tuple[float, float],
    b2: tuple[float, float],
) -> bool:
    def orientation(p, q, r) -> float:
        return (q[1] - p[1]) * (r[0] - q[0]) - (q[0] - p[0]) * (r[1] - q[1])

    def on_segment(p, q, r) -> bool:
        return (
            min(p[0], r[0]) - 1e-6 <= q[0] <= max(p[0], r[0]) + 1e-6
            and min(p[1], r[1]) - 1e-6 <= q[1] <= max(p[1], r[1]) + 1e-6
        )

    o1 = orientation(a1, a2, b1)
    o2 = orientation(a1, a2, b2)
    o3 = orientation(b1, b2, a1)
    o4 = orientation(b1, b2, a2)

    if ((o1 > 0 > o2) or (o1 < 0 < o2)) and ((o3 > 0 > o4) or (o3 < 0 < o4)):
        return True
    if abs(o1) <= 1e-6 and on_segment(a1, b1, a2):
        return True
    if abs(o2) <= 1e-6 and on_segment(a1, b2, a2):
        return True
    if abs(o3) <= 1e-6 and on_segment(b1, a1, b2):
        return True
    if abs(o4) <= 1e-6 and on_segment(b1, a2, b2):
        return True
    return False


def _dedupe_polyline(points: list[tuple[float, float]]) -> list[list[float]]:
    deduped: list[list[float]] = []
    for point in points:
        normalized = [round(float(point[0]), 3), round(float(point[1]), 3)]
        if deduped and deduped[-1] == normalized:
            continue
        deduped.append(normalized)
    return deduped
