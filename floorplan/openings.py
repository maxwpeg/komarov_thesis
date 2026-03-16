"""Opening detection: find doors and windows in walls."""

import cv2
import numpy as np
from typing import List, Tuple, Optional
from .floorplan_types import Opening, OpeningType, Wall, LineSegment, Gap
from .geometry import project_point_to_wall_axis, segment_axis_interval


class OpeningConfig:
    """Configuration for opening detection."""
    
    # Gap detection thresholds
    MIN_GAP_LENGTH = 10  # minimum gap length in pixels
    MAX_GAP_LENGTH = 300  # maximum gap length in pixels
    GAP_PROFILE_STEP = 1  # step size for profiling along wall
    GAP_THRESHOLD = 200  # brightness threshold for gap detection (lower = more gap pixels)
    
    # ROI analysis
    ROI_PADDING = 10  # padding around gap for ROI
    
    # Door detection
    DOOR_MARKER_MIN_LENGTH = 8
    DOOR_MARKER_MAX_LENGTH = 200
    DOOR_MARKER_ANGLE_RANGE = (75, 105)  # perpendicular to wall
    DOOR_CROSS_MARGIN = 2.0
    DOOR_CENTER_TOL = 16.0
    DOOR_SIDE_TOL = 14.0
    INSIDE_THICKNESS_MARGIN = 3.0

    # Window detection
    WINDOW_LINE_MIN_LENGTH = 8
    WINDOW_LINE_MAX_LENGTH = 240
    WINDOW_LINE_ANGLE_RANGE = (-15, 15)  # parallel to wall
    WINDOW_MIN_LINES = 2
    WINDOW_MAX_LINES = 5
    WINDOW_INTERVAL_MARGIN = 6.0

    # Classification confidence
    BASE_CONFIDENCE = 0.5


def find_gaps_along_wall(wall: Wall, binary_img: np.ndarray) -> List[Gap]:
    """
    Find gaps (openings) along a wall by analyzing pixel profile.
    
    Args:
        wall: Wall object.
        binary_img: Binary image (walls are white/255).
        
    Returns:
        List of Gap objects.
    """
    midline = wall.midline
    
    # Create perpendicular profile
    # Sample points along the wall and check for gaps perpendicular to it
    
    num_samples = max(2, int(midline.length / OpeningConfig.GAP_PROFILE_STEP))
    
    # Direction along wall
    wall_dx = midline.x2 - midline.x1
    wall_dy = midline.y2 - midline.y1
    wall_len = np.sqrt(wall_dx**2 + wall_dy**2)
    if wall_len < 1:
        return []
    
    wall_dx /= wall_len
    wall_dy /= wall_len
    
    # Perpendicular direction (normal to wall)
    normal_dx = -wall_dy
    normal_dy = wall_dx
    
    # Sample along wall and build profile
    profile = []
    positions = []
    
    for t in np.linspace(0, 1, num_samples):
        x = midline.x1 + t * wall_dx * wall_len
        y = midline.y1 + t * wall_dy * wall_len
        
        # Check perpendicular profile (thickness)
        has_wall = False
        
        # Check walls radius in pixel coords
        for d in np.linspace(-wall.thickness_px / 2, wall.thickness_px / 2, 5):
            check_x = int(x + d * normal_dx)
            check_y = int(y + d * normal_dy)
            
            if 0 <= check_x < binary_img.shape[1] and 0 <= check_y < binary_img.shape[0]:
                if binary_img[check_y, check_x] > 127:  # white pixel = wall
                    has_wall = True
                    break
        
        profile.append(255 if has_wall else 0)
        positions.append(t * wall_len)
    
    # Find gaps (consecutive zero or low pixels)
    gaps = []
    in_gap = False
    gap_start = 0
    
    for i, val in enumerate(profile):
        if val < OpeningConfig.GAP_THRESHOLD and not in_gap:
            gap_start = i
            in_gap = True
        elif val >= OpeningConfig.GAP_THRESHOLD and in_gap:
            gap_len = i - gap_start
            if OpeningConfig.MIN_GAP_LENGTH <= gap_len <= OpeningConfig.MAX_GAP_LENGTH:
                # Create gap
                start_px = positions[gap_start]
                end_px = positions[i-1]
                
                # Create bounding box for ROI (in image coords)
                roi_bbox = create_gap_bbox(wall, start_px, end_px)
                
                gap = Gap(
                    wall_id=wall.id,
                    start_px=start_px,
                    end_px=end_px,
                    length_px=end_px - start_px,
                    bbox=roi_bbox
                )
                gaps.append(gap)
            
            in_gap = False
    
    # Check final gap
    if in_gap:
        gap_len = len(profile) - gap_start
        if OpeningConfig.MIN_GAP_LENGTH <= gap_len <= OpeningConfig.MAX_GAP_LENGTH:
            start_px = positions[gap_start]
            end_px = positions[-1]
            roi_bbox = create_gap_bbox(wall, start_px, end_px)
            gap = Gap(
                wall_id=wall.id,
                start_px=start_px,
                end_px=end_px,
                length_px=end_px - start_px,
                bbox=roi_bbox
            )
            gaps.append(gap)
    
    return gaps


