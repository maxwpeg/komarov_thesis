"""Fire alarm auto-placement helpers for smoke detectors and manual call points."""

from __future__ import annotations

import math
from typing import Any

from backend.fire_alarm_cover_solver import solve_room_detector_positions
from shapely.geometry import Point as ShapelyPoint
from shapely.geometry import Polygon
from shapely.ops import unary_union


Point = tuple[float, float]


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _safe_scale(scale_factor: float | None) -> float:
    return scale_factor if scale_factor and scale_factor > 0 else 1.0


def _point_on_segment(point: Point, start: Point, end: Point, tolerance: float = 1e-6) -> bool:
    px, py = point
    x1, y1 = start
    x2, y2 = end
    cross = abs((px - x1) * (y2 - y1) - (py - y1) * (x2 - x1))
    if cross > tolerance:
        return False
    dot = (px - x1) * (px - x2) + (py - y1) * (py - y2)
    return dot <= tolerance


def point_in_polygon(point: Point, polygon: list[list[float]]) -> bool:
    """Return True when the point is inside or on the polygon boundary."""
    if not polygon or len(polygon) < 3:
        return False

    x, y = point
    inside = False
    previous = polygon[-1]
    for current in polygon:
        x1, y1 = previous
        x2, y2 = current
        if _point_on_segment((x, y), (x1, y1), (x2, y2), tolerance=1e-4):
            return True
        intersects = ((y1 > y) != (y2 > y)) and (
            x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9) + x1
        )
        if intersects:
            inside = not inside
        previous = current
    return inside


def _bounding_box(points: list[list[float]]) -> tuple[float, float, float, float]:
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _room_center(room: dict[str, Any]) -> Point:
    if room.get("center_x") is not None and room.get("center_y") is not None:
        return float(room["center_x"]), float(room["center_y"])
    points = room.get("boundary_points") or []
    if not points:
        return 0.0, 0.0
    return (
        sum(float(point[0]) for point in points) / len(points),
        sum(float(point[1]) for point in points) / len(points),
    )


def _round_key(point: Point, precision: float = 0.01) -> tuple[int, int]:
    return (
        int(round(point[0] / precision)),
        int(round(point[1] / precision)),
    )


def _unique_points(points: list[Point]) -> list[Point]:
    unique: list[Point] = []
    seen: set[tuple[int, int]] = set()
    for point in points:
        key = _round_key(point)
        if key in seen:
            continue
        seen.add(key)
        unique.append(point)
    return unique


def _bbox_distance(point: Point, polygon: list[list[float]]) -> float:
    min_x, min_y, max_x, max_y = _bounding_box(polygon)
    clamped_x = min(max(point[0], min_x), max_x)
    clamped_y = min(max(point[1], min_y), max_y)
    return _distance(point, (clamped_x, clamped_y))


def locate_fire_alarm_metadata(
    x: float,
    y: float,
    rooms: list[dict[str, Any]],
    scale_factor: float,
) -> dict[str, float | int | None]:
    """Resolve room id and local meter offsets for a fire alarm position."""
    point = (float(x), float(y))
    matched_room: dict[str, Any] | None = None

    for room in rooms:
        polygon = room.get("boundary_points") or []
        if polygon and point_in_polygon(point, polygon):
            matched_room = room
            break

    if matched_room is None:
        max_fallback_distance = 1000.0 / _safe_scale(scale_factor)
        best_distance = float("inf")
        for room in rooms:
            polygon = room.get("boundary_points") or []
            if not polygon:
                continue
            distance = _bbox_distance(point, polygon)
            if distance < best_distance:
                best_distance = distance
                matched_room = room
        if best_distance > max_fallback_distance:
            matched_room = None

    if matched_room is None or not matched_room.get("boundary_points"):
        return {"room_id": None, "offset_left_m": None, "offset_top_m": None}

    min_x, min_y, _max_x, _max_y = _bounding_box(matched_room["boundary_points"])
    scale = _safe_scale(scale_factor)
    return {
        "room_id": matched_room.get("id"),
        "offset_left_m": max(0.0, (point[0] - min_x) * scale / 1000.0),
        "offset_top_m": max(0.0, (point[1] - min_y) * scale / 1000.0),
    }


