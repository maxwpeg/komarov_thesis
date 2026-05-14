"""Wall detection: detect wall segments and pair parallel lines into walls."""

from __future__ import annotations

import cv2
import numpy as np
from typing import List, Optional, Tuple
from .floorplan_types import LineSegment, Wall


class WallConfig:
    """Configuration for wall detection."""

    # Hough line detection: make these much stricter for noisy phone photos
    HOUGH_THRESHOLD = 80
    HOUGH_MIN_LENGTH = 80
    HOUGH_MAX_GAP = 5

    # Merge tolerances
    ANGLE_TOLERANCE = 7.0          # degrees
    COLINEAR_DISTANCE = 12.0       # px
    ENDPOINT_GAP = 25.0            # px

    # Wall pairing tolerances
    MIN_WALL_THICKNESS = 6.0       # px
    MAX_WALL_THICKNESS = 60.0      # px
    MIN_OVERLAP_RATIO = 0.35       # overlap / min(len1, len2)
    MIN_OVERLAP_ABS = 30.0         # px

    # Orientation filter for architectural plans
    ORTHOGONAL_TOL = 7.0           # keep only near 0/90/180 degrees

    # Confidence
    BASE_CONFIDENCE = 0.75


def normalize_angle(angle_deg: float) -> float:
    """Normalize angle to [0, 180)."""
    angle = angle_deg % 180.0
    if angle < 0:
        angle += 180.0
    return angle


def angle_diff(a: float, b: float) -> float:
    """Smallest absolute difference between two angles in [0,180)."""
    d = abs(normalize_angle(a) - normalize_angle(b))
    return min(d, 180.0 - d)


def is_orthogonal_angle(angle_deg: float, tol: float) -> bool:
    """Keep only near-horizontal or near-vertical lines."""
    a = normalize_angle(angle_deg)
    return (
        a < tol
        or abs(a - 90.0) < tol
        or abs(a - 180.0) < tol
    )


def segment_direction(seg: LineSegment) -> np.ndarray:
    """Unit direction vector along segment."""
    dx = seg.x2 - seg.x1
    dy = seg.y2 - seg.y1
    length = np.hypot(dx, dy)
    if length < 1e-6:
        return np.array([1.0, 0.0], dtype=float)
    return np.array([dx / length, dy / length], dtype=float)


def segment_normal(seg: LineSegment) -> np.ndarray:
    """Unit normal vector to segment."""
    d = segment_direction(seg)
    return np.array([-d[1], d[0]], dtype=float)


def point_to_line_distance(point: np.ndarray, seg: LineSegment) -> float:
    """Perpendicular distance from point to infinite line through segment."""
    p = np.array([point[0], point[1]], dtype=float)
    a = np.array([seg.x1, seg.y1], dtype=float)
    n = segment_normal(seg)
    return abs(np.dot(p - a, n))


def segment_midpoint(seg: LineSegment) -> np.ndarray:
    return np.array([(seg.x1 + seg.x2) / 2.0, (seg.y1 + seg.y2) / 2.0], dtype=float)


def project_segment_to_axis(
    seg: LineSegment,
    origin: np.ndarray,
    axis_dir: np.ndarray
) -> Tuple[float, float]:
    """Project segment endpoints onto a given axis."""
    p1 = np.array([seg.x1, seg.y1], dtype=float)
    p2 = np.array([seg.x2, seg.y2], dtype=float)
    t1 = float(np.dot(p1 - origin, axis_dir))
    t2 = float(np.dot(p2 - origin, axis_dir))
    return (min(t1, t2), max(t1, t2))


def overlap_1d(a1: float, a2: float, b1: float, b2: float) -> float:
    """Length of overlap between intervals [a1,a2] and [b1,b2]."""
    return max(0.0, min(a2, b2) - max(a1, b1))


def endpoints_close(seg1: LineSegment, seg2: LineSegment, max_gap: float) -> bool:
    """Check if any pair of endpoints is close."""
    pts1 = [
        np.array([seg1.x1, seg1.y1], dtype=float),
        np.array([seg1.x2, seg1.y2], dtype=float),
    ]
    pts2 = [
        np.array([seg2.x1, seg2.y1], dtype=float),
        np.array([seg2.x2, seg2.y2], dtype=float),
    ]
    for p1 in pts1:
        for p2 in pts2:
            if np.linalg.norm(p1 - p2) <= max_gap:
                return True
    return False


def can_merge_colinear(seg1: LineSegment, seg2: LineSegment) -> bool:
    """Check if two segments are approximately colinear and close enough to merge."""
    if angle_diff(seg1.angle, seg2.angle) > WallConfig.ANGLE_TOLERANCE:
        return False

    # Distance from each midpoint to the other's infinite line
    mid1 = segment_midpoint(seg1)
    mid2 = segment_midpoint(seg2)

    d1 = point_to_line_distance(mid1, seg2)
    d2 = point_to_line_distance(mid2, seg1)
    if max(d1, d2) > WallConfig.COLINEAR_DISTANCE:
        return False

    # Check projected gap/overlap along common direction
    axis_dir = segment_direction(seg1)
    origin = np.array([seg1.x1, seg1.y1], dtype=float)

    s1a, s1b = project_segment_to_axis(seg1, origin, axis_dir)
    s2a, s2b = project_segment_to_axis(seg2, origin, axis_dir)

    ov = overlap_1d(s1a, s1b, s2a, s2b)
    gap = max(0.0, max(s1a, s2a) - min(s1b, s2b))

    return ov > 0 or gap <= WallConfig.ENDPOINT_GAP or endpoints_close(seg1, seg2, WallConfig.ENDPOINT_GAP)