def create_gap_bbox(wall: Wall, start_px: float, end_px: float) -> Tuple[int, int, int, int]:
    """
    Create bounding box for a gap on a wall.
    
    Args:
        wall: Wall object.
        start_px, end_px: Distances along wall axis.
        
    Returns:
        Bounding box (x1, y1, x2, y2).
    """
    midline = wall.midline
    
    # Direction along wall
    wall_dx = midline.x2 - midline.x1
    wall_dy = midline.y2 - midline.y1
    wall_len = np.sqrt(wall_dx**2 + wall_dy**2)
    if wall_len < 1:
        return (int(midline.x1), int(midline.y1), int(midline.x2), int(midline.y2))
    
    wall_dx /= wall_len
    wall_dy /= wall_len
    
    # Perpendicular direction
    normal_dx = -wall_dy
    normal_dy = wall_dx
    
    # Get four corners of the gap ROI
    t1 = start_px / wall_len
    t2 = end_px / wall_len
    
    p1 = np.array([midline.x1 + t1 * wall_dx * wall_len, midline.y1 + t1 * wall_dy * wall_len])
    p2 = np.array([midline.x1 + t2 * wall_dx * wall_len, midline.y1 + t2 * wall_dy * wall_len])
    
    half_thickness = wall.thickness_px / 2 + OpeningConfig.ROI_PADDING
    
    p3 = p1 + half_thickness * np.array([normal_dx, normal_dy])
    p4 = p1 - half_thickness * np.array([normal_dx, normal_dy])
    p5 = p2 + half_thickness * np.array([normal_dx, normal_dy])
    p6 = p2 - half_thickness * np.array([normal_dx, normal_dy])
    
    all_points = [p1, p2, p3, p4, p5, p6]
    xs = [p[0] for p in all_points]
    ys = [p[1] for p in all_points]
    
    x1, x2 = min(xs), max(xs)
    y1, y2 = min(ys), max(ys)
    
    return (int(x1), int(y1), int(x2), int(y2))