def _find_containing_room(point: Point, rooms: list[dict[str, Any]]) -> dict[str, Any] | None:
    for room in rooms:
        polygon = room.get("boundary_points") or []
        if polygon and point_in_polygon(point, polygon):
            return room
    return None


def _is_serviceable_room(room: dict[str, Any] | None) -> bool:
    return bool(room) and room.get("room_type") != "необслуживаемое"


def _room_control_points(room: dict[str, Any], scale_factor: float) -> list[Point]:
    polygon = room.get("boundary_points") or []
    if len(polygon) < 3:
        return []

    step_px = max(6.0, 500.0 / _safe_scale(scale_factor))
    min_x, min_y, max_x, max_y = _bounding_box(polygon)
    points: list[Point] = []

    y = min_y
    while y <= max_y + 1e-6:
        x = min_x
        while x <= max_x + 1e-6:
            point = (x, y)
            if point_in_polygon(point, polygon):
                points.append(point)
            x += step_px
        y += step_px

    center_x, center_y = _room_center(room)
    points.extend(
        [
            (center_x, center_y),
            (min_x, min_y),
            (max_x, min_y),
            (max_x, max_y),
            (min_x, max_y),
            ((min_x + max_x) / 2.0, min_y),
            ((min_x + max_x) / 2.0, max_y),
            (min_x, (min_y + max_y) / 2.0),
            (max_x, (min_y + max_y) / 2.0),
        ]
    )

    for index in range(len(polygon)):
        start = polygon[index]
        end = polygon[(index + 1) % len(polygon)]
        points.append((float(start[0]), float(start[1])))
        points.append(((float(start[0]) + float(end[0])) / 2.0, (float(start[1]) + float(end[1])) / 2.0))

    filtered = [point for point in points if point_in_polygon(point, polygon)]
    return _unique_points(filtered)


def _small_room_pair(room: dict[str, Any], scale_factor: float) -> list[Point]:
    polygon = room.get("boundary_points") or []
    if len(polygon) < 3:
        center = _room_center(room)
        return [center, center]

    min_x, min_y, max_x, max_y = _bounding_box(polygon)
    center_x, center_y = _room_center(room)
    width = max_x - min_x
    height = max_y - min_y
    along_x = width >= height
    shift_px = max(4.0, min(max(width, height) / 4.0, 600.0 / _safe_scale(scale_factor)))

    for factor in (1.0, 0.6, 0.35, 0.2):
        delta = shift_px * factor
        if along_x:
            pair = [(center_x - delta, center_y), (center_x + delta, center_y)]
        else:
            pair = [(center_x, center_y - delta), (center_x, center_y + delta)]
        if all(point_in_polygon(point, polygon) for point in pair):
            return pair

    if point_in_polygon((center_x, center_y), polygon):
        return [(center_x, center_y), (center_x, center_y)]
    return [(min_x + width / 3.0, min_y + height / 2.0), (min_x + (2 * width) / 3.0, min_y + height / 2.0)]


