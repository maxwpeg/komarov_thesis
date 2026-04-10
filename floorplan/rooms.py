"""Room detection based on closed wall boundaries."""

from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np

from .floorplan_types import Room, Wall
from .geometry import wall_boundary_lines


class RoomConfig:
    """Configuration for room extraction."""

    CLOSE_KERNEL = 9
    CLOSE_ITERS = 2
    MIN_ROOM_AREA = 1500
    APPROX_POLY_EPSILON_RATIO = 0.01
    SORT_BUCKET_Y = 40
    GAP_BRIDGE_THRESHOLD_RATIO = 1.5
    GAP_BRIDGE_DIRECTION_DOT = 0.35
    PARALLEL_SEAM_DIRECTION_DOT = 0.94
    PARALLEL_SEAM_MAX_OFFSET_RATIO = 1.25
    PARALLEL_SEAM_AXIS_GAP_RATIO = 1.5
    PARALLEL_SEAM_PROJECTION_MARGIN_RATIO = 0.5
    OUTSIDE_PADDING_RATIO = 2.0
    OUTSIDE_MIN_PADDING = 24


def _wall_polygon(wall: Wall) -> np.ndarray:
    line_a, line_b = wall_boundary_lines(wall)
    return np.array(
        [
            [line_a.x1, line_a.y1],
            [line_a.x2, line_a.y2],
            [line_b.x2, line_b.y2],
            [line_b.x1, line_b.y1],
        ],
        dtype=np.float32,
    )


def _wall_direction(wall: Wall) -> tuple[np.ndarray, float]:
    dx = float(wall.midline.x2 - wall.midline.x1)
    dy = float(wall.midline.y2 - wall.midline.y1)
    length = float(np.hypot(dx, dy))
    if length < 1e-6:
        return np.array([1.0, 0.0], dtype=np.float32), 0.0
    return np.array([dx / length, dy / length], dtype=np.float32), length


def _wall_normal(direction: np.ndarray) -> np.ndarray:
    return np.array([-direction[1], direction[0]], dtype=np.float32)


def _segment_midpoint(start: np.ndarray, end: np.ndarray) -> np.ndarray:
    return (start + end) * 0.5


def _project_point_to_axis(point: np.ndarray, origin: np.ndarray, direction: np.ndarray) -> float:
    return float(np.dot(point - origin, direction))


def _interval_gap(value: float, interval_start: float, interval_end: float) -> float:
    if value < interval_start:
        return interval_start - value
    if value > interval_end:
        return value - interval_end
    return 0.0


