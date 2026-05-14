"""Advanced floorplan recognition tests: openings, rooms, OCR, and assignments."""

from __future__ import annotations

import cv2
import numpy as np

from floorplan.floorplan_types import Dimension, Gap, LineSegment, Room, Wall
from floorplan.ocr_dimensions import assign_dimensions, detect_text_dimensions
from floorplan.openings import classify_opening
from floorplan.rooms import detect_rooms


def _wall(
    wall_id: int,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    thickness_px: float = 20,
) -> Wall:
    angle = float(np.degrees(np.arctan2(y2 - y1, x2 - x1)) % 180.0)
    return Wall(
        id=wall_id,
        midline=LineSegment(
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            length=float(np.hypot(x2 - x1, y2 - y1)),
            angle=angle,
        ),
        thickness_px=thickness_px,
        angle_deg=angle,
        confidence=0.95,
    )


def _horizontal_wall() -> Wall:
    return Wall(
        id=1,
        midline=LineSegment(x1=20, y1=100, x2=180, y2=100, length=160, angle=0),
        thickness_px=20,
        angle_deg=0.0,
        confidence=0.95,
    )


def _shifted_parallel_outer_seam_walls(
    *,
    thickness_px: float = 8,
    lateral_shift_px: float = 10,
    axis_gap_px: float = 12,
) -> list[Wall]:
    return [
        _wall(1, 40, 40, 280, 40, thickness_px=thickness_px),
        _wall(2, 40, 40, 40, 280, thickness_px=thickness_px),
        _wall(3, 40, 150, 280, 150, thickness_px=thickness_px),
        _wall(4, 40, 280, 180, 280, thickness_px=thickness_px),
        _wall(5, 180, 150, 180, 280, thickness_px=thickness_px),
        _wall(6, 280, 40, 280, 90, thickness_px=thickness_px),
        _wall(
            7,
            280 - lateral_shift_px,
            90 + axis_gap_px,
            280 - lateral_shift_px,
            150,
            thickness_px=thickness_px,
        ),
    ]


def _slanted_parallel_outer_seam_walls(
    *,
    thickness_px: float = 8,
    lateral_shift_px: float = 8,
    axis_gap_px: float = 12,
    slope_dx_px: float = 2,
) -> list[Wall]:
    return [
        _wall(1, 40, 40, 240, 40, thickness_px=thickness_px),
        _wall(2, 40, 40, 40, 220, thickness_px=thickness_px),
        _wall(3, 40, 220, 240, 220, thickness_px=thickness_px),
        _wall(4, 240, 40, 240 + slope_dx_px, 100, thickness_px=thickness_px),
        _wall(
            5,
            240 - lateral_shift_px,
            100 + axis_gap_px,
            240 - lateral_shift_px + slope_dx_px,
            220,
            thickness_px=thickness_px,
        ),
    ]


def _gap_for_wall() -> Gap:
    # Gap x-range 80..120 on wall x-range 20..180 => start/end along axis: 60..100
    return Gap(
        wall_id=1,
        start_px=60,
        end_px=100,
        length_px=40,
        bbox=(70, 70, 130, 130),
    )


def test_classify_opening_detects_door_pattern():
    wall = _horizontal_wall()
    gap = _gap_for_wall()

    binary = np.zeros((200, 200), dtype=np.uint8)
    image = np.full((200, 200, 3), 255, dtype=np.uint8)

    # Central perpendicular line crossing both wall boundaries.
    cv2.line(image, (100, 75), (100, 125), (0, 0, 0), 2)
    # Two side perpendicular markers within wall thickness near gap borders.
    cv2.line(image, (82, 92), (82, 108), (0, 0, 0), 2)
    cv2.line(image, (118, 92), (118, 108), (0, 0, 0), 2)

    classified = classify_opening(gap, wall, binary, image)
    assert classified is not None
    opening_type, confidence, metadata = classified
    assert opening_type.value == "door"
    assert confidence >= 0.5
    assert metadata.get("marker") is not None


def test_classify_opening_detects_window_pattern():
    wall = _horizontal_wall()
    gap = _gap_for_wall()

    binary = np.zeros((200, 200), dtype=np.uint8)
    image = np.full((200, 200, 3), 255, dtype=np.uint8)

    # Side perpendicular markers within wall thickness.
    cv2.line(image, (82, 92), (82, 108), (0, 0, 0), 2)
    cv2.line(image, (118, 92), (118, 108), (0, 0, 0), 2)
    # Two lines parallel to wall between side markers.
    cv2.line(image, (84, 96), (116, 96), (0, 0, 0), 2)
    cv2.line(image, (84, 104), (116, 104), (0, 0, 0), 2)

    classified = classify_opening(gap, wall, binary, image)
    assert classified is not None
    opening_type, confidence, metadata = classified
    assert opening_type.value == "window"
    assert confidence >= 0.5
    assert len(metadata.get("lines", [])) >= 2


def test_detect_rooms_returns_closed_region():
    image = np.zeros((220, 220), dtype=np.uint8)
    walls = [
        Wall(1, LineSegment(30, 30, 190, 30, length=160, angle=0), 10, 0.0, 0.9),
        Wall(2, LineSegment(30, 190, 190, 190, length=160, angle=0), 10, 0.0, 0.9),
        Wall(3, LineSegment(30, 30, 30, 190, length=160, angle=90), 10, 90.0, 0.9),
        Wall(4, LineSegment(190, 30, 190, 190, length=160, angle=90), 10, 90.0, 0.9),
    ]

    rooms = detect_rooms(image, walls)
    assert len(rooms) >= 1
    first = rooms[0]
    assert first.room_number == "1"
    assert len(first.boundary_points) >= 4
    assert 80 <= first.center[0] <= 140
    assert 80 <= first.center[1] <= 140