def _room_candidate_points(room: dict[str, Any], scale_factor: float) -> list[Point]:
    polygon = room.get("boundary_points") or []
    if len(polygon) < 3:
        return []

    min_x, min_y, max_x, max_y = _bounding_box(polygon)
    center_x, center_y = _room_center(room)
    step_px = max(8.0, 1000.0 / _safe_scale(scale_factor))
    candidates: list[Point] = []

    for offset_x in (0.0, step_px / 2.0):
        for offset_y in (0.0, step_px / 2.0):
            y = min_y + offset_y
            while y <= max_y + 1e-6:
                x = min_x + offset_x
                while x <= max_x + 1e-6:
                    point = (x, y)
                    if point_in_polygon(point, polygon):
                        candidates.append(point)
                    x += step_px
                y += step_px

    candidates.extend(
        [
            (center_x, center_y),
            ((min_x + center_x) / 2.0, center_y),
            ((max_x + center_x) / 2.0, center_y),
            (center_x, (min_y + center_y) / 2.0),
            (center_x, (max_y + center_y) / 2.0),
        ]
    )
    candidates.extend(_small_room_pair(room, scale_factor))
    candidates.extend(_room_control_points(room, scale_factor))

    filtered = [point for point in candidates if point_in_polygon(point, polygon)]
    return _unique_points(filtered)


def _score_candidate(coverage: list[int], remaining_need: list[int]) -> tuple[int, int]:
    gain = sum(remaining_need[index] for index in coverage if remaining_need[index] > 0)
    return gain, len(coverage)


def _select_detector_positions(
    room: dict[str, Any],
    radius_px: float,
    scale_factor: float,
    coverage_need: int = 2,
) -> tuple[list[Point], list[str]]:
    control_points = _room_control_points(room, scale_factor)
    if not control_points:
        return [], [f"Помещение {room.get('id') or room.get('name') or 'без имени'} не имеет корректного контура."]

    candidate_points = _room_candidate_points(room, scale_factor)
    if not candidate_points:
        return [], [f"Для помещения {room.get('id') or room.get('name') or 'без имени'} не найдены позиции датчиков."]

    coverage_sets: list[list[int]] = []
    for candidate in candidate_points:
        covered = [
            index
            for index, control_point in enumerate(control_points)
            if _distance(candidate, control_point) <= radius_px + 1e-6
        ]
        if covered:
            coverage_sets.append(covered)
        else:
            coverage_sets.append([])

    required_coverage = max(1, int(coverage_need))
    remaining_need = [required_coverage for _ in control_points]
    selected_indices: list[int] = []
    selected_set: set[int] = set()
    warnings: list[str] = []

    while any(need > 0 for need in remaining_need):
        best_index = None
        best_score = (0, 0)
        for index, coverage in enumerate(coverage_sets):
            if index in selected_set or not coverage:
                continue
            score = _score_candidate(coverage, remaining_need)
            if score > best_score:
                best_index = index
                best_score = score

        if best_index is None or best_score[0] <= 0:
            warnings.append(
                f"Не удалось гарантировать двукратное покрытие для помещения {room.get('id') or room.get('name') or 'без имени'}."
            )
            break

        selected_indices.append(best_index)
        selected_set.add(best_index)
        for covered_index in coverage_sets[best_index]:
            if remaining_need[covered_index] > 0:
                remaining_need[covered_index] -= 1

    if selected_indices:
        coverage_count = [0 for _ in control_points]
        for index in selected_indices:
            for covered_index in coverage_sets[index]:
                coverage_count[covered_index] += 1

        for position in range(len(selected_indices) - 1, -1, -1):
            candidate_index = selected_indices[position]
            coverage = coverage_sets[candidate_index]
            if coverage and all(coverage_count[covered_index] - 1 >= required_coverage for covered_index in coverage):
                for covered_index in coverage:
                    coverage_count[covered_index] -= 1
                selected_indices.pop(position)

    selected_points = [candidate_points[index] for index in selected_indices]
    if len(selected_points) < 2:
        for extra_point in _small_room_pair(room, scale_factor):
            selected_points.append(extra_point)
            if len(selected_points) >= 2:
                break
        selected_points = _unique_points(selected_points)
        while len(selected_points) < 2:
            selected_points.append(_room_center(room))

    return selected_points, warnings


