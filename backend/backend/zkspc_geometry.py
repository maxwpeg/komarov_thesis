"""Helpers for building ZKSPC display geometry."""

from __future__ import annotations

from typing import Any

from shapely.geometry import Polygon
from shapely.ops import unary_union


def build_zone_display_geometry(rooms: list[Any]) -> list[list[list[float]]]:
    polygons = []
    fallback = []
    for room in rooms:
        raw_points = getattr(room, "boundary_points", None)
        if raw_points is None and isinstance(room, dict):
            raw_points = room.get("boundary_points")
        points = [
            [float(point[0]), float(point[1])]
            for point in (raw_points or [])
            if isinstance(point, (list, tuple)) and len(point) >= 2
        ]
        if len(points) < 3:
            continue
        fallback.append(points)
        polygon = Polygon(points)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        if polygon.is_empty:
            continue
        polygons.append(polygon)

    if not polygons:
        return fallback

    union = unary_union(polygons)
    geometries = list(getattr(union, "geoms", [union]))
    result: list[list[list[float]]] = []
    for geometry in geometries:
        exterior = getattr(geometry, "exterior", None)
        if exterior is None:
            continue
        ring = [
            [round(float(x), 3), round(float(y), 3)]
            for x, y in list(exterior.coords)[:-1]
        ]
        if len(ring) >= 3:
            result.append(ring)
    return result or fallback
