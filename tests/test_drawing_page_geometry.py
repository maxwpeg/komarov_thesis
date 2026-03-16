from __future__ import annotations

import cv2
import numpy as np

from DrawingPage import (
    build_door_symbol_segments,
    build_wall_mask,
    build_window_symbol_segments,
    extract_wall_contours,
    resolve_opening_wall,
)


def _rasterize_contours(contours: list[np.ndarray], shape: tuple[int, int]) -> np.ndarray:
    image = np.zeros(shape, dtype=np.uint8)
    if contours:
        int_contours = [np.round(contour).astype(np.int32) for contour in contours]
        cv2.polylines(image, int_contours, isClosed=True, color=255, thickness=1)
    return image


def test_wall_contours_do_not_create_internal_segments_for_l_joint():
    walls = [
        {"id": 1, "x1": 20, "y1": 40, "x2": 80, "y2": 40, "thickness": 20},
        {"id": 2, "x1": 80, "y1": 40, "x2": 80, "y2": 80, "thickness": 20},
    ]

    contours = extract_wall_contours(build_wall_mask(walls, 120, 120, 1.0))
    raster = _rasterize_contours(contours, (120, 120))

    assert raster[45, 80] == 0
    assert raster[40, 75] == 0
    assert raster[30, 80] == 255
    assert raster[40, 90] == 255


def test_wall_contours_do_not_create_internal_segments_for_t_joint():
    walls = [
        {"id": 1, "x1": 20, "y1": 60, "x2": 100, "y2": 60, "thickness": 20},
        {"id": 2, "x1": 60, "y1": 20, "x2": 60, "y2": 60, "thickness": 20},
    ]

    contours = extract_wall_contours(build_wall_mask(walls, 120, 120, 1.0))
    raster = _rasterize_contours(contours, (120, 120))

    assert raster[60, 60] == 0
    assert raster[50, 60] == 0
    assert raster[60, 20] == 255
    assert raster[70, 60] == 255


def test_wall_contours_do_not_create_internal_segments_for_cross_joint():
    walls = [
        {"id": 1, "x1": 20, "y1": 60, "x2": 100, "y2": 60, "thickness": 20},
        {"id": 2, "x1": 60, "y1": 20, "x2": 60, "y2": 100, "thickness": 20},
    ]

    contours = extract_wall_contours(build_wall_mask(walls, 120, 120, 1.0))
    raster = _rasterize_contours(contours, (120, 120))

    assert raster[60, 60] == 0
    assert raster[60, 50] == 0
    assert raster[50, 60] == 0
    assert raster[30, 50] == 255
    assert raster[50, 30] == 255
    assert raster[90, 70] == 255
    assert raster[70, 90] == 255


def test_door_symbol_segments_match_wall_thickness():
    walls = [{"id": 1, "x1": 20, "y1": 100, "x2": 180, "y2": 100, "thickness": 200}]
    door = {"id": 1, "x": 80, "y": 95, "width": 40, "height": 10, "wall_id": 1}

    segments = build_door_symbol_segments(door, walls, scale_factor=10.0)

    assert segments == [
        ((80.0, 90.0), (80.0, 110.0)),
        ((100.0, 75.0), (100.0, 125.0)),
        ((120.0, 90.0), (120.0, 110.0)),
    ]


def test_window_symbol_segments_stay_inside_wall_band():
    walls = [{"id": 1, "x1": 20, "y1": 100, "x2": 180, "y2": 100, "thickness": 200}]
    window = {"id": 1, "x": 80, "y": 95, "width": 40, "height": 10, "wall_id": 1}

    segments = build_window_symbol_segments(window, walls, scale_factor=10.0)

    assert segments == [
        ((80.0, 90.0), (80.0, 110.0)),
        ((120.0, 90.0), (120.0, 110.0)),
        ((82.0, 97.0), (118.0, 97.0)),
        ((82.0, 103.0), (118.0, 103.0)),
    ]


def test_resolve_opening_wall_uses_nearest_wall_fallback():
    walls = [
        {"id": 1, "x1": 20, "y1": 20, "x2": 20, "y2": 100, "thickness": 200},
        {"id": 2, "x1": 80, "y1": 20, "x2": 80, "y2": 100, "thickness": 200},
    ]
    opening = {"id": 1, "x": 74, "y": 45, "width": 12, "height": 30}

    wall = resolve_opening_wall(opening, walls, scale_factor=10.0)

    assert wall is not None
    assert wall["id"] == 2