def merge_two_segments(seg1: LineSegment, seg2: LineSegment) -> LineSegment:
    """Merge two approximately colinear segments into one longer segment."""
    axis_dir = segment_direction(seg1)
    origin = np.array([seg1.x1, seg1.y1], dtype=float)

    points = np.array(
        [
            [seg1.x1, seg1.y1],
            [seg1.x2, seg1.y2],
            [seg2.x1, seg2.y1],
            [seg2.x2, seg2.y2],
        ],
        dtype=float,
    )

    ts = [float(np.dot(p - origin, axis_dir)) for p in points]
    t_min = min(ts)
    t_max = max(ts)

    # Estimate average normal offset to stabilize against noise
    n = np.array([-axis_dir[1], axis_dir[0]], dtype=float)
    offsets = [float(np.dot(p - origin, n)) for p in points]
    mean_offset = float(np.mean(offsets))

    p_start = origin + t_min * axis_dir + mean_offset * n
    p_end = origin + t_max * axis_dir + mean_offset * n

    length = float(np.linalg.norm(p_end - p_start))
    angle = normalize_angle(np.degrees(np.arctan2(p_end[1] - p_start[1], p_end[0] - p_start[0])))

    return LineSegment(
        x1=float(p_start[0]),
        y1=float(p_start[1]),
        x2=float(p_end[0]),
        y2=float(p_end[1]),
        length=length,
        angle=angle,
    )


def merge_colinear_segments(segments: List[LineSegment]) -> List[LineSegment]:
    """
    Merge approximately colinear segments.
    Repeats until convergence because one-pass neighbor merge is unstable on noisy data.
    """
    if not segments:
        return []

    merged = segments[:]
    changed = True

    while changed:
        changed = False
        used = [False] * len(merged)
        new_segments: List[LineSegment] = []

        for i in range(len(merged)):
            if used[i]:
                continue

            current = merged[i]
            used[i] = True

            merged_any = True
            while merged_any:
                merged_any = False
                for j in range(len(merged)):
                    if used[j]:
                        continue
                    if can_merge_colinear(current, merged[j]):
                        current = merge_two_segments(current, merged[j])
                        used[j] = True
                        merged_any = True
                        changed = True

            new_segments.append(current)

        merged = new_segments

    return merged


def detect_wall_segments(binary_img: np.ndarray) -> List[LineSegment]:
    """
    Detect candidate wall line segments using Hough transform.
    Expects binary image with foreground lines as white on black.
    """
    if binary_img is None or binary_img.size == 0:
        return []

    # Ensure 8-bit single channel
    img = binary_img
    if len(img.shape) == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # If background is white and lines are black, invert.
    # Heuristic: if mean is high, likely white background.
    if float(np.mean(img)) > 127:
        img = cv2.bitwise_not(img)

    # Mild cleanup to reduce isolated noise
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    cleaned = cv2.morphologyEx(img, cv2.MORPH_OPEN, kernel, iterations=1)

    # Hough directly on binary foreground works fine here
    lines = cv2.HoughLinesP(
        cleaned,
        rho=1,
        theta=np.pi / 180,
        threshold=WallConfig.HOUGH_THRESHOLD,
        minLineLength=WallConfig.HOUGH_MIN_LENGTH,
        maxLineGap=WallConfig.HOUGH_MAX_GAP,
    )

    if lines is None:
        return []

    segments: List[LineSegment] = []

    for line in lines[:, 0]:
        x1, y1, x2, y2 = map(float, line)
        dx = x2 - x1
        dy = y2 - y1
        length = float(np.hypot(dx, dy))

        if length < WallConfig.HOUGH_MIN_LENGTH:
            continue

        angle = normalize_angle(np.degrees(np.arctan2(dy, dx)))

        # Hard architectural prior: keep only near-horizontal / near-vertical
        if not is_orthogonal_angle(angle, WallConfig.ORTHOGONAL_TOL):
            continue

        segments.append(
            LineSegment(
                x1=x1,
                y1=y1,
                x2=x2,
                y2=y2,
                length=length,
                angle=angle,
            )
        )

    # Merge fragmented pieces of the same physical line
    segments = merge_colinear_segments(segments)

    # One more length filter after merge
    segments = [s for s in segments if s.length >= WallConfig.HOUGH_MIN_LENGTH]

    return segments