def _segment_nearest_point(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> tuple[tuple[float, float], float]:
    px, py = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return (x1, y1), float(np.hypot(px - x1, py - y1))
    projection = ((px - x1) * dx + (py - y1) * dy) / ((dx * dx) + (dy * dy))
    t = float(np.clip(projection, 0.0, 1.0))
    nearest = (x1 + (dx * t), y1 + (dy * t))
    return nearest, float(np.hypot(px - nearest[0], py - nearest[1]))


def _point_in_polygon(point: tuple[float, float], polygon: np.ndarray) -> bool:
    contour = np.round(polygon).astype(np.int32).reshape((-1, 1, 2))
    return cv2.pointPolygonTest(contour, point, False) >= 0


def _wall_long_edges(polygon: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    return [
        (polygon[0].astype(np.float32), polygon[1].astype(np.float32)),
        (polygon[3].astype(np.float32), polygon[2].astype(np.float32)),
    ]


def _wall_short_edges(polygon: np.ndarray) -> list[tuple[np.ndarray, np.ndarray]]:
    return [
        (polygon[3].astype(np.float32), polygon[0].astype(np.float32)),
        (polygon[1].astype(np.float32), polygon[2].astype(np.float32)),
    ]


def _find_parallel_seam_connector(
    short_edge: tuple[np.ndarray, np.ndarray],
    wall: Wall,
    wall_direction: np.ndarray,
    other_wall: Wall,
    other_polygon: np.ndarray,
    other_direction: np.ndarray,
) -> np.ndarray | None:
    direction_dot = abs(float(np.dot(wall_direction, other_direction)))
    if direction_dot < RoomConfig.PARALLEL_SEAM_DIRECTION_DOT:
        return None

    short_start, short_end = short_edge
    midpoint = _segment_midpoint(short_start, short_end)
    if _point_in_polygon((float(midpoint[0]), float(midpoint[1])), other_polygon):
        return None

    wall_origin = np.array([wall.midline.x1, wall.midline.y1], dtype=np.float32)
    other_origin = np.array([other_wall.midline.x1, other_wall.midline.y1], dtype=np.float32)
    _, other_length = _wall_direction(other_wall)
    if other_length < 1e-6:
        return None

    base_thickness = max(float(wall.thickness_px), float(other_wall.thickness_px), 4.0)
    max_offset = base_thickness * RoomConfig.PARALLEL_SEAM_MAX_OFFSET_RATIO
    max_axis_gap = base_thickness * RoomConfig.PARALLEL_SEAM_AXIS_GAP_RATIO
    projection_margin = base_thickness * RoomConfig.PARALLEL_SEAM_PROJECTION_MARGIN_RATIO

    t_on_other = _project_point_to_axis(midpoint, other_origin, other_direction)
    axis_gap_to_other = _interval_gap(t_on_other, -projection_margin, other_length + projection_margin)
    if axis_gap_to_other > max_axis_gap:
        return None

    long_edges = _wall_long_edges(other_polygon)
    wall_normal = _wall_normal(wall_direction)
    best_connector: np.ndarray | None = None
    best_score: tuple[float, float] | None = None

    for long_start, long_end in long_edges:
        nearest_midpoint, distance = _segment_nearest_point(
            (float(midpoint[0]), float(midpoint[1])),
            (float(long_start[0]), float(long_start[1])),
            (float(long_end[0]), float(long_end[1])),
        )
        if distance <= 1e-6:
            continue

        gap_vector = np.array(
            [nearest_midpoint[0] - float(midpoint[0]), nearest_midpoint[1] - float(midpoint[1])],
            dtype=np.float32,
        )
        lateral_offset = abs(float(np.dot(gap_vector, wall_normal)))
        axis_offset = abs(float(np.dot(gap_vector, wall_direction)))
        if lateral_offset <= 1e-6 or lateral_offset > max_offset or axis_offset > max_axis_gap:
            continue

        projected_short = [
            _segment_nearest_point(
                (float(point[0]), float(point[1])),
                (float(long_start[0]), float(long_start[1])),
                (float(long_end[0]), float(long_end[1])),
            )[0]
            for point in (short_start, short_end)
        ]
        connector = np.array(
            [
                short_start,
                short_end,
                np.array(projected_short[1], dtype=np.float32),
                np.array(projected_short[0], dtype=np.float32),
            ],
            dtype=np.float32,
        )

        connector_area = abs(float(cv2.contourArea(np.round(connector).astype(np.int32))))
        if connector_area < 1.0:
            continue

        connector_midpoint = _segment_midpoint(connector[2], connector[3])
        axis_gap_to_wall = _interval_gap(
            _project_point_to_axis(connector_midpoint, wall_origin, wall_direction),
            -projection_margin,
            float(np.hypot(wall.midline.x2 - wall.midline.x1, wall.midline.y2 - wall.midline.y1)) + projection_margin,
        )
        if axis_gap_to_wall > max_axis_gap:
            continue

        score = (lateral_offset, axis_offset)
        if best_score is None or score < best_score:
            best_score = score
            best_connector = connector

    return best_connector


def _bridge_parallel_wall_seams(mask: np.ndarray, walls: List[Wall]) -> None:
    wall_data = []
    for wall in walls:
        polygon = _wall_polygon(wall)
        direction, length = _wall_direction(wall)
        if length < 1e-6:
            continue
        wall_data.append(
            {
                "wall": wall,
                "polygon": polygon,
                "direction": direction,
                "short_edges": _wall_short_edges(polygon),
            }
        )

    for index, current in enumerate(wall_data):
        current_wall = current["wall"]
        current_polygon = current["polygon"]
        current_direction = current["direction"]
        current_short_edges = current["short_edges"]

        for other in wall_data[index + 1 :]:
            other_wall = other["wall"]
            other_polygon = other["polygon"]
            other_direction = other["direction"]
            other_short_edges = other["short_edges"]

            connectors = [
                _find_parallel_seam_connector(
                    short_edge,
                    current_wall,
                    current_direction,
                    other_wall,
                    other_polygon,
                    other_direction,
                )
                for short_edge in current_short_edges
            ]
            connectors.extend(
                _find_parallel_seam_connector(
                    short_edge,
                    other_wall,
                    other_direction,
                    current_wall,
                    current_polygon,
                    current_direction,
                )
                for short_edge in other_short_edges
            )

            for connector in connectors:
                if connector is None:
                    continue
                cv2.fillConvexPoly(mask, np.round(connector).astype(np.int32), 255)


def _endpoint_bridge_target(
    wall: Wall,
    endpoint: tuple[float, float],
    axis_direction: tuple[float, float],
    walls: List[Wall],
) -> tuple[tuple[float, float], float] | None:
    best_target: tuple[tuple[float, float], float] | None = None
    current_threshold = max(4.0, wall.thickness_px * RoomConfig.GAP_BRIDGE_THRESHOLD_RATIO)

    for other_wall in walls:
        if other_wall.id == wall.id:
            continue
        polygon = _wall_polygon(other_wall)
        if _point_in_polygon(endpoint, polygon):
            continue

        other_threshold = max(current_threshold, other_wall.thickness_px * RoomConfig.GAP_BRIDGE_THRESHOLD_RATIO)
        candidate_threshold = max(current_threshold, other_threshold)
        edges = [
            (tuple(polygon[index]), tuple(polygon[(index + 1) % len(polygon)]))
            for index in range(len(polygon))
        ]
        for start, end in edges:
            nearest_point, distance = _segment_nearest_point(endpoint, start, end)
            if distance <= 1e-6 or distance > candidate_threshold:
                continue
            gap_dx = nearest_point[0] - endpoint[0]
            gap_dy = nearest_point[1] - endpoint[1]
            gap_length = float(np.hypot(gap_dx, gap_dy))
            if gap_length <= 1e-6:
                continue
            alignment = abs(((gap_dx / gap_length) * axis_direction[0]) + ((gap_dy / gap_length) * axis_direction[1]))
            if alignment < RoomConfig.GAP_BRIDGE_DIRECTION_DOT:
                continue
            if best_target is None or distance < best_target[1]:
                best_target = (nearest_point, distance)

    return best_target


def _bridge_small_wall_gaps(mask: np.ndarray, walls: List[Wall]) -> None:
    for wall in walls:
        dx = float(wall.midline.x2 - wall.midline.x1)
        dy = float(wall.midline.y2 - wall.midline.y1)
        length = float(np.hypot(dx, dy))
        if length < 1e-6:
            continue
        ux = dx / length
        uy = dy / length
        endpoints = [
            ((float(wall.midline.x1), float(wall.midline.y1)), (-ux, -uy)),
            ((float(wall.midline.x2), float(wall.midline.y2)), (ux, uy)),
        ]
        for endpoint, axis_direction in endpoints:
            target = _endpoint_bridge_target(wall, endpoint, axis_direction, walls)
            if target is None:
                continue
            nearest_point, _distance = target
            thickness = int(round(max(2.0, wall.thickness_px)))
            cv2.line(
                mask,
                (int(round(endpoint[0])), int(round(endpoint[1]))),
                (int(round(nearest_point[0])), int(round(nearest_point[1]))),
                255,
                thickness=thickness,
            )


def _crop_to_wall_bounds(mask: np.ndarray, walls: List[Wall]) -> tuple[np.ndarray, tuple[int, int]]:
    if not walls:
        return mask, (0, 0)

    polygons = [_wall_polygon(wall) for wall in walls]
    all_points = np.vstack(polygons)
    max_thickness = max((float(max(4.0, wall.thickness_px)) for wall in walls), default=4.0)
    padding = int(round(max(RoomConfig.OUTSIDE_MIN_PADDING, max_thickness * RoomConfig.OUTSIDE_PADDING_RATIO)))

    min_x = max(0, int(np.floor(np.min(all_points[:, 0])) - padding))
    min_y = max(0, int(np.floor(np.min(all_points[:, 1])) - padding))
    max_x = min(mask.shape[1], int(np.ceil(np.max(all_points[:, 0])) + padding + 1))
    max_y = min(mask.shape[0], int(np.ceil(np.max(all_points[:, 1])) + padding + 1))
    return mask[min_y:max_y, min_x:max_x].copy(), (min_x, min_y)


def _build_wall_mask(binary_img: np.ndarray, walls: List[Wall]) -> np.ndarray:
    height, width = binary_img.shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)

    for wall in walls:
        polygon = np.round(_wall_polygon(wall)).astype(np.int32)
        thickness = int(round(max(4.0, wall.thickness_px)))
        cv2.fillConvexPoly(mask, polygon, 255)
        radius = max(2, thickness // 2)
        cv2.circle(mask, (int(round(wall.midline.x1)), int(round(wall.midline.y1))), radius, 255, -1)
        cv2.circle(mask, (int(round(wall.midline.x2)), int(round(wall.midline.y2))), radius, 255, -1)

    _bridge_parallel_wall_seams(mask, walls)
    _bridge_small_wall_gaps(mask, walls)

    kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT,
        (RoomConfig.CLOSE_KERNEL, RoomConfig.CLOSE_KERNEL),
    )
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=RoomConfig.CLOSE_ITERS)
    return mask