def classify_opening(
    gap: Gap,
    wall: Wall,
    binary_img: np.ndarray,
    original_img: np.ndarray
) -> Optional[Tuple[OpeningType, float, dict]]:
    """
    Classify a gap as door or window.
    
    Args:
        gap: Gap object.
        wall: Wall object.
        binary_img: Binary image of the floor plan.
        original_img: Original image for visualization.
        
    Returns:
        Tuple of (type, confidence, metadata) or None if unclear.
    """
    x1, y1, x2, y2 = gap.bbox
    x1 = max(0, x1)
    y1 = max(0, y1)
    x2 = min(binary_img.shape[1], x2)
    y2 = min(binary_img.shape[0], y2)
    
    if x2 <= x1 or y2 <= y1:
        return None
    
    roi = original_img[y1:y2, x1:x2]
    roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    
    # Find line segments in ROI
    edges = cv2.Canny(roi_gray, 40, 120)
    edges = cv2.dilate(edges, np.ones((3, 3), dtype=np.uint8), iterations=1)

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=10,
        minLineLength=6,
        maxLineGap=6
    )

    if lines is None or len(lines) == 0:
        return None

    # Reshape lines to handle different array shapes
    lines = lines.reshape(-1, 4)

    # Analyze line segments against wall local coordinates.
    half_thickness = max(1.0, wall.thickness_px / 2.0)
    gap_start = float(gap.start_px)
    gap_end = float(gap.end_px)
    gap_center = (gap_start + gap_end) / 2.0

    central_crossers = []
    side_markers = []
    interior_parallel = []

    for x1_l, y1_l, x2_l, y2_l in lines:
        gx1 = float(x1_l + x1)
        gy1 = float(y1_l + y1)
        gx2 = float(x2_l + x1)
        gy2 = float(y2_l + y1)
        dx = gx2 - gx1
        dy = gy2 - gy1
        length = float(np.hypot(dx, dy))

        if length < OpeningConfig.DOOR_MARKER_MIN_LENGTH:
            continue

        angle = float(np.degrees(np.arctan2(dy, dx)) % 180.0)
        wall_angle = wall.angle_deg % 180.0
        relative_angle = ((angle - wall_angle + 90.0) % 180.0) - 90.0
        abs_relative = abs(relative_angle)

        t1, d1 = project_point_to_wall_axis((gx1, gy1), wall)
        t2, d2 = project_point_to_wall_axis((gx2, gy2), wall)
        center_t = (t1 + t2) / 2.0

        segment = LineSegment(gx1, gy1, gx2, gy2, angle=angle, length=length)
        interval_start, interval_end = segment_axis_interval(segment, wall)

        inside_thickness = (
            abs(d1) <= (half_thickness + OpeningConfig.INSIDE_THICKNESS_MARGIN)
            and abs(d2) <= (half_thickness + OpeningConfig.INSIDE_THICKNESS_MARGIN)
        )
        crosses_both_boundaries = (
            min(d1, d2) < -(half_thickness + OpeningConfig.DOOR_CROSS_MARGIN)
            and max(d1, d2) > (half_thickness + OpeningConfig.DOOR_CROSS_MARGIN)
        )

        is_perpendicular = abs(abs_relative - 90.0) <= 15.0
        is_parallel = abs_relative <= 15.0

        if is_perpendicular and length <= OpeningConfig.DOOR_MARKER_MAX_LENGTH:
            near_gap_side = (
                abs(center_t - gap_start) <= OpeningConfig.DOOR_SIDE_TOL
                or abs(center_t - gap_end) <= OpeningConfig.DOOR_SIDE_TOL
            )
            if inside_thickness and near_gap_side:
                side_markers.append({
                    "line": (gx1, gy1, gx2, gy2),
                    "length": length,
                    "center_t": center_t,
                })
            if crosses_both_boundaries and abs(center_t - gap_center) <= OpeningConfig.DOOR_CENTER_TOL:
                central_crossers.append({
                    "line": (gx1, gy1, gx2, gy2),
                    "length": length,
                    "center_t": center_t,
                })

        if is_parallel and inside_thickness and OpeningConfig.WINDOW_LINE_MIN_LENGTH <= length <= OpeningConfig.WINDOW_LINE_MAX_LENGTH:
            if (
                interval_start >= (gap_start - OpeningConfig.WINDOW_INTERVAL_MARGIN)
                and interval_end <= (gap_end + OpeningConfig.WINDOW_INTERVAL_MARGIN)
            ):
                interior_parallel.append({
                    "line": (gx1, gy1, gx2, gy2),
                    "length": length,
                    "center_t": center_t,
                })

    # Door: one central cross marker + two side perpendicular markers.
    if central_crossers and len(side_markers) >= 2:
        central = sorted(
            central_crossers,
            key=lambda item: abs(item["center_t"] - gap_center),
        )[0]
        confidence = min(0.97, 0.70 + 0.06 * len(side_markers))
        return (
            OpeningType.DOOR,
            confidence,
            {
                "marker": list(central["line"]),
                "central_crossers": len(central_crossers),
                "side_markers": len(side_markers),
                "pattern": "center_cross_plus_sides",
            },
        )

    # Window: two side perpendicular markers + >=2 inner parallel lines.
    if len(side_markers) >= 2 and len(interior_parallel) >= OpeningConfig.WINDOW_MIN_LINES:
        selected_lines = [list(item["line"]) for item in interior_parallel[:OpeningConfig.WINDOW_MAX_LINES]]
        confidence = min(0.95, 0.65 + 0.05 * len(interior_parallel))
        return (
            OpeningType.WINDOW,
            confidence,
            {
                "lines": selected_lines,
                "side_markers": len(side_markers),
                "parallel_lines": len(interior_parallel),
                "pattern": "side_markers_plus_parallel",
            },
        )

    # Relaxed fallback for noisy scans.
    if central_crossers and len(side_markers) >= 1:
        central = central_crossers[0]
        return (
            OpeningType.DOOR,
            0.55,
            {
                "marker": list(central["line"]),
                "central_crossers": len(central_crossers),
                "side_markers": len(side_markers),
                "pattern": "door_relaxed",
            },
        )

    if len(interior_parallel) >= OpeningConfig.WINDOW_MIN_LINES:
        selected_lines = [list(item["line"]) for item in interior_parallel[:OpeningConfig.WINDOW_MAX_LINES]]
        return (
            OpeningType.WINDOW,
            0.5,
            {
                "lines": selected_lines,
                "parallel_lines": len(interior_parallel),
                "pattern": "window_relaxed",
            },
        )

    return None


