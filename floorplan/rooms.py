"""Room detection based on closed wall boundaries."""

from __future__ import annotations

from typing import List, Tuple

import cv2
import numpy as np

from .floorplan_types import Room, Wall


class RoomConfig:
    """Configuration for room extraction."""

    CLOSE_KERNEL = 9
    CLOSE_ITERS = 2
    MIN_ROOM_AREA = 1500
    APPROX_POLY_EPSILON_RATIO = 0.01
    SORT_BUCKET_Y = 40


def _build_wall_mask(binary_img: np.ndarray, walls: List[Wall]) -> np.ndarray:
    height, width = binary_img.shape[:2]
    mask = np.zeros((height, width), dtype=np.uint8)

    for wall in walls:
        x1 = int(round(wall.midline.x1))
        y1 = int(round(wall.midline.y1))
        x2 = int(round(wall.midline.x2))
        y2 = int(round(wall.midline.y2))
        thickness = int(round(max(4.0, wall.thickness_px)))

        cv2.line(mask, (x1, y1), (x2, y2), 255, thickness=thickness)
        # Endpoint circles reduce accidental gaps at T-junctions.
        radius = max(2, thickness // 2)
        cv2.circle(mask, (x1, y1), radius, 255, -1)
        cv2.circle(mask, (x2, y2), radius, 255, -1)

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
            cx = float(x + w / 2.0)
            cy = float(y + h / 2.0)
        else:
            cx = float(moments["m10"] / moments["m00"])
            cy = float(moments["m01"] / moments["m00"])

        polygon = _contour_to_polygon(contour)
        if len(polygon) < 3:
            continue

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

