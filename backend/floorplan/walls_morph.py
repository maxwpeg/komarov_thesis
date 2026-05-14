from __future__ import annotations

import cv2
import numpy as np
from typing import List, Tuple
from .floorplan_types import LineSegment, Wall


class MorphWallConfig:
    # fill/connect wall regions
    CLOSE_KERNEL = 7
    DILATE_KERNEL = 3
    DILATE_ITERS = 1

    # orientation extraction
    H_KERNEL_LEN = 35
    V_KERNEL_LEN = 35

    # component filtering
    MIN_COMPONENT_AREA = 80
    MIN_WALL_LENGTH = 40
    MIN_WALL_THICKNESS = 4
    MAX_WALL_THICKNESS = 80

    # merge tolerance
    MERGE_GAP = 20
    MERGE_OFFSET = 12


def ensure_foreground_white(binary: np.ndarray) -> np.ndarray:
    """
    Ensure walls/lines are white (255) on black background.
    """
    img = binary.copy()
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    if np.mean(img) > 127:
        img = cv2.bitwise_not(img)

    return img


def preprocess_wall_mask(binary: np.ndarray) -> np.ndarray:
    """
    Strengthen wall regions so they become solid blobs, not just thin contours.
    """
    img = ensure_foreground_white(binary)

    close_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (MorphWallConfig.CLOSE_KERNEL, MorphWallConfig.CLOSE_KERNEL)
    )
    img = cv2.morphologyEx(img, cv2.MORPH_CLOSE, close_kernel, iterations=2)

    dil_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (MorphWallConfig.DILATE_KERNEL, MorphWallConfig.DILATE_KERNEL)
    )
    img = cv2.dilate(img, dil_kernel, iterations=MorphWallConfig.DILATE_ITERS)

    return img


def extract_horizontal_vertical_masks(mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """
    Extract horizontal and vertical wall candidates separately.
    """
    h_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (MorphWallConfig.H_KERNEL_LEN, 3)
    )
    v_kernel = cv2.getStructuringElement(
        cv2.MORPH_RECT, (3, MorphWallConfig.V_KERNEL_LEN)
    )

    horizontal = cv2.morphologyEx(mask, cv2.MORPH_OPEN, h_kernel, iterations=1)
    vertical = cv2.morphologyEx(mask, cv2.MORPH_OPEN, v_kernel, iterations=1)

    return horizontal, vertical


def component_to_wall(
    labels: np.ndarray,
    stats: np.ndarray,
    label_id: int,
    orientation: str,
    dist_map: np.ndarray,
    wall_id: int
) -> Wall | None:
    """
    Convert a connected component into a Wall.
    """
    x = stats[label_id, cv2.CC_STAT_LEFT]
    y = stats[label_id, cv2.CC_STAT_TOP]
    w = stats[label_id, cv2.CC_STAT_WIDTH]
    h = stats[label_id, cv2.CC_STAT_HEIGHT]
    area = stats[label_id, cv2.CC_STAT_AREA]

    if area < MorphWallConfig.MIN_COMPONENT_AREA:
        return None

    if orientation == "horizontal":
        length = w
        thickness = h
        if length < MorphWallConfig.MIN_WALL_LENGTH:
            return None
        if not (MorphWallConfig.MIN_WALL_THICKNESS <= thickness <= MorphWallConfig.MAX_WALL_THICKNESS):
            return None

        y_mid = y + h / 2.0
        line = LineSegment(
            x1=float(x),
            y1=float(y_mid),
            x2=float(x + w),
            y2=float(y_mid),
            length=float(length),
            angle=0.0,
        )
        angle_deg = 0.0

    else:
        length = h
        thickness = w
        if length < MorphWallConfig.MIN_WALL_LENGTH:
            return None
        if not (MorphWallConfig.MIN_WALL_THICKNESS <= thickness <= MorphWallConfig.MAX_WALL_THICKNESS):
            return None

        x_mid = x + w / 2.0
        line = LineSegment(
            x1=float(x_mid),
            y1=float(y),
            x2=float(x_mid),
            y2=float(y + h),
            length=float(length),
            angle=90.0,
        )
        angle_deg = 90.0

    # better thickness estimate from distance transform inside component
    comp_mask = (labels == label_id).astype(np.uint8)
    comp_dist = dist_map * comp_mask
    max_radius = float(comp_dist.max())
    if max_radius > 0:
        thickness = max(thickness, 2.0 * max_radius)

    return Wall(
        id=wall_id,
        midline=line,
        thickness_px=float(thickness),
        angle_deg=float(angle_deg),
        confidence=0.9,
    )