def remove_duplicate_openings(openings: List[Opening]) -> List[Opening]:
    """
    Remove duplicate/overlapping openings using NMS.
    
    Args:
        openings: List of Opening objects.
        
    Returns:
        Filtered list.
    """
    if not openings:
        return []
    
    # Sort by confidence (descending)
    sorted_openings = sorted(openings, key=lambda o: o.confidence, reverse=True)
    
    keep = []
    for i, opening in enumerate(sorted_openings):
        keep_this = True
        
        for j in range(len(keep)):
            kept = keep[j]
            
            # Check IoU
            iou = bbox_iou(opening.bbox, kept.bbox)
            if iou > 0.3:  # too much overlap
                keep_this = False
                break
        
        if keep_this:
            keep.append(opening)
    
    return keep


def bbox_iou(box1: Tuple[int, int, int, int], box2: Tuple[int, int, int, int]) -> float:
    """Intersection over Union of two boxes."""
    x1_a, y1_a, x2_a, y2_a = box1
    x1_b, y1_b, x2_b, y2_b = box2
    
    inter_x1 = max(x1_a, x1_b)
    inter_y1 = max(y1_a, y1_b)
    inter_x2 = min(x2_a, x2_b)
    inter_y2 = min(y2_a, y2_b)
    
    inter_area = max(0, inter_x2 - inter_x1) * max(0, inter_y2 - inter_y1)
    
    box1_area = (x2_a - x1_a) * (y2_a - y1_a)
    box2_area = (x2_b - x1_b) * (y2_b - y1_b)
    
    union_area = box1_area + box2_area - inter_area
    
    if union_area < 1e-6:
        return 0.0
    
    return inter_area / union_area
