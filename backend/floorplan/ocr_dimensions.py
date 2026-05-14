"""OCR extraction of linear dimensions and assignment to walls/rooms."""

from __future__ import annotations

import re
from typing import Iterable, List, Optional

import cv2
import numpy as np

from .floorplan_types import Dimension, Room, Wall
from .geometry import project_point_to_wall_axis

try:
    import pytesseract
except Exception:  # pragma: no cover - handled gracefully when OCR dependency is absent
    pytesseract = None


class OCRConfig:
    """Configuration for OCR dimensions."""

    MIN_CONFIDENCE = 30.0
    MAX_WALL_ASSIGN_DISTANCE = 90.0
    WALL_PROJECTION_MARGIN = 30.0
    ROOM_FALLBACK_MAX_DISTANCE = 400.0


DIMENSION_PATTERN = re.compile(r"(?P<value>\d+[.,]?\d*)\s*(?P<unit>мм|mm|см|cm|м|m)?", re.IGNORECASE)


def _normalize_value_to_meters(value: float, unit: Optional[str]) -> float:
    if unit:
        normalized = unit.lower()
        if normalized in {"мм", "mm"}:
            return value / 1000.0
        if normalized in {"см", "cm"}:
            return value / 100.0
        if normalized in {"м", "m"}:
            return value

    # Heuristic for plans where units are omitted:
    # 2400 -> 2.4m (mm), 240 -> 2.4m (cm), 3.6 -> 3.6m.
    if value >= 1000:
        return value / 1000.0
    if value >= 100:
        return value / 100.0
    return value


def _iter_matches(text: str) -> Iterable[tuple[float, Optional[str]]]:
    for match in DIMENSION_PATTERN.finditer(text):
        value_raw = match.group("value")
        unit = match.group("unit")
        if not value_raw:
            continue
        try:
            value = float(value_raw.replace(",", "."))
        except ValueError:
            continue
        if value <= 0:
            continue
        yield value, unit


def detect_text_dimensions(image: np.ndarray) -> List[Dimension]:
    """
    Detect numeric dimensions from image text. Output values are normalized to meters.
    """
    if image is None or image.size == 0 or pytesseract is None:
        return []

    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image.copy()

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    try:
        ocr_data = pytesseract.image_to_data(
            enhanced,
            output_type=pytesseract.Output.DICT,
            lang="eng+rus",
        )
    except Exception:
        return []

    dimensions: List[Dimension] = []
    dim_id = 1

    total = len(ocr_data.get("text", []))
    for i in range(total):
        text = str(ocr_data["text"][i]).strip()
        if not text:
            continue

        try:
            conf = float(ocr_data["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if conf < OCRConfig.MIN_CONFIDENCE:
            continue

        left = int(ocr_data["left"][i])
        top = int(ocr_data["top"][i])
        width = int(ocr_data["width"][i])
        height = int(ocr_data["height"][i])
        if width <= 0 or height <= 0:
            continue

        cx = float(left + width / 2.0)
        cy = float(top + height / 2.0)

        found = False
        for value_raw, unit in _iter_matches(text):
            value_m = _normalize_value_to_meters(value_raw, unit)
            dimensions.append(
                Dimension(
                    id=dim_id,
                    x=cx,
                    y=cy,
                    value=float(value_m),
                    unit="m",
                    text=text,
                    confidence=conf / 100.0,
                    bbox=(left, top, left + width, top + height),
                    metadata={
                        "raw_value": value_raw,
                        "raw_unit": unit,
                        "source": "ocr",
                    },
                )
            )
            dim_id += 1
            found = True

        # Keep non-parsed OCR only for diagnostics if it still looks numeric.
        if not found and any(ch.isdigit() for ch in text):
            dimensions.append(
                Dimension(
                    id=dim_id,
                    x=cx,
                    y=cy,
                    value=0.0,
                    unit="m",
                    text=text,
                    confidence=conf / 100.0,
                    bbox=(left, top, left + width, top + height),
                    metadata={"source": "ocr_unparsed"},
                )
            )
            dim_id += 1

    # Remove unparsed fallback entries if parsed dimensions exist for the same bbox.
    parsed_bbox = {dim.bbox for dim in dimensions if dim.value > 0}
    dimensions = [dim for dim in dimensions if dim.value > 0 or dim.bbox not in parsed_bbox]
    return [dim for dim in dimensions if dim.value > 0]


def _assign_wall(dimension: Dimension, walls: List[Wall]) -> Optional[int]:
    if not walls:
        return None

    best_wall_id: Optional[int] = None
    best_distance = float("inf")

    for wall in walls:
        length = float(max(wall.midline.length or 0.0, 1.0))
        t, signed_dist = project_point_to_wall_axis((dimension.x, dimension.y), wall)
        if t < -OCRConfig.WALL_PROJECTION_MARGIN or t > (length + OCRConfig.WALL_PROJECTION_MARGIN):
            continue

        distance = abs(signed_dist)
        if distance < best_distance:
            best_distance = distance
            best_wall_id = wall.id

    if best_wall_id is None:
        return None
    if best_distance > OCRConfig.MAX_WALL_ASSIGN_DISTANCE:
        return None
    return best_wall_id


def _point_in_room(point: tuple[float, float], room: Room) -> bool:
    if not room.boundary_points or len(room.boundary_points) < 3:
        return False
    contour = np.array(room.boundary_points, dtype=np.float32).reshape((-1, 1, 2))
    return cv2.pointPolygonTest(contour, point, False) >= 0


def _assign_room(dimension: Dimension, rooms: List[Room]) -> Optional[int]:
    if not rooms:
        return None

    point = (float(dimension.x), float(dimension.y))
    containing = [room for room in rooms if _point_in_room(point, room)]
    if containing:
        return containing[0].id

    best_room_id = None
    best_distance = float("inf")
    for room in rooms:
        cx, cy = room.center
        dist = float(np.hypot(point[0] - cx, point[1] - cy))
        if dist < best_distance:
            best_distance = dist
            best_room_id = room.id

    if best_distance > OCRConfig.ROOM_FALLBACK_MAX_DISTANCE:
        return None
    return best_room_id


def assign_dimensions(dimensions: List[Dimension], walls: List[Wall], rooms: List[Room]) -> List[Dimension]:
    """
    Attach each dimension to nearest wall and room.
    """
    for dimension in dimensions:
        dimension.wall_id = _assign_wall(dimension, walls)
        dimension.room_id = _assign_room(dimension, rooms)
    return dimensions