def _door_rotation_deg(door: dict[str, Any], walls_by_id: dict[int, dict[str, Any]]) -> float:
    if door.get("rotation_deg") is not None:
        return float(door["rotation_deg"])
    wall_id = door.get("wall_id")
    if wall_id is not None and wall_id in walls_by_id:
        wall = walls_by_id[wall_id]
        return math.degrees(math.atan2(float(wall["y2"]) - float(wall["y1"]), float(wall["x2"]) - float(wall["x1"])))
    return 0.0 if float(door.get("width", 0.0)) >= float(door.get("height", 0.0)) else 90.0


def _distance_to_rect(point: Point, rect: tuple[float, float, float, float]) -> float:
    min_x, min_y, max_x, max_y = rect
    clamped_x = min(max(point[0], min_x), max_x)
    clamped_y = min(max(point[1], min_y), max_y)
    return _distance(point, (clamped_x, clamped_y))


def _expand_rect(rect: tuple[float, float, float, float], margin: float) -> tuple[float, float, float, float]:
    min_x, min_y, max_x, max_y = rect
    return min_x - margin, min_y - margin, max_x + margin, max_y + margin


def _room_polygon_pixels(room: dict[str, Any]) -> Polygon | None:
    points = room.get("boundary_points") or []
    if len(points) < 3:
        return None
    polygon = Polygon([(float(point[0]), float(point[1])) for point in points])
    if polygon.is_empty:
        return None
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    if polygon.is_empty or not isinstance(polygon, Polygon):
        return None
    return polygon


def _detector_coverage_satisfied(
    room_polygon: Polygon,
    positions: list[Point],
    radius_px: float,
    multiplicity: int,
) -> bool:
    if room_polygon.is_empty or not positions:
        return False

    disks = [
        ShapelyPoint(float(point[0]), float(point[1])).buffer(radius_px, quad_segs=32).intersection(room_polygon)
        for point in positions
    ]
    if multiplicity <= 1:
        covered = unary_union(disks)
    else:
        covered_once = Polygon()
        covered_twice = Polygon()
        for disk in disks:
            if covered_once.is_empty:
                covered_once = disk
                continue
            overlap = covered_once.intersection(disk)
            covered_twice = overlap if covered_twice.is_empty else unary_union([covered_twice, overlap])
            covered_once = unary_union([covered_once, disk])
        covered = covered_twice
    uncovered = room_polygon.difference(covered)
    return uncovered.area <= 1e-3


def _detector_symbol_spacing_px(scale_factor: float) -> float:
    scale = _safe_scale(scale_factor)
    return max(20.0, 220.0 / scale)


def _refine_detector_positions_for_drawing(
    room: dict[str, Any],
    positions: list[Point],
    *,
    radius_px: float,
    scale_factor: float,
    coverage_need: int,
) -> tuple[list[Point], bool]:
    if len(positions) < 2:
        return positions, False

    room_polygon = _room_polygon_pixels(room)
    if room_polygon is None:
        return positions, False

    min_spacing = _detector_symbol_spacing_px(scale_factor)
    center = _room_center(room)
    refined = [(float(point[0]), float(point[1])) for point in positions]
    moved = False

    for _ in range(24):
        updated = False
        for left_index in range(len(refined) - 1):
            for right_index in range(left_index + 1, len(refined)):
                left = refined[left_index]
                right = refined[right_index]
                dx = right[0] - left[0]
                dy = right[1] - left[1]
                distance = math.hypot(dx, dy)
                if distance >= min_spacing - 1e-6:
                    continue

                if distance <= 1e-6:
                    dx = right[0] - center[0]
                    dy = right[1] - center[1]
                    if abs(dx) <= 1e-6 and abs(dy) <= 1e-6:
                        dx = 1.0
                        dy = 0.0
                    distance = math.hypot(dx, dy)

                shift = (min_spacing - distance) / 2.0 + 0.25
                direction = (dx / distance, dy / distance)
                candidates = [
                    (
                        (left[0] - direction[0] * shift, left[1] - direction[1] * shift),
                        (right[0] + direction[0] * shift, right[1] + direction[1] * shift),
                    ),
                    (
                        (left[0] - direction[0] * shift * 2.0, left[1] - direction[1] * shift * 2.0),
                        right,
                    ),
                    (
                        left,
                        (right[0] + direction[0] * shift * 2.0, right[1] + direction[1] * shift * 2.0),
                    ),
                ]

                accepted = None
                for next_left, next_right in candidates:
                    if not room_polygon.covers(ShapelyPoint(next_left)) or not room_polygon.covers(ShapelyPoint(next_right)):
                        continue
                    trial = refined[:]
                    trial[left_index] = next_left
                    trial[right_index] = next_right
                    if _detector_coverage_satisfied(room_polygon, trial, radius_px, coverage_need):
                        accepted = trial
                        break

                if accepted is None:
                    continue

                refined = accepted
                updated = True
                moved = True
                break
            if updated:
                break
        if not updated:
            break

    has_overlap = any(
        _distance(refined[left_index], refined[right_index]) < min_spacing - 1e-6
        for left_index in range(len(refined) - 1)
        for right_index in range(left_index + 1, len(refined))
    )
    return refined, has_overlap