def _mark_outside(background_mask: np.ndarray) -> np.ndarray:
    """
    Flood-fill from border pixels to mark outside area.
    """
    filled = background_mask.copy()
    h, w = filled.shape
    ff_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)

    border_points: list[Tuple[int, int]] = []
    for x in range(w):
        border_points.append((x, 0))
        border_points.append((x, h - 1))
    for y in range(h):
        border_points.append((0, y))
        border_points.append((w - 1, y))

    for x, y in border_points:
        if filled[y, x] > 0:
            cv2.floodFill(filled, ff_mask, (x, y), 127)

    return (filled == 127).astype(np.uint8) * 255


def _contour_to_polygon(contour: np.ndarray) -> list[list[float]]:
    epsilon = RoomConfig.APPROX_POLY_EPSILON_RATIO * cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, epsilon, True)
    if len(approx) < 3:
        approx = contour
    return [[float(pt[0][0]), float(pt[0][1])] for pt in approx]


def detect_rooms(binary_img: np.ndarray, walls: List[Wall]) -> List[Room]:
    """
    Detect closed room regions bounded by walls.
    """
    if binary_img is None or binary_img.size == 0 or not walls:
        return []

    wall_mask = _build_wall_mask(binary_img, walls)
    wall_mask, (offset_x, offset_y) = _crop_to_wall_bounds(wall_mask, walls)
    free_space = cv2.bitwise_not(wall_mask)
    outside_mask = _mark_outside(free_space)
    inside_mask = cv2.bitwise_and(free_space, cv2.bitwise_not(outside_mask))

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(inside_mask, connectivity=8)

    detected: list[tuple[float, float, list[list[float]], float]] = []

    for label_id in range(1, num_labels):
        area = float(stats[label_id, cv2.CC_STAT_AREA])
        if area < RoomConfig.MIN_ROOM_AREA:
            continue

        x = stats[label_id, cv2.CC_STAT_LEFT]
        y = stats[label_id, cv2.CC_STAT_TOP]
        w = stats[label_id, cv2.CC_STAT_WIDTH]
        h = stats[label_id, cv2.CC_STAT_HEIGHT]
        if x == 0 or y == 0 or (x + w) >= inside_mask.shape[1] or (y + h) >= inside_mask.shape[0]:
            continue

        component = np.zeros_like(inside_mask)
        component[labels == label_id] = 255

        contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            continue

        contour = max(contours, key=cv2.contourArea)
        contour_area = float(cv2.contourArea(contour))
        if contour_area < RoomConfig.MIN_ROOM_AREA:
            continue

        moments = cv2.moments(contour)
        if moments["m00"] == 0:
            cx = float(offset_x + x + (w / 2.0))
            cy = float(offset_y + y + (h / 2.0))
        else:
            cx = float(offset_x + (moments["m10"] / moments["m00"]))
            cy = float(offset_y + (moments["m01"] / moments["m00"]))

        polygon = _contour_to_polygon(contour)
        if len(polygon) < 3:
            continue
        polygon = [[point[0] + offset_x, point[1] + offset_y] for point in polygon]

        detected.append((cx, cy, polygon, contour_area))

    detected.sort(key=lambda item: (int(item[1] // RoomConfig.SORT_BUCKET_Y), item[0]))

    rooms: List[Room] = []
    for idx, (cx, cy, polygon, area) in enumerate(detected, start=1):
        room_number = str(idx)
        rooms.append(
            Room(
                id=idx,
                room_number=room_number,
                name=f"Помещение {room_number}",
                boundary_points=polygon,
                center=(cx, cy),
                area_px=area,
                confidence=0.85,
                metadata={"source": "wall-closure"},
            )
        )

    return rooms