def can_pair_parallel(seg1: LineSegment, seg2: LineSegment) -> bool:
    """
    Check if two segments are likely the two boundary lines of the same wall.
    """
    # Similar orientation
    if angle_diff(seg1.angle, seg2.angle) > WallConfig.ANGLE_TOLERANCE:
        return False

    axis_dir = segment_direction(seg1)
    n = np.array([-axis_dir[1], axis_dir[0]], dtype=float)
    origin = np.array([seg1.x1, seg1.y1], dtype=float)

    # Distance between lines measured by midpoint offset along normal
    mid2 = segment_midpoint(seg2)
    dist = abs(float(np.dot(mid2 - origin, n)))

    if not (WallConfig.MIN_WALL_THICKNESS <= dist <= WallConfig.MAX_WALL_THICKNESS):
        return False

    # They must overlap meaningfully along wall direction
    s1a, s1b = project_segment_to_axis(seg1, origin, axis_dir)
    s2a, s2b = project_segment_to_axis(seg2, origin, axis_dir)
    ov = overlap_1d(s1a, s1b, s2a, s2b)

    min_len = min(seg1.length, seg2.length)
    if ov < WallConfig.MIN_OVERLAP_ABS:
        return False
    if ov / max(min_len, 1.0) < WallConfig.MIN_OVERLAP_RATIO:
        return False

    return True


def create_wall_from_pair(seg1: LineSegment, seg2: LineSegment, wall_id: int) -> Optional[Wall]:
    """
    Build a wall from two parallel boundary segments.
    Midline is computed on the overlapping interval of the two segments.
    """
    axis_dir = segment_direction(seg1)
    n = np.array([-axis_dir[1], axis_dir[0]], dtype=float)

    origin = np.array([seg1.x1, seg1.y1], dtype=float)

    # Project segments onto common axis
    s1a, s1b = project_segment_to_axis(seg1, origin, axis_dir)
    s2a, s2b = project_segment_to_axis(seg2, origin, axis_dir)

    ov_a = max(s1a, s2a)
    ov_b = min(s1b, s2b)
    ov_len = ov_b - ov_a

    if ov_len < WallConfig.MIN_OVERLAP_ABS:
        return None

    # Average normal offsets of the two boundary lines
    pts1 = [
        np.array([seg1.x1, seg1.y1], dtype=float),
        np.array([seg1.x2, seg1.y2], dtype=float),
    ]
    pts2 = [
        np.array([seg2.x1, seg2.y1], dtype=float),
        np.array([seg2.x2, seg2.y2], dtype=float),
    ]

    off1 = float(np.mean([np.dot(p - origin, n) for p in pts1]))
    off2 = float(np.mean([np.dot(p - origin, n) for p in pts2]))

    thickness = abs(off2 - off1)
    mid_off = (off1 + off2) / 2.0

    p_start = origin + ov_a * axis_dir + mid_off * n
    p_end = origin + ov_b * axis_dir + mid_off * n

    length = float(np.linalg.norm(p_end - p_start))
    if length < WallConfig.MIN_OVERLAP_ABS:
        return None

    angle = normalize_angle(np.degrees(np.arctan2(p_end[1] - p_start[1], p_end[0] - p_start[0])))

    midline = LineSegment(
        x1=float(p_start[0]),
        y1=float(p_start[1]),
        x2=float(p_end[0]),
        y2=float(p_end[1]),
        length=length,
        angle=angle,
    )

    confidence = min(
        0.98,
        WallConfig.BASE_CONFIDENCE
        + 0.10 * min(1.0, ov_len / 120.0)
        + 0.10 * min(1.0, thickness / 25.0),
    )

    return Wall(
        id=wall_id,
        midline=midline,
        thickness_px=float(thickness),
        angle_deg=float(angle),
        confidence=float(confidence),
    )


def pair_parallel_lines(segments: List[LineSegment]) -> List[Wall]:
    """
    Pair parallel line segments into walls.
    IMPORTANT: only paired segments become walls.
    """
    if not segments:
        return []

    walls: List[Wall] = []
    used = set()
    wall_id = 1

    # Prefer long segments first
    order = sorted(range(len(segments)), key=lambda i: segments[i].length, reverse=True)

    for i in order:
        if i in used:
            continue

        seg1 = segments[i]
        best_j = None
        best_score = -1.0
        best_wall = None

        for j in order:
            if j == i or j in used:
                continue

            seg2 = segments[j]

            if not can_pair_parallel(seg1, seg2):
                continue

            candidate_wall = create_wall_from_pair(seg1, seg2, wall_id)
            if candidate_wall is None:
                continue

            # Score prefers longer overlap and reasonable thickness
            thickness_score = 1.0 - abs(candidate_wall.thickness_px - 18.0) / 18.0
            thickness_score = max(0.0, thickness_score)

            score = (
                0.6 * min(seg1.length, seg2.length)
                + 0.3 * candidate_wall.midline.length
                + 20.0 * thickness_score
            )

            if score > best_score:
                best_score = score
                best_j = j
                best_wall = candidate_wall

        if best_j is not None and best_wall is not None:
            walls.append(best_wall)
            used.add(i)
            used.add(best_j)
            wall_id += 1

    return walls


def detect_walls(binary_img: np.ndarray) -> List[Wall]:
    """Full wall detection pipeline."""
    segments = detect_wall_segments(binary_img)
    walls = pair_parallel_lines(segments)
    return walls