def _wall_axis_data(wall: dict[str, Any]) -> tuple[Point, Point, Point, float] | None:
    x1 = float(wall.get("x1") or 0.0)
    y1 = float(wall.get("y1") or 0.0)
    x2 = float(wall.get("x2") or 0.0)
    y2 = float(wall.get("y2") or 0.0)
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length <= 1e-6:
        return None
    axis = (dx / length, dy / length)
    normal = (-axis[1], axis[0])
    return (x1, y1), axis, normal, length


def _opening_half_span_along_axis(
    opening: dict[str, Any],
    axis: Point,
) -> float:
    half_width = float(opening.get("width") or 0.0) / 2.0
    half_height = float(opening.get("height") or 0.0) / 2.0
    return abs(axis[0]) * half_width + abs(axis[1]) * half_height


def _opening_projection_interval(
    opening: dict[str, Any],
    wall_origin: Point,
    axis: Point,
) -> tuple[float, float]:
    center_x = float(opening["x"]) + float(opening.get("width", 0.0)) / 2.0
    center_y = float(opening["y"]) + float(opening.get("height", 0.0)) / 2.0
    projection = ((center_x - wall_origin[0]) * axis[0]) + ((center_y - wall_origin[1]) * axis[1])
    half_span = _opening_half_span_along_axis(opening, axis)
    return projection - half_span, projection + half_span


