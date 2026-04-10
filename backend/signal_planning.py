"""Signal planning helpers for ZKSPC grouping and cable routing."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any


SYSTEM_TYPES = {"addressable", "non_addressable"}
MERGE_CAPABLE_INSTRUMENTS = {"control_panel", "loop_controller"}
DETECTOR_SYMBOL_HALF_SIZE_PX = 9.0
ZC_SYMBOL_HALF_SIZE_PX = 5.4
ZC_ROUTE_OFFSET_PX = DETECTOR_SYMBOL_HALF_SIZE_PX + ZC_SYMBOL_HALF_SIZE_PX
SINGLE_RING_DETOUR_PX = 18.0
ROUTE_KIND_ORDER = {
    "ring": 0,
    "zone_loop": 1,
    "manual_line": 2,
}


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

    if system == "addressable":
        if not normalized_alarms:
            return []
        ordered = _optimize_alarm_order((float(instrument["x"]), float(instrument["y"])), normalized_alarms, walls, close_ring=True)
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
        polyline = _build_polyline(
            start=(float(instrument["x"]), float(instrument["y"])),
            targets=[(float(item["x"]), float(item["y"])) for item in ordered],
            walls=walls,
            close_ring=close_ring,
            trunk_anchor=trunk_anchor,
        )
        if ordered:
            polyline = _append_zc_terminal(polyline, walls)
        routes.append(
            {
                "system_type": system,
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
