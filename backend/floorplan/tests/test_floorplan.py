"""Unit tests for the current floorplan package API."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from floorplan.floorplan_types import LineSegment, Opening, OpeningType, ProcessingResult, Wall
from floorplan.main import FloorPlanProcessor
from floorplan.visualize import create_overlay
from floorplan.walls_morph import detect_walls


class TestProcessingResult:
    def test_roundtrip_json(self):
        result = ProcessingResult(
            image_width=640,
            image_height=480,
            walls=[
                Wall(
                    id=1,
                    midline=LineSegment(10, 20, 30, 40),
                    thickness_px=12.0,
                    angle_deg=0.0,
                    confidence=0.9,
                )
            ],
            openings=[
                Opening(
                    type=OpeningType.DOOR,
                    wall_id=1,
                    bbox=(100, 100, 140, 140),
                    confidence=0.8,
                    center=(120.0, 120.0),
                )
            ],
        )

        restored = ProcessingResult.from_dict(result.to_dict())

        assert restored.image_width == 640
        assert len(restored.walls) == 1
        assert restored.openings[0].type == OpeningType.DOOR


class TestWallDetection:
    def test_detect_walls_from_simple_binary_image(self):
        image = np.zeros((200, 200), dtype=np.uint8)
        cv2.rectangle(image, (20, 20), (180, 40), 255, -1)
        walls = detect_walls(image)
        assert len(walls) >= 1
        assert all(wall.thickness_px >= 0 for wall in walls)


class TestVisualization:
    def test_create_overlay_returns_image_with_same_shape(self):
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        result = ProcessingResult(image_width=100, image_height=100)
        overlay = create_overlay(image, result)
        assert overlay.shape == image.shape


class TestProcessor:
    def test_missing_file_raises_value_error(self):
        processor = FloorPlanProcessor(debug=False)
        with pytest.raises(ValueError):
            processor.process(str(Path("missing-image.png")))