class FireAlarmPlacement:
    """Auto-place smoke detectors and manual call points."""

    DEFAULT_SMOKE_DETECTOR_RADIUS = 4500.0
    DEFAULT_SMOKE_DETECTOR_MOUNTING_HEIGHT = 3000.0
    DEFAULT_MANUAL_CALL_POINT_OFFSET = 300.0
    DEFAULT_MANUAL_CALL_POINT_HEIGHT = 1400.0

    def __init__(
        self,
        smoke_detector_radius: float | None = None,
        ceiling_height: float | None = None,
        system_type: str = "non_addressable",
    ) -> None:
        self.smoke_detector_radius = float(smoke_detector_radius or self.DEFAULT_SMOKE_DETECTOR_RADIUS)
        self.ceiling_height = float(ceiling_height or self.DEFAULT_SMOKE_DETECTOR_MOUNTING_HEIGHT)
        self.system_type = system_type if system_type in {"addressable", "non_addressable"} else "non_addressable"

    def calculate_room_devices(
        self,
        room: dict[str, Any],
        scale_factor: float = 1.0,
        room_type: str = "general",
    ) -> tuple[list[dict[str, Any]], list[str]]:
        if room_type == "необслуживаемое":
            return [], []
        if not room.get("boundary_points") or len(room["boundary_points"]) < 3:
            return [], [f"Помещение {room.get('id') or room.get('name') or 'без имени'} пропущено: нет полигона."]

        detector_positions, warnings = solve_room_detector_positions(
            room,
            smoke_detector_radius_mm=self.smoke_detector_radius,
            scale_factor=scale_factor,
            coverage_need=1 if self.system_type == "addressable" else 2,
        )
        radius_px = self.smoke_detector_radius / _safe_scale(scale_factor)
        refined_positions, has_overlap = _refine_detector_positions_for_drawing(
            room,
            detector_positions,
            radius_px=radius_px,
            scale_factor=scale_factor,
            coverage_need=1 if self.system_type == "addressable" else 2,
        )
        if has_overlap:
            warnings.append(
                f"Detector layout for room {room.get('id') or room.get('name') or 'unknown'} still contains drawing overlaps after refinement."
            )
        devices = []
        for x, y in refined_positions:
            devices.append(
                {
                    "device_type": "smoke_detector",
                    "x": float(x),
                    "y": float(y),
                    "coverage_radius": self.smoke_detector_radius,
                    "mounting_height": self.ceiling_height,
                }
            )
        return devices, warnings

    def calculate_manual_call_points(
        self,
        doors: list[dict[str, Any]],
        stairs: list[dict[str, Any]],
        rooms: list[dict[str, Any]],
        walls: list[dict[str, Any]],
        scale_factor: float = 1.0,
    ) -> list[dict[str, Any]]:
        devices: list[dict[str, Any]] = []
        if not doors:
            return devices

        walls_by_id = {int(wall["id"]): wall for wall in walls if wall.get("id") is not None}
        openings_by_wall: dict[int, list[dict[str, Any]]] = {}
        for door in doors:
            wall_id = door.get("wall_id")
            if wall_id is None:
                continue
            openings_by_wall.setdefault(int(wall_id), []).append(door)
        scale = _safe_scale(scale_factor)
        sample_offset_px = max(6.0, 750.0 / scale)
        placement_offset_px = max(4.0, self.DEFAULT_MANUAL_CALL_POINT_OFFSET / scale)
        stair_margin_px = max(8.0, 600.0 / scale)
        tangent_clearance_px = max(8.0, 180.0 / scale)

        stair_rects = [
            _expand_rect(
                (
                    float(stair["x"]),
                    float(stair["y"]),
                    float(stair["x"]) + float(stair["width"]),
                    float(stair["y"]) + float(stair["height"]),
                ),
                stair_margin_px,
            )
            for stair in stairs
        ]

        for door in doors:
            center_x = float(door["x"]) + float(door.get("width", 0.0)) / 2.0
            center_y = float(door["y"]) + float(door.get("height", 0.0)) / 2.0
            angle_rad = math.radians(_door_rotation_deg(door, walls_by_id))
            normal = (-math.sin(angle_rad), math.cos(angle_rad))

            positive_sample = (
                center_x + normal[0] * sample_offset_px,
                center_y + normal[1] * sample_offset_px,
            )
            negative_sample = (
                center_x - normal[0] * sample_offset_px,
                center_y - normal[1] * sample_offset_px,
            )

            positive_room = _find_containing_room(positive_sample, rooms)
            negative_room = _find_containing_room(negative_sample, rooms)
            positive_inside = _is_serviceable_room(positive_room)
            negative_inside = _is_serviceable_room(negative_room)

            is_external = positive_inside != negative_inside

            near_stair = False
            desired_sign = 0.0
            if stair_rects:
                positive_stair_distance = min(_distance_to_rect(positive_sample, rect) for rect in stair_rects)
                negative_stair_distance = min(_distance_to_rect(negative_sample, rect) for rect in stair_rects)
                near_stair = min(positive_stair_distance, negative_stair_distance) <= stair_margin_px
                if near_stair:
                    if positive_inside != negative_inside:
                        desired_sign = 1.0 if positive_inside else -1.0
                    elif positive_inside:
                        desired_sign = 1.0 if positive_stair_distance >= negative_stair_distance else -1.0

            if not near_stair and is_external:
                desired_sign = 1.0 if positive_inside else -1.0

            if desired_sign == 0.0:
                continue

            wall = walls_by_id.get(int(door["wall_id"])) if door.get("wall_id") is not None else None
            if wall is None:
                continue
            wall_axis = _wall_axis_data(wall)
            if wall_axis is None:
                continue
            origin, axis, _wall_normal, wall_length = wall_axis
            door_start, door_end = _opening_projection_interval(door, origin, axis)
            door_start = max(0.0, door_start)
            door_end = min(wall_length, door_end)

            left_limit = 0.0
            right_limit = wall_length
            for other in openings_by_wall.get(int(wall["id"]), []):
                if other.get("id") == door.get("id"):
                    continue
                other_start, other_end = _opening_projection_interval(other, origin, axis)
                if other_end <= door_start and other_end > left_limit:
                    left_limit = other_end
                if other_start >= door_end and other_start < right_limit:
                    right_limit = other_start

            available_left = max(0.0, door_start - left_limit)
            available_right = max(0.0, right_limit - door_end)
            side_order = [1.0, -1.0] if available_right >= available_left else [-1.0, 1.0]

            half_span = _opening_half_span_along_axis(door, axis)
            placed_point = None
            for tangent_sign in side_order:
                available_span = available_right if tangent_sign > 0 else available_left
                if available_span <= tangent_clearance_px + 1e-6:
                    continue
                shift_along_wall = half_span + min(
                    available_span - 2.0,
                    max(tangent_clearance_px, half_span + tangent_clearance_px * 0.35),
                )
                projection = ((center_x - origin[0]) * axis[0]) + ((center_y - origin[1]) * axis[1])
                projected = max(0.0, min(wall_length, projection + (tangent_sign * shift_along_wall)))
                candidate = (
                    origin[0] + (axis[0] * projected) + (normal[0] * placement_offset_px * desired_sign),
                    origin[1] + (axis[1] * projected) + (normal[1] * placement_offset_px * desired_sign),
                )
                placed_point = candidate
                break

            if placed_point is None:
                continue

            devices.append(
                {
                    "device_type": "manual_call_point",
                    "x": placed_point[0],
                    "y": placed_point[1],
                    "coverage_radius": None,
                    "mounting_height": self.DEFAULT_MANUAL_CALL_POINT_HEIGHT,
                }
            )

        return devices

    def generate_complete_system(
        self,
        floor_plan_data: dict[str, Any],
        scale_factor: float = 1.0,
        *,
        zkspc_zones: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        rooms = floor_plan_data.get("rooms", []) or []
        doors = floor_plan_data.get("doors", []) or []
        stairs = floor_plan_data.get("stairs", []) or []
        walls = floor_plan_data.get("walls", []) or []

        detectors: list[dict[str, Any]] = []
        warnings: list[str] = []
        for room in rooms:
            room_devices, room_warnings = self.calculate_room_devices(
                room,
                scale_factor,
                room.get("room_type", "general"),
            )
            detectors.extend(room_devices)
            warnings.extend(room_warnings)

        manual_call_points = self.calculate_manual_call_points(
            doors=doors,
            stairs=stairs,
            rooms=rooms,
            walls=walls,
            scale_factor=scale_factor,
        )

        all_devices = detectors + manual_call_points
        room_to_zone: dict[int, dict[str, int | None]] = {}
        for zone in (zkspc_zones or floor_plan_data.get("zkspc_zones") or []):
            zone_id = zone.get("id") or zone.get("zone_number")
            zone_number = int(zone.get("zone_number") or zone_id or 1)
            for room_id in zone.get("room_ids") or []:
                room_to_zone[int(room_id)] = {
                    "id": int(zone_id) if zone_id is not None else None,
                    "zone_number": zone_number,
                }
        for device in all_devices:
            metadata = locate_fire_alarm_metadata(
                device["x"],
                device["y"],
                rooms,
                scale_factor,
            )
            device.update(metadata)
            room_id = metadata.get("room_id")
            zone_info = room_to_zone.get(int(room_id)) if room_id is not None and int(room_id) in room_to_zone else None
            device["system_type"] = self.system_type
            device["zkspc_zone_id"] = zone_info["id"] if zone_info else None
            device["loop_kind"] = "ring" if self.system_type == "addressable" else "zone_loop"
            device["loop_number"] = zone_info["zone_number"] if zone_info else 1
            device["device_number"] = None
            device["zone"] = str(zone_info["zone_number"] if zone_info else 1)
            device["address"] = None

        smoke_by_zone: dict[int, list[dict[str, Any]]] = {}
        for detector in detectors:
            zone_key = int(detector.get("loop_number") or detector.get("zkspc_zone_id") or 1)
            smoke_by_zone.setdefault(zone_key, []).append(detector)

        warnings.extend(self._apply_branch_metadata(detectors, manual_call_points, smoke_by_zone))

        return {
            "detectors": detectors,
            "manual_call_points": manual_call_points,
            "all_devices": all_devices,
            "summary": {
                "total_devices": len(all_devices),
                "smoke_detectors": len(detectors),
                "manual_call_points": len(manual_call_points),
                "system_type": self.system_type,
                "loops": len(smoke_by_zone) if self.system_type == "non_addressable" else (1 if all_devices else 0),
            },
            "warnings": warnings,
        }

    def _apply_branch_metadata(
        self,
        detectors: list[dict[str, Any]],
        manual_call_points: list[dict[str, Any]],
        smoke_by_zone: dict[int, list[dict[str, Any]]],
    ) -> list[str]:
        warnings: list[str] = []
        if self.system_type == "addressable":
            sequence = detectors + manual_call_points
            for index, device in enumerate(sequence, start=1):
                device["loop_kind"] = "ring"
                device["loop_number"] = 1
                device["device_number"] = index
                device["address"] = str(index)
            for zone_number, zone_devices in smoke_by_zone.items():
                if len(zone_devices) > 32:
                    warnings.append(
                        f"Полное покрытие требует {len(zone_devices)} датчиков в ЗКСПС {zone_number}, "
                        "что превышает лимит 32 для адресной системы."
                    )
            return warnings

        for zone_number, zone_devices in smoke_by_zone.items():
            ordered = sorted(zone_devices, key=lambda item: (float(item["x"]), float(item["y"])))
            for index, device in enumerate(ordered, start=1):
                device["loop_kind"] = "zone_loop"
                device["loop_number"] = zone_number
                device["device_number"] = index
                device["address"] = str(index)
            if len(zone_devices) > 20:
                warnings.append(
                    f"Полное покрытие требует {len(zone_devices)} датчиков в ЗКСПС {zone_number}, "
                    "что превышает лимит 20 для безадресной системы."
                )

        manual_loop_start = (max(smoke_by_zone) if smoke_by_zone else 0) + 1
        for index, device in enumerate(sorted(manual_call_points, key=lambda item: (float(item["x"]), float(item["y"]))), start=1):
            device["loop_kind"] = "manual_line"
            device["loop_number"] = manual_loop_start + index - 1
            device["device_number"] = 1
            device["address"] = "1"
        return warnings


def calculate_fire_alarm_layout(
    floor_plan_data: dict[str, Any],
    scale_factor: float = 1.0,
    system_type: str = "non_addressable",
    zkspc_zones: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    placement = FireAlarmPlacement(
        ceiling_height=floor_plan_data.get("ceiling_height_mm"),
        system_type=system_type,
    )
    return placement.generate_complete_system(floor_plan_data, scale_factor, zkspc_zones=zkspc_zones)