def detect_component_walls(mask: np.ndarray, orientation: str, start_id: int) -> List[Wall]:
    """
    Detect walls from connected components in horizontal or vertical mask.
    """
    dist_map = cv2.distanceTransform(mask, cv2.DIST_L2, 5)

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)

    walls: List[Wall] = []
    wall_id = start_id

    for label_id in range(1, num_labels):
        wall = component_to_wall(labels, stats, label_id, orientation, dist_map, wall_id)
        if wall is not None:
            walls.append(wall)
            wall_id += 1

    return walls


def can_merge_walls(w1: Wall, w2: Wall) -> bool:
    """
    Merge nearby collinear walls split into pieces.
    """
    if abs(w1.angle_deg - w2.angle_deg) > 1e-3:
        return False

    if w1.angle_deg == 0.0:
        # horizontal
        y1 = (w1.midline.y1 + w1.midline.y2) / 2.0
        y2 = (w2.midline.y1 + w2.midline.y2) / 2.0
        if abs(y1 - y2) > MorphWallConfig.MERGE_OFFSET:
            return False

        a1, a2 = sorted([w1.midline.x1, w1.midline.x2])
        b1, b2 = sorted([w2.midline.x1, w2.midline.x2])

        gap = max(0.0, max(a1, b1) - min(a2, b2))
        return gap <= MorphWallConfig.MERGE_GAP

    else:
        # vertical
        x1 = (w1.midline.x1 + w1.midline.x2) / 2.0
        x2 = (w2.midline.x1 + w2.midline.x2) / 2.0
        if abs(x1 - x2) > MorphWallConfig.MERGE_OFFSET:
            return False

        a1, a2 = sorted([w1.midline.y1, w1.midline.y2])
        b1, b2 = sorted([w2.midline.y1, w2.midline.y2])

        gap = max(0.0, max(a1, b1) - min(a2, b2))
        return gap <= MorphWallConfig.MERGE_GAP


def merge_two_walls(w1: Wall, w2: Wall, new_id: int) -> Wall:
    """
    Merge two horizontal or two vertical walls.
    """
    if w1.angle_deg == 0.0:
        y = np.mean([w1.midline.y1, w1.midline.y2, w2.midline.y1, w2.midline.y2])
        xs = [w1.midline.x1, w1.midline.x2, w2.midline.x1, w2.midline.x2]
        x1, x2 = min(xs), max(xs)
        line = LineSegment(
            x1=float(x1), y1=float(y),
            x2=float(x2), y2=float(y),
            length=float(abs(x2 - x1)),
            angle=0.0,
        )
        angle_deg = 0.0
    else:
        x = np.mean([w1.midline.x1, w1.midline.x2, w2.midline.x1, w2.midline.x2])
        ys = [w1.midline.y1, w1.midline.y2, w2.midline.y1, w2.midline.y2]
        y1, y2 = min(ys), max(ys)
        line = LineSegment(
            x1=float(x), y1=float(y1),
            x2=float(x), y2=float(y2),
            length=float(abs(y2 - y1)),
            angle=90.0,
        )
        angle_deg = 90.0

    thickness = float(max(w1.thickness_px, w2.thickness_px))

    return Wall(
        id=new_id,
        midline=line,
        thickness_px=thickness,
        angle_deg=angle_deg,
        confidence=max(w1.confidence, w2.confidence),
    )


def merge_walls(walls: List[Wall]) -> List[Wall]:
    """
    Merge fragmented walls.
    """
    if not walls:
        return []

    changed = True
    current = walls[:]

    while changed:
        changed = False
        used = [False] * len(current)
        merged: List[Wall] = []
        next_id = 1

        for i in range(len(current)):
            if used[i]:
                continue

            base = current[i]
            used[i] = True

            merged_any = True
            while merged_any:
                merged_any = False
                for j in range(len(current)):
                    if used[j]:
                        continue
                    if can_merge_walls(base, current[j]):
                        base = merge_two_walls(base, current[j], new_id=next_id)
                        used[j] = True
                        merged_any = True
                        changed = True

            base.id = next_id
            merged.append(base)
            next_id += 1

        current = merged

    # reindex cleanly
    for idx, wall in enumerate(current, start=1):
        wall.id = idx

    return current


def detect_walls(binary_img: np.ndarray) -> List[Wall]:
    """
    Full morphology-based wall detection pipeline.
    """
    wall_mask = preprocess_wall_mask(binary_img)

    horizontal_mask, vertical_mask = extract_horizontal_vertical_masks(wall_mask)

    walls_h = detect_component_walls(horizontal_mask, "horizontal", start_id=1)
    walls_v = detect_component_walls(vertical_mask, "vertical", start_id=1 + len(walls_h))

    walls = walls_h + walls_v
    walls = merge_walls(walls)

    return walls