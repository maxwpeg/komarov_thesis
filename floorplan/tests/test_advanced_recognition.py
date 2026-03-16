"""Advanced floorplan recognition tests: openings, rooms, OCR, and assignments."""

from __future__ import annotations

import cv2
import numpy as np

from floorplan.floorplan_types import Dimension, Gap, LineSegment, Room, Wall
from floorplan.ocr_dimensions import assign_dimensions, detect_text_dimensions
from floorplan.openings import classify_opening
from floorplan.rooms import detect_rooms


def _horizontal_wall() -> Wall:
    return Wall(
        id=1,
        midline=LineSegment(x1=20, y1=100, x2=180, y2=100, length=160, angle=0),
        thickness_px=20,
        angle_deg=0.0,
        confidence=0.95,
    )


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

