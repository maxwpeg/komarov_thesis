"""Geometry helpers shared across floor plan stages."""

from __future__ import annotations

from typing import Tuple

import numpy as np

from .floorplan_types import LineSegment, Wall


def _wall_direction(wall: Wall) -> Tuple[np.ndarray, float]:
    dx = wall.midline.x2 - wall.midline.x1
    dy = wall.midline.y2 - wall.midline.y1
    length = float(np.hypot(dx, dy))
    if length < 1e-6:
        return np.array([1.0, 0.0], dtype=float), 0.0
    return np.array([dx / length, dy / length], dtype=float), length


def _wall_normal(wall: Wall) -> np.ndarray:
    direction, _ = _wall_direction(wall)
    return np.array([-direction[1], direction[0]], dtype=float)


def wall_boundary_lines(wall: Wall) -> Tuple[LineSegment, LineSegment]:
    """
    Convert a wall represented by midline+thickness into two boundary lines.
    """
    direction, length = _wall_direction(wall)
    if length < 1e-6:
        return wall.midline, wall.midline

    normal = _wall_normal(wall)
    half_thickness = max(0.0, wall.thickness_px / 2.0)
    p1 = np.array([wall.midline.x1, wall.midline.y1], dtype=float)
    p2 = np.array([wall.midline.x2, wall.midline.y2], dtype=float)

    a1 = p1 + normal * half_thickness
    a2 = p2 + normal * half_thickness
    b1 = p1 - normal * half_thickness
    b2 = p2 - normal * half_thickness

    line_a = LineSegment(
        x1=float(a1[0]),
        y1=float(a1[1]),
        x2=float(a2[0]),
        y2=float(a2[1]),
        length=float(np.hypot(a2[0] - a1[0], a2[1] - a1[1])),
        angle=wall.angle_deg,
    )
    line_b = LineSegment(
        x1=float(b1[0]),
        y1=float(b1[1]),
        x2=float(b2[0]),
        y2=float(b2[1]),
        length=float(np.hypot(b2[0] - b1[0], b2[1] - b1[1])),
        angle=wall.angle_deg,
    )
    return line_a, line_b


def project_point_to_wall_axis(point: Tuple[float, float], wall: Wall) -> Tuple[float, float]:
    """
    Project a point to wall coordinates.

    Returns:
        (t_along_axis_px, signed_perpendicular_distance_px)
    """
    direction, _ = _wall_direction(wall)
    normal = _wall_normal(wall)
    origin = np.array([wall.midline.x1, wall.midline.y1], dtype=float)
    p = np.array([point[0], point[1]], dtype=float)

    delta = p - origin
    t = float(np.dot(delta, direction))
    signed_distance = float(np.dot(delta, normal))
    return t, signed_distance


def point_to_segment_distance(point: Tuple[float, float], segment: LineSegment) -> float:
    """Euclidean distance from point to finite line segment."""
    px, py = point
    x1, y1, x2, y2 = segment.x1, segment.y1, segment.x2, segment.y2
    dx = x2 - x1
    dy = y2 - y1

    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return float(np.hypot(px - x1, py - y1))

    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return float(np.hypot(px - proj_x, py - proj_y))


def segment_axis_interval(segment: LineSegment, wall: Wall) -> Tuple[float, float]:
    """Return min/max projection of a segment onto wall axis."""
    t1, _ = project_point_to_wall_axis((segment.x1, segment.y1), wall)
    t2, _ = project_point_to_wall_axis((segment.x2, segment.y2), wall)
    return (min(t1, t2), max(t1, t2))

