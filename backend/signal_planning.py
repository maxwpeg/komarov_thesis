"""Signal planning helpers for ZKSPC grouping and cable routing."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


SYSTEM_TYPES = {"addressable", "non_addressable"}
MERGE_CAPABLE_INSTRUMENTS = {"control_panel", "loop_controller"}


def _safe_scale(scale_factor: float | None) -> float:
    return float(scale_factor) if scale_factor and scale_factor > 0 else 1.0


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


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
    trunk_anchor = _nearest_wall_anchor((float(instrument["x"]), float(instrument["y"])), walls) if use_shared_trunk else None

    if system == "addressable":
        if not alarms:
            return []
        ordered = sorted(
            alarms,
            key=lambda item: (
                int(item.get("loop_number") or 1),
                int(item.get("device_number") or 0),
                float(item.get("x") or 0.0),
                float(item.get("y") or 0.0),
            ),
        )
        polyline = _build_polyline(
            start=(float(instrument["x"]), float(instrument["y"])),
            targets=[(float(item["x"]), float(item["y"])) for item in ordered],
            walls=walls,
            close_ring=True,
            trunk_anchor=trunk_anchor,
        )
        return [
            {
                "system_type": system,
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
    for alarm in alarms:
        if alarm.get("device_type") == "manual_call_point":
            route_number = int(alarm.get("loop_number") or len(grouped) + 1)
            grouped[("manual_line", route_number)].append(alarm)
            continue
        route_number = int(alarm.get("loop_number") or alarm.get("zkspc_zone_id") or 1)
        grouped[("zone_loop", route_number)].append(alarm)

    routes: list[dict[str, Any]] = []
    for index, ((route_kind, route_number), group_alarms) in enumerate(sorted(grouped.items(), key=lambda item: (item[0][0], item[0][1]))):
        ordered = sorted(
            group_alarms,
            key=lambda item: (
                int(item.get("device_number") or 0),
                float(item.get("x") or 0.0),
                float(item.get("y") or 0.0),
            ),
        )
        close_ring = False
        polyline = _build_polyline(
            start=(float(instrument["x"]), float(instrument["y"])),
            targets=[(float(item["x"]), float(item["y"])) for item in ordered],
            walls=walls,
            close_ring=close_ring,
            trunk_anchor=trunk_anchor,
        )
        routes.append(
            {
                "system_type": system,
                "instrument_id": instrument["id"],
                "route_kind": route_kind,
                "route_number": route_number if route_number > 0 else index + 1,
                "polyline_points": polyline,
                "device_ids": [int(item["id"]) for item in ordered if item.get("id") is not None],
                "warnings": [],
                "length_m": route_length_m(polyline, scale_factor),
                "is_manual": False,
            }
        )
    return routes


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


def _build_polyline(
    *,
    start: tuple[float, float],
    targets: list[tuple[float, float]],
    walls: list[dict[str, Any]],
    close_ring: bool,
    trunk_anchor: tuple[float, float] | None,
) -> list[list[float]]:
    points: list[tuple[float, float]] = [start]
    current = start
    if trunk_anchor and _distance(start, trunk_anchor) > 1e-6:
        points.extend(_connector_points(start, trunk_anchor, walls))
        current = points[-1]
    for target in targets:
        points.extend(_connector_points(current, target, walls))
        current = points[-1]
    if close_ring and targets:
        points.extend(_connector_points(current, start, walls))
    return _dedupe_polyline(points)


def _connector_points(
    start: tuple[float, float],
    end: tuple[float, float],
    walls: list[dict[str, Any]],
) -> list[tuple[float, float]]:
    if _distance(start, end) <= 1e-6:
        return [end]
    horizontal_first = [start, (end[0], start[1]), end]
    vertical_first = [start, (start[0], end[1]), end]
    best = horizontal_first
    best_score = _polyline_score(horizontal_first, walls)
    alt_score = _polyline_score(vertical_first, walls)
    if alt_score < best_score:
        best = vertical_first
    return best[1:]


def _polyline_score(polyline: list[tuple[float, float]], walls: list[dict[str, Any]]) -> tuple[int, float]:
    return (
        _count_wall_crossings(polyline, walls),
        sum(_distance(start, end) for start, end in zip(polyline, polyline[1:])),
    )


def _count_wall_crossings(polyline: list[tuple[float, float]], walls: list[dict[str, Any]]) -> int:
    count = 0
    for start, end in zip(polyline, polyline[1:]):
        for wall in walls:
            wall_start = (float(wall.get("x1") or 0.0), float(wall.get("y1") or 0.0))
            wall_end = (float(wall.get("x2") or 0.0), float(wall.get("y2") or 0.0))
            if _segments_intersect(start, end, wall_start, wall_end):
                count += 1
    return count


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
