"""Data structures for floor plan processing."""

from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Any
from enum import Enum
import json


class OpeningType(str, Enum):
    """Type of opening: door or window."""
    DOOR = "door"
    WINDOW = "window"
    UNKNOWN = "unknown"


@dataclass
class Point:
    """2D point."""
    x: float
    y: float

    def to_list(self) -> List[float]:
        return [self.x, self.y]

    @classmethod
    def from_list(cls, p: List[float]) -> "Point":
        return cls(p[0], p[1])


@dataclass
class LineSegment:
    """Line segment with coordinates and properties."""
    x1: float
    y1: float
    x2: float
    y2: float
    angle: Optional[float] = None  # in degrees, 0-180
    length: Optional[float] = None

    def to_list(self) -> List[float]:
        return [self.x1, self.y1, self.x2, self.y2]

    def endpoints(self) -> Tuple[Point, Point]:
        return Point(self.x1, self.y1), Point(self.x2, self.y2)


@dataclass
class Wall:
    """Wall represented as central axis + thickness."""
    id: int
    midline: LineSegment  # central axis
    thickness_px: float  # distance between parallel lines in pixels
    angle_deg: float  # 0-90 (horizontal/vertical)
    confidence: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "midline": self.midline.to_list(),
            "thickness_px": self.thickness_px,
            "angle_deg": self.angle_deg,
            "confidence": self.confidence,
        }


@dataclass
class Gap:
    """Gap (opening) found in a wall."""
    wall_id: int
    start_px: float  # distance along wall axis where gap starts
    end_px: float  # distance along wall axis where gap ends
    length_px: float  # end_px - start_px
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2 in image coords


@dataclass
class Opening:
    """Door or window opening."""
    type: OpeningType
    wall_id: Optional[int]  # ID of the wall it belongs to
    bbox: Tuple[int, int, int, int]  # bounding box [x1, y1, x2, y2]
    confidence: float
    center: Tuple[float, float]  # center coordinates
    marker: Optional[List[List[float]]] = None  # for doors: line coordinates [[x1,y1],[x2,y2]]
    lines: Optional[List[List[List[float]]]] = None  # for windows: list of lines
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "type": self.type.value,
            "wall_id": self.wall_id,
            "bbox": list(self.bbox),
            "confidence": self.confidence,
            "center": list(self.center),
        }
        if self.marker is not None:
            result["marker"] = self.marker
        if self.lines is not None:
            result["lines"] = self.lines
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class Room:
    """Detected room polygon."""
    id: int
    room_number: str
    name: Optional[str]
    boundary_points: List[List[float]]
    center: Tuple[float, float]
    area_px: Optional[float] = None
    confidence: float = 1.0
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "room_number": self.room_number,
            "name": self.name,
            "boundary_points": self.boundary_points,
            "center": list(self.center),
            "confidence": self.confidence,
        }
        if self.area_px is not None:
            result["area_px"] = self.area_px
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class Dimension:
    """Detected text dimension normalized to meters."""
    id: int
    x: float
    y: float
    value: float
    unit: str = "m"
    text: Optional[str] = None
    confidence: Optional[float] = None
    bbox: Optional[Tuple[int, int, int, int]] = None
    wall_id: Optional[int] = None
    room_id: Optional[int] = None
    line_x1: Optional[float] = None
    line_y1: Optional[float] = None
    line_x2: Optional[float] = None
    line_y2: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "id": self.id,
            "x": self.x,
            "y": self.y,
            "value": self.value,
            "unit": self.unit,
            "text": self.text,
            "confidence": self.confidence,
            "wall_id": self.wall_id,
            "room_id": self.room_id,
            "line_x1": self.line_x1,
            "line_y1": self.line_y1,
            "line_x2": self.line_x2,
            "line_y2": self.line_y2,
        }
        if self.bbox is not None:
            result["bbox"] = list(self.bbox)
        if self.metadata:
            result["metadata"] = self.metadata
        return result


@dataclass
class ProcessingResult:
    """Complete processing result."""
    image_width: int
    image_height: int
    walls: List[Wall] = field(default_factory=list)
    openings: List[Opening] = field(default_factory=list)
    rooms: List[Room] = field(default_factory=list)
    dimensions: List[Dimension] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "image": {
                "width": self.image_width,
                "height": self.image_height,
            },
            "walls": [w.to_dict() for w in self.walls],
            "openings": [o.to_dict() for o in self.openings],
            "rooms": [r.to_dict() for r in self.rooms],
            "dimensions": [d.to_dict() for d in self.dimensions],
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    def save_json(self, path: str) -> None:
        """Save to JSON file."""
        with open(path, "w") as f:
            f.write(self.to_json())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessingResult":
        """Deserialize from dict."""
        result = cls(
            image_width=data["image"]["width"],
            image_height=data["image"]["height"],
        )
        for wall_data in data.get("walls", []):
            line = wall_data["midline"]
            result.walls.append(
                Wall(
                    id=wall_data["id"],
                    midline=LineSegment(line[0], line[1], line[2], line[3]),
                    thickness_px=wall_data["thickness_px"],
                    angle_deg=wall_data["angle_deg"],
                    confidence=wall_data.get("confidence", 1.0),
                )
            )
        for opening_data in data.get("openings", []):
            bbox = tuple(opening_data["bbox"])
            result.openings.append(
                Opening(
                    type=OpeningType(opening_data["type"]),
                    wall_id=opening_data.get("wall_id"),
                    bbox=bbox,
                    confidence=opening_data["confidence"],
                    center=tuple(opening_data["center"]),
                    marker=opening_data.get("marker"),
                    lines=opening_data.get("lines"),
                    metadata=opening_data.get("metadata"),
                )
            )
        for room_data in data.get("rooms", []):
            result.rooms.append(
                Room(
                    id=room_data["id"],
                    room_number=str(room_data.get("room_number", room_data["id"])),
                    name=room_data.get("name"),
                    boundary_points=room_data.get("boundary_points", []),
                    center=tuple(room_data.get("center", (0.0, 0.0))),
                    area_px=room_data.get("area_px"),
                    confidence=room_data.get("confidence", 1.0),
                    metadata=room_data.get("metadata"),
                )
            )
        for dim_data in data.get("dimensions", []):
            bbox = tuple(dim_data["bbox"]) if dim_data.get("bbox") else None
            result.dimensions.append(
                Dimension(
                    id=dim_data["id"],
                    x=float(dim_data["x"]),
                    y=float(dim_data["y"]),
                    value=float(dim_data["value"]),
                    unit=str(dim_data.get("unit", "m")),
                    text=dim_data.get("text"),
                    confidence=dim_data.get("confidence"),
                    bbox=bbox,
                    wall_id=dim_data.get("wall_id"),
                    room_id=dim_data.get("room_id"),
                    line_x1=dim_data.get("line_x1"),
                    line_y1=dim_data.get("line_y1"),
                    line_x2=dim_data.get("line_x2"),
                    line_y2=dim_data.get("line_y2"),
                    metadata=dim_data.get("metadata"),
                )
            )
        return result