def test_detect_rooms_keeps_perimeter_room_when_outer_gap_is_within_adaptive_threshold():
    image = np.zeros((260, 260), dtype=np.uint8)
    walls = [
        _wall(1, 30, 30, 116, 30, thickness_px=20),
        _wall(2, 144, 30, 230, 30, thickness_px=20),
        _wall(3, 30, 230, 230, 230, thickness_px=20),
        _wall(4, 30, 30, 30, 230, thickness_px=20),
        _wall(5, 230, 30, 230, 230, thickness_px=20),
        _wall(6, 30, 130, 230, 130, thickness_px=20),
        _wall(7, 130, 130, 130, 230, thickness_px=20),
    ]

    rooms = detect_rooms(image, walls)

    assert len(rooms) == 3
    assert any(room.center[1] < 120 for room in rooms)


def test_detect_rooms_does_not_close_large_outer_gap():
    image = np.zeros((260, 260), dtype=np.uint8)
    walls = [
        _wall(1, 30, 30, 110, 30, thickness_px=20),
        _wall(2, 150, 30, 230, 30, thickness_px=20),
        _wall(3, 30, 230, 230, 230, thickness_px=20),
        _wall(4, 30, 30, 30, 230, thickness_px=20),
        _wall(5, 230, 30, 230, 230, thickness_px=20),
        _wall(6, 30, 130, 230, 130, thickness_px=20),
        _wall(7, 130, 130, 130, 230, thickness_px=20),
    ]

    rooms = detect_rooms(image, walls)

    assert len(rooms) == 2
    assert all(room.center[1] > 120 for room in rooms)


def test_detect_rooms_handles_slightly_slanted_outer_wall():
    image = np.zeros((240, 240), dtype=np.uint8)
    walls = [
        _wall(1, 40, 42, 200, 28, thickness_px=16),
        _wall(2, 40, 42, 40, 200, thickness_px=16),
        _wall(3, 200, 28, 200, 200, thickness_px=16),
        _wall(4, 40, 200, 200, 200, thickness_px=16),
    ]

    rooms = detect_rooms(image, walls)

    assert len(rooms) == 1
    assert 90 <= rooms[0].center[0] <= 150
    assert 90 <= rooms[0].center[1] <= 150


def test_detect_rooms_keeps_perimeter_room_with_shifted_parallel_outer_seam():
    image = np.zeros((360, 360), dtype=np.uint8)

    rooms = detect_rooms(image, _shifted_parallel_outer_seam_walls())

    assert len(rooms) == 2
    assert any(room.center[1] < 140 for room in rooms)


def test_detect_rooms_does_not_stitch_parallel_seam_when_lateral_shift_is_too_large():
    image = np.zeros((360, 360), dtype=np.uint8)

    rooms = detect_rooms(
        image,
        _shifted_parallel_outer_seam_walls(lateral_shift_px=16, axis_gap_px=12),
    )

    assert len(rooms) == 1
    assert all(room.center[1] > 160 for room in rooms)


def test_detect_rooms_does_not_stitch_parallel_seam_when_axis_gap_is_too_large():
    image = np.zeros((360, 360), dtype=np.uint8)

    rooms = detect_rooms(
        image,
        _shifted_parallel_outer_seam_walls(lateral_shift_px=10, axis_gap_px=14),
    )

    assert len(rooms) == 1
    assert all(room.center[1] > 160 for room in rooms)


def test_detect_rooms_handles_slightly_slanted_parallel_outer_seam():
    image = np.zeros((320, 320), dtype=np.uint8)

    rooms = detect_rooms(image, _slanted_parallel_outer_seam_walls())

    assert len(rooms) == 1
    assert 100 <= rooms[0].center[0] <= 180
    assert 90 <= rooms[0].center[1] <= 170


def test_detect_text_dimensions_normalizes_to_meters(monkeypatch):
    class _DummyOutput:
        DICT = "DICT"

    class _DummyTesseract:
        Output = _DummyOutput

        @staticmethod
        def image_to_data(*_args, **_kwargs):
            return {
                "text": ["2400", "3,5м", "120cm", "nope"],
                "conf": ["90", "85", "80", "99"],
                "left": [10, 30, 50, 70],
                "top": [10, 20, 30, 40],
                "width": [20, 20, 20, 20],
                "height": [10, 10, 10, 10],
            }

    import floorplan.ocr_dimensions as ocr_module

    monkeypatch.setattr(ocr_module, "pytesseract", _DummyTesseract)
    dims = detect_text_dimensions(np.zeros((100, 100), dtype=np.uint8))

    values = sorted(round(item.value, 2) for item in dims)
    assert values == [1.2, 2.4, 3.5]
    assert all(item.unit == "m" for item in dims)


def test_assign_dimensions_links_to_wall_and_room():
    walls = [_horizontal_wall()]
    rooms = [
        Room(
            id=7,
            room_number="1",
            name="Room 1",
            boundary_points=[[40, 40], [160, 40], [160, 160], [40, 160]],
            center=(100, 100),
        )
    ]
    dimensions = [
        Dimension(id=1, x=95, y=85, value=2.4, unit="m"),
    ]

    assigned = assign_dimensions(dimensions, walls, rooms)
    assert assigned[0].wall_id == 1
    assert assigned[0].room_id == 7
