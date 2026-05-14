"""Floor plan processing module.

Detects walls, doors, and windows from floor plan images using classical computer vision.
"""

from .floorplan_types import (
    Point,
    LineSegment,
    Wall,
    Gap,
    Opening,
    Room,
    Dimension,
    OpeningType,
    ProcessingResult,
)
from .main import FloorPlanProcessor

__version__ = "1.0.0"
__all__ = [
    "FloorPlanProcessor",
    "Point",
    "LineSegment",
    "Wall",
    "Gap",
    "Opening",
    "Room",
    "Dimension",
    "OpeningType",
    "ProcessingResult",
]
