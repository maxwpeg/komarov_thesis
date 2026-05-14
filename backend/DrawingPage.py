from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics

from backend.signal_planning import DETECTOR_SYMBOL_HALF_SIZE_PX, ZC_ROUTE_OFFSET_PX, ZC_SYMBOL_HALF_SIZE_PX, should_show_zc_terminator
from Page import Page
from consts import *

Point = tuple[float, float]
Segment = tuple[Point, Point]

PDF_CABLE_ROUTE_STROKE_WIDTH = 1.6
DISPLAY_ROUTE_SPACING = PDF_CABLE_ROUTE_STROKE_WIDTH
ZC_LABEL_TEXT = "ZC"
ARK_LABEL_TEXT = "ARK"
ZC_LABEL_FONT_SIZE = 8.0
FIRE_ALARM_LABEL_FONT_SIZE = 8.0
SIGNAL_LABEL_FONT_SIZE = 9.0
ZC_SIDE_VECTORS: dict[str, Point] = {
    "east": (1.0, 0.0),
    "west": (-1.0, 0.0),
    "north": (0.0, -1.0),
    "south": (0.0, 1.0),
}
FIRE_ALARM_AUTO_POINTS: tuple[Point, ...] = (
    (2.2, -6.6),
    (-1.2, -0.8),
    (2.6, -0.8),
    (-2.2, 6.6),
    (1.2, 0.8),
    (-2.6, 0.8),
)
FIRE_ALARM_MANUAL_POINTS: tuple[Point, ...] = (
    (-5.5, -3.5),
    (-4.8, -0.2),
    (-3.0, 2.4),
    (0.0, 3.2),
    (3.0, 2.4),
    (4.8, -0.2),
    (5.5, -3.5),
)
FIRE_ALARM_MANUAL_STEM: tuple[Point, Point] = ((0.0, 3.2), (0.0, 8.0))
EDITOR_SYMBOL_REFERENCE_SIZE = 18.0
EXIT_SIGN_RADIUS = 13.0
EXIT_SIGN_CROSS_RATIO = 7.0 / 13.0
SIREN_BODY_X = -10.2
SIREN_BODY_Y = -9.0
SIREN_BODY_WIDTH = 7.2
SIREN_BODY_HEIGHT = 18.0
SIREN_HORN_POINTS: tuple[Point, ...] = (
    (-3.0, -9.0),
    (9.6, -22.0),
    (9.6, 22.0),
    (-3.0, 9.0),
)
SIREN_HALF_WIDTH = 10.2
SIREN_HALF_HEIGHT = 22.0


@dataclass(frozen=True)
class PlanTransform:
    image_width: float
    image_height: float
    scale: float
    offset_x: float
    offset_y: float
    scale_factor: float
    rotation_quarter_turns: int = 0
    rotated_width: float | None = None
    rotated_height: float | None = None


def _normalize_quarter_turns(value: int) -> int:
    normalized = int(value) % 4
    return normalized if normalized >= 0 else normalized + 4


def _rotated_plan_size(
    image_width: float,
    image_height: float,
    rotation_quarter_turns: int,
) -> tuple[float, float]:
    normalized = _normalize_quarter_turns(rotation_quarter_turns)
    if normalized % 2 == 0:
        return image_width, image_height
    return image_height, image_width


def _rotate_plan_point(
    x: float,
    y: float,
    image_width: float,
    image_height: float,
    rotation_quarter_turns: int,
) -> tuple[float, float]:
    normalized = _normalize_quarter_turns(rotation_quarter_turns)
    center_x = image_width / 2.0
    center_y = image_height / 2.0
    translated_x = x - center_x
    translated_y = y - center_y

    if normalized == 1:
        rotated_x, rotated_y = -translated_y, translated_x
    elif normalized == 2:
        rotated_x, rotated_y = -translated_x, -translated_y
    elif normalized == 3:
        rotated_x, rotated_y = translated_y, -translated_x
    else:
        rotated_x, rotated_y = translated_x, translated_y

    rotated_width, rotated_height = _rotated_plan_size(image_width, image_height, normalized)
    return (rotated_x + (rotated_width / 2.0), rotated_y + (rotated_height / 2.0))


def _as_float(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def compute_plan_transform(
    floor_plan_data: dict,
    drawing_x: float,
    drawing_y: float,
    drawing_width: float,
    drawing_height: float,
    *,
    rotation_quarter_turns: int = 0,
) -> PlanTransform:
    image_width = max(1.0, _as_float(floor_plan_data.get("image_width"), 800.0))
    image_height = max(1.0, _as_float(floor_plan_data.get("image_height"), 600.0))
    rotated_width, rotated_height = _rotated_plan_size(image_width, image_height, rotation_quarter_turns)
    scale = min(drawing_width / rotated_width, drawing_height / rotated_height)
    scaled_width = rotated_width * scale
    scaled_height = rotated_height * scale
    offset_x = drawing_x + (drawing_width - scaled_width) / 2.0
    offset_y = drawing_y + (drawing_height - scaled_height) / 2.0
    scale_factor = max(1e-6, _as_float(floor_plan_data.get("scale_factor"), 1.0))
    return PlanTransform(
        image_width=image_width,
        image_height=image_height,
        scale=scale,
        offset_x=offset_x,
        offset_y=offset_y,
        scale_factor=scale_factor,
        rotation_quarter_turns=_normalize_quarter_turns(rotation_quarter_turns),
        rotated_width=rotated_width,
        rotated_height=rotated_height,
    )


def plan_point_to_pdf(x: float, y: float, transform: PlanTransform) -> Point:
    rotated_x, rotated_y = _rotate_plan_point(
        float(x),
        float(y),
        transform.image_width,
        transform.image_height,
        transform.rotation_quarter_turns,
    )
    return (
        transform.offset_x + rotated_x * transform.scale,
        transform.offset_y + rotated_y * transform.scale,
    )


def _clamp_channel(value: float) -> int:
    return max(0, min(255, int(round(value))))


def _hsl_to_hex(hue: float, saturation: float, lightness: float) -> str:
    hue = hue % 360.0
    saturation = max(0.0, min(100.0, saturation)) / 100.0
    lightness = max(0.0, min(100.0, lightness)) / 100.0
    chroma = (1.0 - abs((2.0 * lightness) - 1.0)) * saturation
    segment = hue / 60.0
    secondary = chroma * (1.0 - abs((segment % 2.0) - 1.0))
    offset = lightness - (chroma / 2.0)

    red = green = blue = 0.0
    if 0.0 <= segment < 1.0:
        red, green = chroma, secondary
    elif 1.0 <= segment < 2.0:
        red, green = secondary, chroma
    elif 2.0 <= segment < 3.0:
        green, blue = chroma, secondary
    elif 3.0 <= segment < 4.0:
        green, blue = secondary, chroma
    elif 4.0 <= segment < 5.0:
        red, blue = secondary, chroma
    else:
        red, blue = chroma, secondary

    return "#{:02x}{:02x}{:02x}".format(
        _clamp_channel((red + offset) * 255.0),
        _clamp_channel((green + offset) * 255.0),
        _clamp_channel((blue + offset) * 255.0),
    )


def _hex_to_rgba_color(hex_color: str, alpha: float = 1.0) -> colors.Color:
    normalized = hex_color.lstrip("#")
    if len(normalized) != 6:
        normalized = "7c3aed"
    red = int(normalized[0:2], 16) / 255.0
    green = int(normalized[2:4], 16) / 255.0
    blue = int(normalized[4:6], 16) / 255.0
    return colors.Color(red, green, blue, alpha=alpha)


def get_zkspc_style(zone_number: int, floor_plan_id: int | None = None) -> dict[str, object]:
    safe_zone = max(1, int(zone_number or 1))
    safe_floor = max(0, int(floor_plan_id or 0))
    seed = abs(((safe_floor + 1) * 92821) + (safe_zone * 68917))
    hue = (seed * 137.508) % 360.0
    color_hex = _hsl_to_hex(hue, 78.0, 44.0)
    return {
        "color_hex": color_hex,
        "fill_color": _hex_to_rgba_color(color_hex, alpha=0.14),
        "hatch_color": _hex_to_rgba_color(color_hex, alpha=0.78),
        "label_color": _hex_to_rgba_color(color_hex, alpha=1.0),
        "hatch_spacing": 18 + ((seed % 5) * 3),
        "label": f"ЗКСПС №{safe_zone}",
    }

ZKSPC_COLOR_PALETTE: tuple[str, ...] = (
    "#d94841",
    "#2563eb",
    "#15803d",
    "#f08c00",
    "#7c3aed",
    "#0f766e",
    "#c026d3",
    "#0891b2",
)

SOUE_COLOR_HEX = "#0000FF"
SOUE_COLOR = colors.HexColor(SOUE_COLOR_HEX)
COMMON_SIGNAL_SYSTEM = "common"
SUPPORTED_SIGNAL_SYSTEMS = {"addressable", "non_addressable", COMMON_SIGNAL_SYSTEM}
SUPPORTED_ACTIVE_SIGNAL_SYSTEMS = {"addressable", "non_addressable"}


DIMENSION_EXTENSION_LENGTH = 10.0 * mm
DIMENSION_LINE_OFFSET = 5.0 * mm
DIMENSION_PLAN_GUTTER = 34.0 * mm
DIMENSION_MIN_PLAN_WIDTH = 80.0 * mm
DIMENSION_MIN_PLAN_HEIGHT = 60.0 * mm
DRAWING_SAFE_MARGIN = 4.0 * mm
EXPLICATION_GAP = 4.0 * mm


@dataclass(frozen=True)
class ExteriorDimensionSpec:
    side: str
    orientation: str
    outer_coord: float
    anchors: tuple[float, ...]


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    normalized = str(hex_color or "").lstrip("#")
    if len(normalized) != 6:
        normalized = "7c3aed"
    return (
        int(normalized[0:2], 16),
        int(normalized[2:4], 16),
        int(normalized[4:6], 16),
    )


def _color_distance(hex_a: str, hex_b: str) -> float:
    red_a, green_a, blue_a = _hex_to_rgb(hex_a)
    red_b, green_b, blue_b = _hex_to_rgb(hex_b)
    return math.sqrt(
        ((red_a - red_b) ** 2) + ((green_a - green_b) ** 2) + ((blue_a - blue_b) ** 2)
    )


def _room_bounds_touch(
    bounds_a: tuple[float, float, float, float] | None,
    bounds_b: tuple[float, float, float, float] | None,
) -> bool:
    if bounds_a is None or bounds_b is None:
        return False
    tolerance = 14.0
    minimum_overlap = 18.0
    horizontal_overlap = min(bounds_a[2], bounds_b[2]) - max(bounds_a[0], bounds_b[0])
    vertical_overlap = min(bounds_a[3], bounds_b[3]) - max(bounds_a[1], bounds_b[1])
    return bool(
        (
            vertical_overlap >= minimum_overlap
            and (
                abs(bounds_a[2] - bounds_b[0]) <= tolerance
                or abs(bounds_b[2] - bounds_a[0]) <= tolerance
            )
        )
        or (
            horizontal_overlap >= minimum_overlap
            and (
                abs(bounds_a[3] - bounds_b[1]) <= tolerance
                or abs(bounds_b[3] - bounds_a[1]) <= tolerance
            )
        )
    )


def _zone_seed(zone_number: int, floor_plan_id: int | None = None) -> int:
    safe_zone = max(1, int(zone_number or 1))
    safe_floor = max(0, int(floor_plan_id or 0))
    return abs(((safe_floor + 1) * 92821) + (safe_zone * 68917))


def _build_zkspc_style(
    zone_number: int,
    color_hex: str,
    floor_plan_id: int | None = None,
) -> dict[str, object]:
    seed = _zone_seed(zone_number, floor_plan_id)
    return {
        "color_hex": color_hex,
        "fill_color": _hex_to_rgba_color(color_hex, alpha=0.14),
        "hatch_color": _hex_to_rgba_color(color_hex, alpha=0.78),
        "outline_color": _hex_to_rgba_color(color_hex, alpha=0.92),
        "label_color": colors.black,
        "hatch_spacing": 18 + ((seed % 5) * 3),
        "label": f"ЗКСПС №{max(1, int(zone_number or 1))}",
    }


def build_zkspc_style_map(floor_plan_data: dict | None) -> dict[int, dict[str, object]]:
    if not floor_plan_data:
        return {}

    floor_plan_id = int(floor_plan_data.get("id") or 0)
    zones = [
        zone
        for zone in (floor_plan_data.get("zkspc_zones") or [])
        if zone.get("zone_number") is not None
    ]
    if not zones:
        return {}

    rooms_by_id = {
        int(room["id"]): room
        for room in (floor_plan_data.get("rooms") or [])
        if room.get("id") is not None
    }
    zone_numbers = [max(1, int(zone.get("zone_number") or 1)) for zone in zones]
    adjacency: dict[int, set[int]] = {zone_number: set() for zone_number in zone_numbers}
    zone_room_bounds: dict[int, list[tuple[float, float, float, float]]] = {
        zone_number: [] for zone_number in zone_numbers
    }

    for zone in zones:
        zone_number = max(1, int(zone.get("zone_number") or 1))
        for room_id in zone.get("room_ids") or []:
            room = rooms_by_id.get(int(room_id))
            bounds = _room_bounds(room) if room else None
            if bounds is not None:
                zone_room_bounds[zone_number].append(bounds)

    for index, left_zone in enumerate(zone_numbers):
        for right_zone in zone_numbers[index + 1:]:
            if any(
                _room_bounds_touch(left_bounds, right_bounds)
                for left_bounds in zone_room_bounds.get(left_zone, [])
                for right_bounds in zone_room_bounds.get(right_zone, [])
            ):
                adjacency[left_zone].add(right_zone)
                adjacency[right_zone].add(left_zone)

    rotation_rank_cache: dict[int, dict[int, int]] = {}
    assigned_indexes: dict[int, int] = {}
    palette_usage = [0 for _ in ZKSPC_COLOR_PALETTE]
    zone_order = sorted(
        zone_numbers,
        key=lambda zone_number: (-len(adjacency[zone_number]), zone_number),
    )

    for zone_number in zone_order:
        seed_index = _zone_seed(zone_number, floor_plan_id) % len(ZKSPC_COLOR_PALETTE)
        if seed_index not in rotation_rank_cache:
            rotation_rank_cache[seed_index] = {
                ((seed_index + offset) % len(ZKSPC_COLOR_PALETTE)): offset
                for offset in range(len(ZKSPC_COLOR_PALETTE))
            }
        rotation_rank = rotation_rank_cache[seed_index]
        used_neighbor_indexes = {
            assigned_indexes[neighbor]
            for neighbor in adjacency[zone_number]
            if neighbor in assigned_indexes
        }
        candidates = [
            index
            for index in range(len(ZKSPC_COLOR_PALETTE))
            if index not in used_neighbor_indexes
        ] or list(range(len(ZKSPC_COLOR_PALETTE)))

        def candidate_key(color_index: int) -> tuple[float, int, int]:
            if used_neighbor_indexes:
                min_distance = min(
                    _color_distance(
                        ZKSPC_COLOR_PALETTE[color_index],
                        ZKSPC_COLOR_PALETTE[neighbor_index],
                    )
                    for neighbor_index in used_neighbor_indexes
                )
            else:
                min_distance = float("inf")
            return (-min_distance, palette_usage[color_index], rotation_rank[color_index])

        chosen_index = min(candidates, key=candidate_key)
        assigned_indexes[zone_number] = chosen_index
        palette_usage[chosen_index] += 1

    return {
        zone_number: _build_zkspc_style(
            zone_number,
            ZKSPC_COLOR_PALETTE[
                assigned_indexes.get(
                    zone_number,
                    _zone_seed(zone_number, floor_plan_id) % len(ZKSPC_COLOR_PALETTE),
                )
            ],
            floor_plan_id=floor_plan_id,
        )
        for zone_number in zone_numbers
    }


def get_zkspc_style(
    zone_number: int,
    floor_plan_id: int | None = None,
    *,
    style_map: dict[int, dict[str, object]] | None = None,
) -> dict[str, object]:
    safe_zone = max(1, int(zone_number or 1))
    if style_map and safe_zone in style_map:
        return style_map[safe_zone]
    color_index = _zone_seed(safe_zone, floor_plan_id) % len(ZKSPC_COLOR_PALETTE)
    return _build_zkspc_style(
        safe_zone,
        ZKSPC_COLOR_PALETTE[color_index],
        floor_plan_id=floor_plan_id,
    )


def _room_bounds(room: dict) -> tuple[float, float, float, float] | None:
    points = room.get("boundary_points") or []
    if len(points) < 3:
        return None
    xs = [float(point[0]) for point in points]
    ys = [float(point[1]) for point in points]
    return min(xs), min(ys), max(xs), max(ys)


def _room_center(room: dict) -> tuple[float, float] | None:
    if room.get("center_x") is not None and room.get("center_y") is not None:
        return float(room["center_x"]), float(room["center_y"])
    bounds = _room_bounds(room)
    if bounds is None:
        return None
    min_x, min_y, max_x, max_y = bounds
    return ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)


def build_room_numbering(rooms: list[dict]) -> list[dict[str, object]]:
    sortable: list[tuple[float, float, dict, tuple[float, float]]] = []
    for room in rooms:
        points = room.get("boundary_points") or []
        if len(points) < 3:
            continue
        center = _room_center(room)
        if center is None:
            continue
        sortable.append((center[1], center[0], room, center))

    numbered: list[dict[str, object]] = []
    for index, (_center_y, _center_x, room, center) in enumerate(sorted(sortable, key=lambda item: (item[0], item[1])), start=1):
        numbered.append(
            {
                "number": index,
                "room": room,
                "center": center,
                "name": room.get("name") or f"Помещение {index}",
                "area_sqm": round(float(room.get("area_sqm") or 0.0), 2),
            }
        )
    return numbered


def split_explication_rows(numbered_rooms: list[dict[str, object]], max_rows_per_part: int) -> list[list[dict[str, object]]]:
    if not numbered_rooms:
        return []
    if len(numbered_rooms) <= max_rows_per_part:
        return [numbered_rooms]
    midpoint = math.ceil(len(numbered_rooms) / 2.0)
    return [numbered_rooms[:midpoint], numbered_rooms[midpoint:]]


def compute_room_circle_radius(numbered_rooms: list[dict[str, object]], transform: PlanTransform) -> float:
    if not numbered_rooms:
        return 8.0
    candidates: list[float] = []
    for item in numbered_rooms:
        room = item["room"]
        bounds = _room_bounds(room)
        if bounds is None:
            continue
        min_span = min(bounds[2] - bounds[0], bounds[3] - bounds[1]) * transform.scale
        candidates.append(max(7.0, min_span * 0.16))
    if not candidates:
        return 8.0
    return max(7.0, min(16.0, min(candidates)))


def _point_in_polygon(point: Point, polygon: list[list[float]] | list[tuple[float, float]]) -> bool:
    if len(polygon) < 3:
        return False
    x, y = point
    inside = False
    prev_x, prev_y = polygon[-1]
    for current_x, current_y in polygon:
        on_segment = (
            abs((x - prev_x) * (current_y - prev_y) - (y - prev_y) * (current_x - prev_x)) < 1e-4
            and ((x - prev_x) * (x - current_x) + (y - prev_y) * (y - current_y)) <= 1e-4
        )
        if on_segment:
            return True
        intersects = ((prev_y > y) != (current_y > y)) and (
            x < (((current_x - prev_x) * (y - prev_y)) / ((current_y - prev_y) or 1e-9)) + prev_x
        )
        if intersects:
            inside = not inside
        prev_x, prev_y = current_x, current_y
    return inside


def _distance_to_segment(point: Point, start: Point, end: Point) -> float:
    px, py = point
    x1, y1 = start
    x2, y2 = end
    dx = x2 - x1
    dy = y2 - y1
    if abs(dx) < 1e-6 and abs(dy) < 1e-6:
        return math.hypot(px - x1, py - y1)
    projection = ((px - x1) * dx + (py - y1) * dy) / ((dx * dx) + (dy * dy))
    t = max(0.0, min(1.0, projection))
    closest_x = x1 + (dx * t)
    closest_y = y1 + (dy * t)
    return math.hypot(px - closest_x, py - closest_y)


def _distance_to_polygon_edges(point: Point, polygon: list[list[float]] | list[tuple[float, float]]) -> float:
    if len(polygon) < 2:
        return 0.0
    distances = [
        _distance_to_segment(
            point,
            (float(start[0]), float(start[1])),
            (float(end[0]), float(end[1])),
        )
        for start, end in zip(polygon, polygon[1:] + polygon[:1])
    ]
    return min(distances) if distances else 0.0


def find_room_badge_center(room: dict, radius: float, transform: PlanTransform) -> Point | None:
    points = room.get("boundary_points") or []
    bounds = _room_bounds(room)
    if len(points) < 3 or bounds is None:
        return _room_center(room)

    inset_px = max((radius / max(transform.scale, 1e-6)) + 6.0, 10.0)
    step_px = max(4.0, inset_px * 0.4)
    max_x = max(bounds[0] + inset_px, bounds[2] - inset_px)
    max_y = max(bounds[1] + inset_px, bounds[3] - inset_px)
    preferred_y = bounds[1] + inset_px

    row = 0
    candidate_y = preferred_y
    while candidate_y <= max_y + 1e-6:
        column = 0
        candidate_x = bounds[0] + inset_px
        while candidate_x <= max_x + 1e-6:
            candidate = (candidate_x, candidate_y)
            if _point_in_polygon(candidate, points) and _distance_to_polygon_edges(candidate, points) >= (inset_px * 0.78):
                return candidate
            column += 1
            candidate_x = bounds[0] + inset_px + (column * step_px)
        row += 1
        candidate_y = preferred_y + (row * step_px)

    center = _room_center(room)
    return center if center is not None else (bounds[0] + inset_px, bounds[1] + inset_px)


def _find_room_badge_rect(
    c,
    room: dict,
    text: str,
    radius: float,
    font_size: float,
    transform: PlanTransform,
    obstacles: list[dict[str, float]],
    bounds: dict[str, float] | None,
) -> dict[str, object] | None:
    preferred_center = find_room_badge_center(room, radius, transform) or _room_center(room)
    if preferred_center is None:
        return None
    points = room.get("boundary_points") or []
    region_constraint = {
        "polygons": [points] if len(points) >= 3 else [],
        "preferred_points": [preferred_center],
        "bounds": _room_bounds(room),
    }
    text_placement = _place_plan_text_pdf(
        c,
        text=str(text),
        font_size=font_size,
        anchor=preferred_center,
        obstacles=obstacles,
        bounds=bounds,
        strategy="region",
        region_constraint=region_constraint,
    )
    if text_placement is None or text_placement.get("rect") is None:
        return None
    center_x, center_y = _rect_center(text_placement["rect"])
    badge_rect = {
        "x": center_x - radius,
        "y": center_y - radius,
        "width": radius * 2.0,
        "height": radius * 2.0,
    }
    if any(_rects_intersect(badge_rect, obstacle) for obstacle in obstacles):
        return None
    if not _rect_inside_bounds(badge_rect, bounds):
        return None
    return {
        "rect": badge_rect,
        "leader_polyline": text_placement.get("leader_polyline"),
        "overflow": bool(text_placement.get("overflow")),
    }


def _oriented_fire_alarm_point(point: Point, device_type: str | None) -> Point:
    point_x, point_y = point
    if device_type == "manual_call_point":
        return point_x, -point_y
    return -point_x, point_y


def draw_fire_alarm_symbol(c, x: float, y: float, device_type: str | None, size: float = 4.5 * mm) -> None:
    half = size / 2.0
    scale = size / EDITOR_SYMBOL_REFERENCE_SIZE
    c.saveState()
    c.setStrokeColor(colors.red)
    c.setFillColor(colors.white)
    c.setLineWidth(max(0.7, size * 0.08))
    c.setLineCap(1)
    c.setLineJoin(1)
    c.rect(x - half, y - half, size, size, stroke=1, fill=1)

    if device_type == "manual_call_point":
        manual_path = c.beginPath()
        first_point = _oriented_fire_alarm_point(FIRE_ALARM_MANUAL_POINTS[0], device_type)
        manual_path.moveTo(x + (first_point[0] * scale), y + (first_point[1] * scale))
        for point_x, point_y in FIRE_ALARM_MANUAL_POINTS[1:]:
            point_x, point_y = _oriented_fire_alarm_point((point_x, point_y), device_type)
            manual_path.lineTo(x + (point_x * scale), y + (point_y * scale))
        stem_start = _oriented_fire_alarm_point(FIRE_ALARM_MANUAL_STEM[0], device_type)
        stem_end = _oriented_fire_alarm_point(FIRE_ALARM_MANUAL_STEM[1], device_type)
        c.drawPath(manual_path, stroke=1, fill=0)
        c.line(
            x + (stem_start[0] * scale),
            y + (stem_start[1] * scale),
            x + (stem_end[0] * scale),
            y + (stem_end[1] * scale),
        )
    else:
        auto_path = c.beginPath()
        first_point = _oriented_fire_alarm_point(FIRE_ALARM_AUTO_POINTS[0], device_type)
        auto_path.moveTo(x + (first_point[0] * scale), y + (first_point[1] * scale))
        for point_x, point_y in FIRE_ALARM_AUTO_POINTS[1:]:
            point_x, point_y = _oriented_fire_alarm_point((point_x, point_y), device_type)
            auto_path.lineTo(x + (point_x * scale), y + (point_y * scale))
        c.drawPath(auto_path, stroke=1, fill=0)

    c.restoreState()


def _rotate_half_extents(half_width: float, half_height: float, rotation_deg: float) -> tuple[float, float]:
    angle_rad = math.radians(float(rotation_deg or 0.0) % 360.0)
    sin_value = abs(math.sin(angle_rad))
    cos_value = abs(math.cos(angle_rad))
    return (
        (half_width * cos_value) + (half_height * sin_value),
        (half_width * sin_value) + (half_height * cos_value),
    )


def _soue_device_symbol_half_extents(
    device_type: str | None,
    size: float = 4.5 * mm,
    rotation_deg: float = 0.0,
) -> tuple[float, float]:
    scale = size / EDITOR_SYMBOL_REFERENCE_SIZE
    if device_type == "siren":
        return _rotate_half_extents(SIREN_HALF_WIDTH * scale, SIREN_HALF_HEIGHT * scale, rotation_deg)
    radius = EXIT_SIGN_RADIUS * scale
    return radius, radius


def draw_soue_device_symbol(
    c,
    x: float,
    y: float,
    device_type: str | None,
    size: float = 4.5 * mm,
    rotation_deg: float = 0.0,
) -> tuple[float, float]:
    stroke = SOUE_COLOR
    scale = size / EDITOR_SYMBOL_REFERENCE_SIZE
    half_width, half_height = _soue_device_symbol_half_extents(device_type, size, rotation_deg)
    c.saveState()
    c.translate(x, y)
    if device_type == "siren" and abs(float(rotation_deg or 0.0)) > 1e-6:
        c.rotate(float(rotation_deg))
    c.setStrokeColor(stroke)
    c.setFillColor(colors.white)
    c.setLineWidth(max(0.7, size * 0.08))

    if device_type == "siren":
        c.rect(
            SIREN_BODY_X * scale,
            SIREN_BODY_Y * scale,
            SIREN_BODY_WIDTH * scale,
            SIREN_BODY_HEIGHT * scale,
            stroke=1,
            fill=1,
        )
        horn_path = c.beginPath()
        first_point = SIREN_HORN_POINTS[0]
        horn_path.moveTo(first_point[0] * scale, first_point[1] * scale)
        for point_x, point_y in SIREN_HORN_POINTS[1:]:
            horn_path.lineTo(point_x * scale, point_y * scale)
        horn_path.close()
        c.drawPath(horn_path, stroke=1, fill=1)
        c.restoreState()
        return half_width, half_height

    c.circle(0.0, 0.0, half_width, stroke=1, fill=1)
    cross_offset = half_width * EXIT_SIGN_CROSS_RATIO
    c.line(-cross_offset, -cross_offset, cross_offset, cross_offset)
    c.line(-cross_offset, cross_offset, cross_offset, -cross_offset)
    c.restoreState()
    return half_width, half_height


def _get_fire_alarm_code(alarm: dict, floor_number: object | None, fallback_number: int = 1) -> str:
    floor_text = str(floor_number if floor_number is not None else 1).strip() or "1"
    prefix = "BTM" if alarm.get("device_type") == "manual_call_point" else "BTH"
    loop = str(alarm.get("zone") or 1).strip() or "1"
    address = str(alarm.get("address") or fallback_number).strip() or str(fallback_number)
    return f"{floor_text}{prefix}{loop}.{address}"


def _get_soue_device_code(device: dict, floor_number: object | None, fallback_number: int = 1) -> str:
    floor_text = str(floor_number if floor_number is not None else 1).strip() or "1"
    prefix = "BIAS1" if device.get("device_type") == "siren" else "BIAL2"
    device_number = str(device.get("device_number") or fallback_number).strip() or str(fallback_number)
    return f"{floor_text}{prefix}.{device_number}"


def _normalize_signal_system_type(value: object | None) -> str:
    normalized = str(value or "").strip()
    return normalized if normalized in SUPPORTED_SIGNAL_SYSTEMS else "non_addressable"


def _normalize_active_signal_system_type(value: object | None) -> str:
    normalized = _normalize_signal_system_type(value)
    return normalized if normalized in SUPPORTED_ACTIVE_SIGNAL_SYSTEMS else "non_addressable"


def _filter_items_by_system_type(items: list[dict], system_type: object | None) -> list[dict]:
    normalized_system_type = _normalize_signal_system_type(system_type)
    return [
        item
        for item in (items or [])
        if _normalize_signal_system_type(item.get("system_type")) == normalized_system_type
    ]


def _active_floor_plan_signal_system(floor_plan_data: dict) -> str:
    return _normalize_active_signal_system_type(floor_plan_data.get("active_signal_system_type"))


def _all_items_missing_system_type(items: list[dict]) -> bool:
    return bool(items) and all(not str(item.get("system_type") or "").strip() for item in items)


def _visible_signal_instruments_for_sheet(floor_plan_data: dict, sheet_kind: str) -> list[dict]:
    instruments = list(floor_plan_data.get("signal_instruments", []) or [])
    if sheet_kind in {"sps", "soue"}:
        common_instruments = _filter_items_by_system_type(instruments, COMMON_SIGNAL_SYSTEM)
        if common_instruments or not _all_items_missing_system_type(instruments):
            return common_instruments
    return instruments


def _visible_fire_alarms_for_sheet(floor_plan_data: dict, sheet_kind: str) -> list[dict]:
    alarms = list(floor_plan_data.get("fire_alarms", []) or [])
    if sheet_kind == "sps":
        return _filter_items_by_system_type(alarms, _active_floor_plan_signal_system(floor_plan_data))
    return alarms


def _visible_soue_devices_for_sheet(floor_plan_data: dict, sheet_kind: str) -> list[dict]:
    devices = list(floor_plan_data.get("soue_devices", []) or [])
    if sheet_kind == "soue":
        common_devices = _filter_items_by_system_type(devices, COMMON_SIGNAL_SYSTEM)
        if common_devices or not _all_items_missing_system_type(devices):
            return common_devices
    return devices


def _get_signal_instrument_label_text(instrument: dict | None) -> str | None:
    if not instrument:
        return None
    if instrument.get("instrument_type") == "control_panel":
        return ARK_LABEL_TEXT
    equipment_name = str(instrument.get("equipment_name") or "").strip()
    if equipment_name:
        return equipment_name
    explicit_name = str(instrument.get("name") or "").strip()
    if explicit_name:
        return explicit_name
    return None


def _soue_device_counter_key(device_type: object | None) -> str:
    return "siren" if str(device_type or "") == "siren" else "non_siren"


def _dedupe_signal_instruments_for_sheet(instruments: list[dict]) -> list[dict]:
    unique: list[dict] = []
    seen: set[tuple[str, int, int, str]] = set()
    for instrument in instruments:
        instrument_type = str(instrument.get("instrument_type") or "")
        signature = (
            instrument_type,
            int(round(float(instrument.get("x") or 0.0) * 10.0)),
            int(round(float(instrument.get("y") or 0.0) * 10.0)),
            "" if instrument_type == "control_panel" else str(instrument.get("name") or "").strip(),
        )
        if signature in seen:
            continue
        seen.add(signature)
        unique.append(instrument)
    return unique


def _measure_text_rect(
    c,
    center_x: float,
    center_y: float,
    text: str,
    font_size: float,
    padding_x: float = 3.0,
    rotation: float = 0.0,
) -> dict[str, float]:
    width = c.stringWidth(str(text or ""), DEFAULT_FONT_NAME, font_size) + (padding_x * 2.0)
    height = max(font_size + 2.0, font_size * 1.2)
    quarter_turn = int(round(rotation / 90.0)) % 4
    if quarter_turn in {1, 3}:
        width, height = height, width
    return {
        "x": center_x - (width / 2.0),
        "y": center_y - (height / 2.0),
        "width": width,
        "height": height,
    }


def _measure_text_rect_from_offset(
    c,
    anchor_x: float,
    anchor_y: float,
    text: str,
    font_size: float,
    dx: object | None,
    dy: object | None,
    padding_x: float = 3.0,
    rotation: float = 0.0,
) -> dict[str, float] | None:
    if dx is None or dy is None:
        return None
    width = c.stringWidth(str(text or ""), DEFAULT_FONT_NAME, font_size) + (padding_x * 2.0)
    height = max(font_size + 2.0, font_size * 1.2)
    quarter_turn = int(round(rotation / 90.0)) % 4
    if quarter_turn in {1, 3}:
        width, height = height, width
    return {
        "x": float(anchor_x) + float(dx),
        "y": float(anchor_y) + float(dy),
        "width": width,
        "height": height,
    }


def _rects_intersect(a: dict[str, float] | None, b: dict[str, float] | None) -> bool:
    if a is None or b is None:
        return False
    return not (
        a["x"] + a["width"] <= b["x"]
        or b["x"] + b["width"] <= a["x"]
        or a["y"] + a["height"] <= b["y"]
        or b["y"] + b["height"] <= a["y"]
    )


def _rect_inside_bounds(rect: dict[str, float] | None, bounds: dict[str, float] | None) -> bool:
    if rect is None or bounds is None:
        return True
    return (
        rect["x"] >= bounds["x"]
        and rect["y"] >= bounds["y"]
        and rect["x"] + rect["width"] <= bounds["x"] + bounds["width"]
        and rect["y"] + rect["height"] <= bounds["y"] + bounds["height"]
    )


def _inflate_rect(rect: dict[str, float] | None, padding: float) -> dict[str, float] | None:
    if rect is None:
        return None
    return {
        "x": rect["x"] - padding,
        "y": rect["y"] - padding,
        "width": rect["width"] + (padding * 2.0),
        "height": rect["height"] + (padding * 2.0),
    }


def _line_obstacle(start: Point, end: Point, padding: float = 4.0) -> dict[str, float]:
    return _inflate_rect(
        {
            "x": min(start[0], end[0]),
            "y": min(start[1], end[1]),
            "width": max(1.0, abs(end[0] - start[0])),
            "height": max(1.0, abs(end[1] - start[1])),
        },
        padding,
    )


def _polyline_obstacles(points: list[Point], padding: float = 4.0) -> list[dict[str, float]]:
    return [_line_obstacle(start, end, padding) for start, end in zip(points, points[1:])]


def _merge_rect_bounds(bounds_list: list[dict[str, float] | None]) -> dict[str, float] | None:
    valid = [bounds for bounds in bounds_list if bounds is not None]
    if not valid:
        return None
    min_x = min(bounds["x"] for bounds in valid)
    min_y = min(bounds["y"] for bounds in valid)
    max_x = max(bounds["x"] + bounds["width"] for bounds in valid)
    max_y = max(bounds["y"] + bounds["height"] for bounds in valid)
    return {
        "x": min_x,
        "y": min_y,
        "width": max_x - min_x,
        "height": max_y - min_y,
    }


def _rect_center(rect: dict[str, float]) -> Point:
    return rect["x"] + (rect["width"] / 2.0), rect["y"] + (rect["height"] / 2.0)


def _rect_contains_point(rect: dict[str, float] | None, point: Point) -> bool:
    if rect is None:
        return False
    return (
        point[0] >= rect["x"]
        and point[0] <= rect["x"] + rect["width"]
        and point[1] >= rect["y"]
        and point[1] <= rect["y"] + rect["height"]
    )


def _normalize_vector(vector: Point | None) -> Point | None:
    if vector is None:
        return None
    length = math.hypot(vector[0], vector[1])
    if length <= 1e-6:
        return None
    return vector[0] / length, vector[1] / length


def _build_direction_order(preferred_vector: Point | None) -> list[Point]:
    directions = [
        (1.0, 0.0),
        (math.sqrt(0.5), -math.sqrt(0.5)),
        (math.sqrt(0.5), math.sqrt(0.5)),
        (-1.0, 0.0),
        (-math.sqrt(0.5), -math.sqrt(0.5)),
        (-math.sqrt(0.5), math.sqrt(0.5)),
        (0.0, -1.0),
        (0.0, 1.0),
    ]
    normalized = _normalize_vector(preferred_vector)
    if normalized is None:
        return directions
    return sorted(directions, key=lambda item: -((item[0] * normalized[0]) + (item[1] * normalized[1])))


def _point_in_any_polygon(point: Point, polygons: list[list[list[float]] | list[tuple[float, float]]]) -> bool:
    if not polygons:
        return True
    return any(_point_in_polygon(point, polygon) for polygon in polygons if len(polygon) >= 3)


def _region_bounds(polygons: list[list[list[float]] | list[tuple[float, float]]]) -> dict[str, float] | None:
    return _merge_rect_bounds([
        (
            {
                "x": bounds[0],
                "y": bounds[1],
                "width": bounds[2] - bounds[0],
                "height": bounds[3] - bounds[1],
            }
            if bounds is not None
            else None
        )
        for polygon in polygons
        for bounds in [_room_bounds({"boundary_points": polygon}) if len(polygon) >= 3 else None]
    ])


def _rect_matches_region(rect: dict[str, float], region_constraint: dict[str, object] | None) -> bool:
    if region_constraint is None:
        return True
    center = _rect_center(rect)
    polygons = [
        polygon
        for polygon in region_constraint.get("polygons", [])
        if isinstance(polygon, list) and len(polygon) >= 3
    ]
    if not _point_in_any_polygon(center, polygons):
        return False
    bounds = region_constraint.get("bounds")
    return _rect_inside_bounds(rect, bounds if isinstance(bounds, dict) else None)


def _leader_polyline_candidates(anchor: Point, rect: dict[str, float]) -> list[list[Point]]:
    left_distance = abs(anchor[0] - rect["x"])
    right_distance = abs(anchor[0] - (rect["x"] + rect["width"]))
    top_distance = abs(anchor[1] - rect["y"])
    bottom_distance = abs(anchor[1] - (rect["y"] + rect["height"]))
    minimum = min(left_distance, right_distance, top_distance, bottom_distance)
    if minimum == left_distance:
        target = (rect["x"], min(max(anchor[1], rect["y"]), rect["y"] + rect["height"]))
    elif minimum == right_distance:
        target = (rect["x"] + rect["width"], min(max(anchor[1], rect["y"]), rect["y"] + rect["height"]))
    elif minimum == top_distance:
        target = (min(max(anchor[0], rect["x"]), rect["x"] + rect["width"]), rect["y"])
    else:
        target = (min(max(anchor[0], rect["x"]), rect["x"] + rect["width"]), rect["y"] + rect["height"])
    if abs(anchor[0] - target[0]) <= 1e-6 or abs(anchor[1] - target[1]) <= 1e-6:
        return [[anchor, target]]
    return [
        [anchor, (target[0], anchor[1]), target],
        [anchor, (anchor[0], target[1]), target],
    ]


def _leader_polyline_clear(polyline: list[Point], anchor: Point, rect: dict[str, float], obstacles: list[dict[str, float]]) -> bool:
    filtered = [obstacle for obstacle in obstacles if not _rect_contains_point(obstacle, anchor)]
    for leader_obstacle in _polyline_obstacles(polyline, 3.0):
        if any(_rects_intersect(leader_obstacle, obstacle) and not _rects_intersect(obstacle, rect) for obstacle in filtered):
            return False
    return True


def _build_overflow_candidates(anchor: Point, width: float, height: float, bounds: dict[str, float] | None) -> list[dict[str, float]]:
    if bounds is None:
        return []
    step = max(width * 0.55, height * 1.15, 18.0)
    side_offsets = [0.0]
    for index in range(1, 13):
        side_offsets.extend((-(index * step), index * step))
    side_specs = [
        {
            "distance": abs(anchor[1] - bounds["y"]),
            "builder": lambda offset: {
                "x": min(max(anchor[0] + offset - (width / 2.0), bounds["x"] + 8.0), bounds["x"] + bounds["width"] - width - 8.0),
                "y": bounds["y"] + 8.0,
                "width": width,
                "height": height,
            },
        },
        {
            "distance": abs((bounds["y"] + bounds["height"]) - anchor[1]),
            "builder": lambda offset: {
                "x": min(max(anchor[0] + offset - (width / 2.0), bounds["x"] + 8.0), bounds["x"] + bounds["width"] - width - 8.0),
                "y": bounds["y"] + bounds["height"] - height - 8.0,
                "width": width,
                "height": height,
            },
        },
        {
            "distance": abs(anchor[0] - bounds["x"]),
            "builder": lambda offset: {
                "x": bounds["x"] + 8.0,
                "y": min(max(anchor[1] + offset - (height / 2.0), bounds["y"] + 8.0), bounds["y"] + bounds["height"] - height - 8.0),
                "width": width,
                "height": height,
            },
        },
        {
            "distance": abs((bounds["x"] + bounds["width"]) - anchor[0]),
            "builder": lambda offset: {
                "x": bounds["x"] + bounds["width"] - width - 8.0,
                "y": min(max(anchor[1] + offset - (height / 2.0), bounds["y"] + 8.0), bounds["y"] + bounds["height"] - height - 8.0),
                "width": width,
                "height": height,
            },
        },
    ]
    candidates: list[dict[str, float]] = []
    for spec in sorted(side_specs, key=lambda item: float(item["distance"])):
        for offset in side_offsets:
            candidates.append(spec["builder"](offset))
    return candidates


def _place_plan_text_pdf(
    c,
    *,
    text: str,
    font_size: float,
    anchor: Point,
    obstacles: list[dict[str, float]],
    bounds: dict[str, float] | None,
    strategy: str = "anchor",
    symbol_half_width: float = 0.0,
    symbol_half_height: float = 0.0,
    preferred_offset: tuple[float, float] | None = None,
    preferred_vector: Point | None = None,
    preferred_side: int | None = None,
    segment: tuple[Point, Point] | None = None,
    region_constraint: dict[str, object] | None = None,
    rotation: float = 0.0,
) -> dict[str, object] | None:
    if not str(text or "").strip():
        return None
    base_rect = _measure_text_rect(c, anchor[0], anchor[1], text, font_size, rotation=rotation)
    width = base_rect["width"]
    height = base_rect["height"]
    candidates: list[dict[str, float]] = []
    if preferred_offset is not None:
        preferred_rect = _measure_text_rect_from_offset(
            c,
            anchor[0],
            anchor[1],
            text,
            font_size,
            preferred_offset[0],
            preferred_offset[1],
            rotation=rotation,
        )
        if preferred_rect is not None:
            candidates.append(preferred_rect)
            preferred_center = _rect_center(preferred_rect)
            preferred_vector = (
                preferred_center[0] - anchor[0],
                preferred_center[1] - anchor[1],
            )
    if strategy == "segment" and segment is not None:
        start, end = segment
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.hypot(dx, dy) or 1.0
        tangent = (dx / length, dy / length)
        normal = (-tangent[1], tangent[0])
        midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        tangent_step = max(width * 0.5, 18.0)
        tangent_offsets = [0.0, -tangent_step, tangent_step, -(tangent_step * 2.0), tangent_step * 2.0]
        signs = [-1, 1] if preferred_side == -1 else [1, -1] if preferred_side == 1 else [1, -1]
        normal_step = max(height * 0.75, 10.0)
        for sign in signs:
            for ring in range(6):
                for tangent_offset in tangent_offsets:
                    center_x = midpoint[0] + (normal[0] * sign * ((height / 2.0) + 8.0 + (ring * normal_step))) + (tangent[0] * tangent_offset)
                    center_y = midpoint[1] + (normal[1] * sign * ((height / 2.0) + 8.0 + (ring * normal_step))) + (tangent[1] * tangent_offset)
                    candidates.append(_measure_text_rect(c, center_x, center_y, text, font_size, rotation=rotation))
    elif strategy == "region":
        normalized_region = region_constraint or {}
        polygons = [
            polygon
            for polygon in normalized_region.get("polygons", [])
            if isinstance(polygon, list) and len(polygon) >= 3
        ]
        region_bounds = normalized_region.get("bounds")
        if not isinstance(region_bounds, dict):
            region_bounds = _region_bounds(polygons)
            if region_constraint is not None:
                region_constraint["bounds"] = region_bounds
        preferred_points = [
            tuple(point)
            for point in normalized_region.get("preferred_points", [])
            if point is not None
        ]
        for point in preferred_points:
            candidates.append(_measure_text_rect(c, float(point[0]), float(point[1]), text, font_size, rotation=rotation))
        if region_bounds is not None:
            step_x = max(width * 0.55, 12.0)
            step_y = max(height * 0.8, 12.0)
            y = region_bounds["y"] + (height / 2.0)
            while y <= region_bounds["y"] + region_bounds["height"] - (height / 2.0) + 1e-6:
                x = region_bounds["x"] + (width / 2.0)
                while x <= region_bounds["x"] + region_bounds["width"] - (width / 2.0) + 1e-6:
                    if _point_in_any_polygon((x, y), polygons):
                        candidates.append(_measure_text_rect(c, x, y, text, font_size, rotation=rotation))
                    x += step_x
                y += step_y
    else:
        for direction in _build_direction_order(preferred_vector):
            for ring in range(6):
                tangent_offsets = [0.0] if ring == 0 else [0.0, -(max(width, height) * 0.35), max(width, height) * 0.35]
                for tangent_offset in tangent_offsets:
                    normal = (-direction[1], direction[0])
                    center_x = anchor[0] + (direction[0] * (symbol_half_width + 8.0 + (width / 2.0) + (ring * max(10.0, min(width, height))))) + (normal[0] * tangent_offset)
                    center_y = anchor[1] + (direction[1] * (symbol_half_height + 8.0 + (height / 2.0) + (ring * max(10.0, min(width, height))))) + (normal[1] * tangent_offset)
                    candidates.append(_measure_text_rect(c, center_x, center_y, text, font_size, rotation=rotation))

    for candidate in candidates:
        if not _rect_inside_bounds(candidate, bounds):
            continue
        if not _rect_matches_region(candidate, region_constraint):
            continue
        if any(_rects_intersect(candidate, obstacle) for obstacle in obstacles):
            continue
        return {"rect": candidate, "leader_polyline": None, "overflow": False}

    for candidate in _build_overflow_candidates(anchor, width, height, bounds):
        if any(_rects_intersect(candidate, obstacle) for obstacle in obstacles):
            continue
        leader = next(
            (
                polyline
                for polyline in _leader_polyline_candidates(anchor, candidate)
                if _leader_polyline_clear(polyline, anchor, candidate, obstacles)
            ),
            None,
        )
        if leader is not None:
            return {"rect": candidate, "leader_polyline": leader, "overflow": True}
    return None


def _place_symbol_label(
    c,
    *,
    anchor_x: float,
    anchor_y: float,
    text: str,
    font_size: float,
    symbol_half_width: float,
    symbol_half_height: float,
    obstacles: list[dict[str, float]],
    bounds: dict[str, float] | None,
) -> dict[str, object] | None:
    return _place_plan_text_pdf(
        c,
        text=text,
        font_size=font_size,
        anchor=(anchor_x, anchor_y),
        obstacles=obstacles,
        bounds=bounds,
        strategy="anchor",
        symbol_half_width=symbol_half_width,
        symbol_half_height=symbol_half_height,
    )


def draw_signal_instrument_symbol(c, x: float, y: float, instrument_type: str | None, size: float = 6.0 * mm) -> tuple[float, float]:
    c.saveState()
    c.setStrokeColor(colors.black)
    c.setFillColor(colors.white)
    c.setLineWidth(0.9)
    if instrument_type == "control_panel":
        width = size * 1.6
        height = size * 0.8
        c.rect(x - (width / 2.0), y - (height / 2.0), width, height, stroke=1, fill=1)
        c.setFillColor(colors.black)
        c.rect(x - (width / 2.0), y - (height / 2.0), width / 2.0, height / 2.0, stroke=0, fill=1)
        c.restoreState()
        return width / 2.0, height / 2.0

    half = size / 2.0
    c.roundRect(x - half, y - half, size, size, 2.0, stroke=1, fill=1)
    c.setFont(DEFAULT_FONT_NAME, max(8.0, size * 0.42))
    c.setFillColor(colors.black)
    c.drawCentredString(x, y - (size * 0.17), "К" if instrument_type == "loop_controller" else "О")
    c.restoreState()
    return half, half


def _draw_zc_terminator(c, x: float, y: float, size: float = 10.8) -> tuple[float, float]:
    half = size / 2.0
    c.saveState()
    c.setStrokeColor(colors.red)
    c.setFillColor(colors.white)
    c.setLineWidth(1.4)
    c.rect(x - half, y - half, size, size, stroke=1, fill=1)
    c.line(x - (size * 0.25), y, x + (size * 0.25), y)
    c.restoreState()
    return half, half


def _segment_orientation(start: Point, end: Point) -> str | None:
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    if abs(dx) >= abs(dy) and abs(dx) > 1e-6:
        return "horizontal"
    if abs(dy) > 1e-6:
        return "vertical"
    return None


def _round_display_value(value: float) -> float:
    return round(float(value) * 1000.0) / 1000.0


def _segment_key(start: Point, end: Point) -> str | None:
    orientation = _segment_orientation(start, end)
    if orientation is None:
        return None
    if orientation == "horizontal":
        y = _round_display_value(start[1])
        x1 = _round_display_value(min(start[0], end[0]))
        x2 = _round_display_value(max(start[0], end[0]))
        return f"h:{y}:{x1}:{x2}"
    x = _round_display_value(start[0])
    y1 = _round_display_value(min(start[1], end[1]))
    y2 = _round_display_value(max(start[1], end[1]))
    return f"v:{x}:{y1}:{y2}"


def _spread_offsets(count: int, spacing_step: float = DISPLAY_ROUTE_SPACING) -> list[float]:
    if count <= 1:
        return [0.0]
    midpoint = (count - 1) / 2.0
    return [(index - midpoint) * spacing_step for index in range(count)]


def _offset_segment(start: Point, end: Point, offset: float) -> tuple[str | None, Point, Point]:
    orientation = _segment_orientation(start, end)
    if orientation is None or abs(offset) <= 1e-6:
        return orientation, (float(start[0]), float(start[1])), (float(end[0]), float(end[1]))
    if orientation == "horizontal":
        return orientation, (float(start[0]), float(start[1] + offset)), (float(end[0]), float(end[1] + offset))
    return orientation, (float(start[0] + offset), float(start[1])), (float(end[0] + offset), float(end[1]))


def _resolve_joint(previous_segment: tuple[str | None, Point, Point] | None, next_segment: tuple[str | None, Point, Point] | None) -> Point:
    if previous_segment is None:
        return next_segment[1] if next_segment is not None else (0.0, 0.0)
    if next_segment is None:
        return previous_segment[2]
    if previous_segment[0] == "horizontal" and next_segment[0] == "vertical":
        return (next_segment[1][0], previous_segment[2][1])
    if previous_segment[0] == "vertical" and next_segment[0] == "horizontal":
        return (previous_segment[2][0], next_segment[1][1])
    return (
        (previous_segment[2][0] + next_segment[1][0]) / 2.0,
        (previous_segment[2][1] + next_segment[1][1]) / 2.0,
    )


def _apply_route_offsets(polyline: list[Point], route_id: object, offset_lookup: dict[str, float]) -> list[Point]:
    if len(polyline) < 2:
        return polyline
    segments = []
    for segment_index in range(len(polyline) - 1):
        offset = offset_lookup.get(f"{route_id}:{segment_index}", 0.0)
        segments.append(_offset_segment(polyline[segment_index], polyline[segment_index + 1], offset))
    if not segments:
        return polyline
    display_points = [segments[0][1]]
    for segment_index in range(len(segments) - 1):
        display_points.append(_resolve_joint(segments[segment_index], segments[segment_index + 1]))
    display_points.append(segments[-1][2])
    return [(_round_display_value(point[0]), _round_display_value(point[1])) for point in display_points]


def build_display_cable_routes_pdf(
    routes: list[dict],
    transform: PlanTransform,
    *,
    spacing_step: float = DISPLAY_ROUTE_SPACING,
) -> dict[object, list[Point]]:
    prepared = []
    for route_index, route in enumerate(routes or []):
        route_id = route.get("id", f"route-{route_index}")
        pdf_polyline = [
            plan_point_to_pdf(float(point[0]), float(point[1]), transform)
            for point in (route.get("polyline_points") or [])
        ]
        prepared.append(
            {
                "route": route,
                "route_id": route_id,
                "route_index": route_index,
                "route_number": int(route.get("route_number") or 0),
                "polyline": pdf_polyline,
            }
        )

    groups: dict[str, list[dict[str, int | object]]] = {}
    for item in prepared:
        polyline = item["polyline"]
        for segment_index in range(len(polyline) - 1):
            key = _segment_key(polyline[segment_index], polyline[segment_index + 1])
            if key is None:
                continue
            groups.setdefault(key, []).append(
                {
                    "route_id": item["route_id"],
                    "route_index": item["route_index"],
                    "route_number": item["route_number"],
                    "segment_index": segment_index,
                }
            )

    offset_lookup: dict[str, float] = {}
    for entries in groups.values():
        if len(entries) < 2:
            continue
        ordered = sorted(
            entries,
            key=lambda entry: (
                int(entry["route_number"]),
                str(entry["route_id"]),
                int(entry["route_index"]),
            ),
        )
        offsets = _spread_offsets(len(ordered), spacing_step)
        for index, entry in enumerate(ordered):
            offset_lookup[f"{entry['route_id']}:{entry['segment_index']}"] = offsets[index]

    return {
        item["route_id"]: _apply_route_offsets(item["polyline"], item["route_id"], offset_lookup)
        for item in prepared
    }


def _terminal_direction(polyline: list[Point]) -> Point:
    if len(polyline) < 2:
        return (1.0, 0.0)
    end = polyline[-1]
    for index in range(len(polyline) - 2, -1, -1):
        start = polyline[index]
        dx = end[0] - start[0]
        dy = end[1] - start[1]
        length = math.hypot(dx, dy)
        if length > 1e-6:
            return dx / length, dy / length
    return (1.0, 0.0)


def _point_signature(point: Point | None) -> tuple[float, float] | None:
    if point is None:
        return None
    return round(float(point[0]), 3), round(float(point[1]), 3)


def _ordered_zc_sides(dx: float, dy: float) -> list[str]:
    if abs(dx) <= 1e-6 and abs(dy) <= 1e-6:
        return ["east", "north", "south", "west"]
    return [
        side
        for side, _score in sorted(
            (
                (side, -((vector[0] * dx) + (vector[1] * dy)))
                for side, vector in ZC_SIDE_VECTORS.items()
            ),
            key=lambda item: (item[1], item[0]),
        )
    ]


def _infer_used_zc_side(center_point: Point, polyline: list[Point]) -> str | None:
    center_signature = _point_signature(center_point)
    for point in reversed(polyline):
        if _point_signature(point) == center_signature:
            continue
        dx = float(point[0]) - float(center_point[0])
        dy = float(point[1]) - float(center_point[1])
        ordered = _ordered_zc_sides(dx, dy)
        return ordered[0] if ordered else None
    return None


def _zc_candidate_point(center_point: Point, side: str) -> Point:
    vector = ZC_SIDE_VECTORS.get(side, (1.0, 0.0))
    return (
        round(float(center_point[0]) + (vector[0] * ZC_ROUTE_OFFSET_PX), 3),
        round(float(center_point[1]) + (vector[1] * ZC_ROUTE_OFFSET_PX), 3),
    )


def _zc_candidate_obstacles(center_point: Point, candidate_point: Point) -> list[dict[str, float]]:
    return [
        obstacle
        for obstacle in (
            _line_obstacle(center_point, candidate_point, 3.0),
            _inflate_rect(
                {
                    "x": candidate_point[0] - ZC_SYMBOL_HALF_SIZE_PX,
                    "y": candidate_point[1] - ZC_SYMBOL_HALF_SIZE_PX,
                    "width": ZC_SYMBOL_HALF_SIZE_PX * 2.0,
                    "height": ZC_SYMBOL_HALF_SIZE_PX * 2.0,
                },
                1.0,
            ),
        )
        if obstacle is not None
    ]


def _resolve_zc_terminator_point_pdf(
    route: dict,
    display_polyline: list[Point],
    device_lookup: dict[object, Point],
    obstacles: list[dict[str, float]],
) -> Point | None:
    if not display_polyline:
        return None
    device_ids = route.get("device_ids") or []
    last_device_id = device_ids[-1] if device_ids else None
    center_point = device_lookup.get(last_device_id)
    raw_endpoint = display_polyline[-1]
    if center_point is None:
        return raw_endpoint

    base_polyline = display_polyline[:-1] if len(display_polyline) > 1 else list(display_polyline)
    reference_point = base_polyline[-1] if base_polyline else raw_endpoint
    blocked_side = _infer_used_zc_side(center_point, base_polyline)
    ordered_sides = _ordered_zc_sides(
        float(center_point[0]) - float(reference_point[0]),
        float(center_point[1]) - float(reference_point[1]),
    )
    if blocked_side in ordered_sides and len(ordered_sides) > 1:
        ordered_sides = [side for side in ordered_sides if side != blocked_side] + [blocked_side]

    device_obstacles = [
        _inflate_rect(
            {
                "x": device_point[0] - DETECTOR_SYMBOL_HALF_SIZE_PX,
                "y": device_point[1] - DETECTOR_SYMBOL_HALF_SIZE_PX,
                "width": DETECTOR_SYMBOL_HALF_SIZE_PX * 2.0,
                "height": DETECTOR_SYMBOL_HALF_SIZE_PX * 2.0,
            },
            1.0,
        )
        for device_id, device_point in device_lookup.items()
        if device_id != last_device_id
    ]

    for side in ordered_sides:
        candidate = _zc_candidate_point(center_point, side)
        candidate_obstacles = _zc_candidate_obstacles(center_point, candidate)
        if any(
            _rects_intersect(candidate_obstacle, obstacle)
            for candidate_obstacle in candidate_obstacles
            for obstacle in [*obstacles, *device_obstacles]
        ):
            continue
        return candidate

    return raw_endpoint


def _get_zc_label_layout_pdf(c, polyline: list[Point], obstacles: list[dict[str, float]], bounds: dict[str, float] | None) -> dict[str, object] | None:
    if not polyline:
        return None
    end = polyline[-1]
    return _place_plan_text_pdf(
        c,
        text=ZC_LABEL_TEXT,
        font_size=ZC_LABEL_FONT_SIZE,
        anchor=end,
        obstacles=obstacles,
        bounds=bounds,
        strategy="anchor",
        symbol_half_width=5.4,
        symbol_half_height=5.4,
        preferred_vector=_terminal_direction(polyline),
    )


def wall_thickness_px(wall: dict, scale_factor: float) -> float:
    thickness_mm = _as_float(wall.get("thickness"), 200.0)
    return max(1.0, thickness_mm / max(scale_factor, 1e-6))


def wall_normal_offsets_px(wall: dict, scale_factor: float) -> tuple[float, float]:
    thickness = wall_thickness_px(wall, scale_factor)
    half = thickness / 2.0
    return half, half


def _wall_axis(wall: dict) -> tuple[float, float, float, float, float]:
    x1 = _as_float(wall.get("x1"), 0.0)
    y1 = _as_float(wall.get("y1"), 0.0)
    x2 = _as_float(wall.get("x2"), 0.0)
    y2 = _as_float(wall.get("y2"), 0.0)
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return x1, y1, 1.0, 0.0, 0.0
    return x1, y1, dx / length, dy / length, length


def wall_polygon(wall: dict, scale_factor: float) -> np.ndarray:
    x1 = _as_float(wall.get("x1"), 0.0)
    y1 = _as_float(wall.get("y1"), 0.0)
    x2 = _as_float(wall.get("x2"), x1)
    y2 = _as_float(wall.get("y2"), y1)
    positive_offset, negative_offset = wall_normal_offsets_px(wall, scale_factor)
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)

    if length < 1e-6:
        thickness = positive_offset + negative_offset
        half = thickness / 2.0
        return np.array(
            [
                [x1 - half, y1 - half],
                [x1 + half, y1 - half],
                [x1 + half, y1 + half],
                [x1 - half, y1 + half],
            ],
            dtype=np.float32,
        )

    ux = dx / length
    uy = dy / length
    nx = -uy
    ny = ux
    return np.array(
        [
            [x1 + nx * positive_offset, y1 + ny * positive_offset],
            [x2 + nx * positive_offset, y2 + ny * positive_offset],
            [x2 - nx * negative_offset, y2 - ny * negative_offset],
            [x1 - nx * negative_offset, y1 - ny * negative_offset],
        ],
        dtype=np.float32,
    )


def build_wall_mask(
    walls: list[dict],
    image_width: int | float,
    image_height: int | float,
    scale_factor: float,
) -> np.ndarray:
    width = max(1, int(math.ceil(float(image_width))))
    height = max(1, int(math.ceil(float(image_height))))
    mask = np.zeros((height, width), dtype=np.uint8)
    for wall in walls:
        polygon = np.round(wall_polygon(wall, scale_factor)).astype(np.int32)
        cv2.fillPoly(mask, [polygon], 255)
    return mask


def extract_wall_contours(mask: np.ndarray) -> list[np.ndarray]:
    contours, _hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    return [contour.reshape(-1, 2).astype(np.float32) for contour in contours if len(contour) >= 2]


def simplify_wall_contour(contour: np.ndarray) -> np.ndarray:
    """Reduce raster stair-stepping before exporting the contour to vector PDF."""
    if len(contour) < 3:
        return contour
    approx = cv2.approxPolyDP(contour.reshape(-1, 1, 2), epsilon=0.8, closed=True)
    simplified = approx.reshape(-1, 2).astype(np.float32)
    return simplified if len(simplified) >= 2 else contour


def resolve_opening_wall(opening: dict, walls: list[dict], scale_factor: float) -> dict | None:
    if not walls:
        return None

    width = max(1.0, _as_float(opening.get("width"), 1.0))
    height = max(1.0, _as_float(opening.get("height"), 1.0))
    center_x = _as_float(opening.get("x"), 0.0) + width / 2.0
    center_y = _as_float(opening.get("y"), 0.0) + height / 2.0
    projection_margin = max(width, height, 1.0)

    def distance_to_wall(wall: dict) -> tuple[float, bool]:
        x1 = _as_float(wall.get("x1"), 0.0)
        y1 = _as_float(wall.get("y1"), 0.0)
        x2 = _as_float(wall.get("x2"), x1)
        y2 = _as_float(wall.get("y2"), y1)
        dx = x2 - x1
        dy = y2 - y1
        length = math.hypot(dx, dy)
        if length < 1e-6:
            return float("inf"), False

        ux = dx / length
        uy = dy / length
        nx = -uy
        ny = ux
        along = ((center_x - x1) * ux) + ((center_y - y1) * uy)
        signed = ((center_x - x1) * nx) + ((center_y - y1) * ny)
        positive_offset, negative_offset = wall_normal_offsets_px(wall, scale_factor)
        thickness = wall_thickness_px(wall, scale_factor)
        max_distance = max(thickness * 0.5, min(width, height, 40.0))
        within_projection = -projection_margin <= along <= (length + projection_margin)
        within_thickness = (
            signed >= (-negative_offset - max_distance)
            and signed <= (positive_offset + max_distance)
        )
        if signed < -negative_offset:
            distance = abs(signed + negative_offset)
        elif signed > positive_offset:
            distance = abs(signed - positive_offset)
        else:
            distance = 0.0
        return distance, within_projection and within_thickness

    wall_lookup = {wall.get("id"): wall for wall in walls}
    wall_id = opening.get("wall_id")
    if wall_id in wall_lookup:
        wall = wall_lookup[wall_id]
        _distance, fits = distance_to_wall(wall)
        if fits:
            return wall

    best_wall: dict | None = None
    best_distance = float("inf")
    for wall in walls:
        distance, fits = distance_to_wall(wall)
        if not fits:
            continue
        if distance < best_distance:
            best_wall = wall
            best_distance = distance
    return best_wall


def _opening_half_span(opening: dict, ux: float, uy: float) -> float:
    width = max(1.0, _as_float(opening.get("width"), 1.0))
    height = max(1.0, _as_float(opening.get("height"), 1.0))
    return (abs(ux) * width + abs(uy) * height) / 2.0


def _opening_boundary_segments(
    opening: dict,
    wall: dict,
    scale_factor: float,
) -> tuple[Segment, Segment] | None:
    _x1, _y1, ux, uy, length = _wall_axis(wall)
    if length < 1e-6:
        return None

    nx = -uy
    ny = ux
    positive_offset, negative_offset = wall_normal_offsets_px(wall, scale_factor)
    span = _opening_half_span(opening, ux, uy)
    center_x = _as_float(opening.get("x"), 0.0) + _as_float(opening.get("width"), 0.0) / 2.0
    center_y = (
        _as_float(opening.get("y"), 0.0)
        + _as_float(opening.get("height"), 0.0) / 2.0
    )

    start_center = (center_x - ux * span, center_y - uy * span)
    end_center = (center_x + ux * span, center_y + uy * span)
    start_segment = (
        (start_center[0] - nx * negative_offset, start_center[1] - ny * negative_offset),
        (start_center[0] + nx * positive_offset, start_center[1] + ny * positive_offset),
    )
    end_segment = (
        (end_center[0] - nx * negative_offset, end_center[1] - ny * negative_offset),
        (end_center[0] + nx * positive_offset, end_center[1] + ny * positive_offset),
    )
    return start_segment, end_segment


def build_door_symbol_segments(
    opening: dict,
    walls: list[dict],
    scale_factor: float,
) -> list[Segment]:
    wall = resolve_opening_wall(opening, walls, scale_factor)
    if wall is None:
        return []

    boundary_segments = _opening_boundary_segments(opening, wall, scale_factor)
    if boundary_segments is None:
        return []

    _x1, _y1, ux, uy, length = _wall_axis(wall)
    if length < 1e-6:
        return []

    nx = -uy
    ny = ux
    thickness = wall_thickness_px(wall, scale_factor)
    half_leaf = thickness / 2.0 + thickness * 0.75
    center_x = _as_float(opening.get("x"), 0.0) + _as_float(opening.get("width"), 0.0) / 2.0
    center_y = (
        _as_float(opening.get("y"), 0.0) + _as_float(opening.get("height"), 0.0) / 2.0
    )
    center_segment = (
        (center_x - nx * half_leaf, center_y - ny * half_leaf),
        (center_x + nx * half_leaf, center_y + ny * half_leaf),
    )
    return [boundary_segments[0], center_segment, boundary_segments[1]]


def build_window_symbol_segments(
    opening: dict,
    walls: list[dict],
    scale_factor: float,
) -> list[Segment]:
    wall = resolve_opening_wall(opening, walls, scale_factor)
    if wall is None:
        return []

    boundary_segments = _opening_boundary_segments(opening, wall, scale_factor)
    if boundary_segments is None:
        return []

    _x1, _y1, ux, uy, length = _wall_axis(wall)
    if length < 1e-6:
        return []

    nx = -uy
    ny = ux
    thickness = wall_thickness_px(wall, scale_factor)
    span = _opening_half_span(opening, ux, uy)
    inner_half_span = max(0.0, span * 0.9)
    normal_offset = thickness * 0.15
    center_x = _as_float(opening.get("x"), 0.0) + _as_float(opening.get("width"), 0.0) / 2.0
    center_y = _as_float(opening.get("y"), 0.0) + _as_float(opening.get("height"), 0.0) / 2.0

    window_segments: list[Segment] = [boundary_segments[0], boundary_segments[1]]
    for direction in (-1.0, 1.0):
        line_center_x = center_x + nx * normal_offset * direction
        line_center_y = center_y + ny * normal_offset * direction
        window_segments.append(
            (
                (line_center_x - ux * inner_half_span, line_center_y - uy * inner_half_span),
                (line_center_x + ux * inner_half_span, line_center_y + uy * inner_half_span),
            )
        )
    return window_segments


def _rotate_point(point: Point, center: Point, angle_deg: float) -> Point:
    radians = math.radians(angle_deg)
    cos_value = math.cos(radians)
    sin_value = math.sin(radians)
    translated_x = point[0] - center[0]
    translated_y = point[1] - center[1]
    return (
        center[0] + (translated_x * cos_value) - (translated_y * sin_value),
        center[1] + (translated_x * sin_value) + (translated_y * cos_value),
    )


def build_stair_segments(stair: dict) -> tuple[list[Point], list[Segment]]:
    x = _as_float(stair.get("x"), 0.0)
    y = _as_float(stair.get("y"), 0.0)
    width = max(1.0, _as_float(stair.get("width"), 1.0))
    height = max(1.0, _as_float(stair.get("height"), 1.0))
    rotation_deg = _as_float(stair.get("rotation_deg"), 0.0)
    step_count = max(2, int(_as_float(stair.get("step_count"), 5)))
    step_axis = stair.get("step_axis") or ("horizontal" if width >= height else "vertical")
    center = (x + (width / 2.0), y + (height / 2.0))

    outline = [
        (x, y),
        (x + width, y),
        (x + width, y + height),
        (x, y + height),
    ]
    rotated_outline = [_rotate_point(point, center, rotation_deg) for point in outline]

    step_segments: list[Segment] = []
    if step_axis == "horizontal":
        for index in range(1, step_count):
            local_x = x + ((width / step_count) * index)
            start = _rotate_point((local_x, y), center, rotation_deg)
            end = _rotate_point((local_x, y + height), center, rotation_deg)
            step_segments.append((start, end))
    else:
        for index in range(1, step_count):
            local_y = y + ((height / step_count) * index)
            start = _rotate_point((x, local_y), center, rotation_deg)
            end = _rotate_point((x + width, local_y), center, rotation_deg)
            step_segments.append((start, end))

    return rotated_outline, step_segments


def _wall_stroke_width(walls: list[dict], transform: PlanTransform) -> float:
    if not walls:
        return 0.7
    scaled = [wall_thickness_px(wall, transform.scale_factor) * transform.scale for wall in walls]
    median_thickness = float(np.median(np.array(scaled, dtype=np.float32)))
    return max(0.45, min(1.2, median_thickness * 0.09))


def _draw_segments(c, segments: list[Segment], transform: PlanTransform) -> None:
    for start, end in segments:
        x1, y1 = plan_point_to_pdf(start[0], start[1], transform)
        x2, y2 = plan_point_to_pdf(end[0], end[1], transform)
        c.line(x1, y1, x2, y2)


def _describe_wall_for_dimensions(wall: dict, scale_factor: float) -> dict[str, float | int | str]:
    x1 = _as_float(wall.get("x1"), 0.0)
    y1 = _as_float(wall.get("y1"), 0.0)
    x2 = _as_float(wall.get("x2"), x1)
    y2 = _as_float(wall.get("y2"), y1)
    dx = x2 - x1
    dy = y2 - y1
    thickness = wall_thickness_px(wall, scale_factor)
    polygon = wall_polygon(wall, scale_factor)
    orientation = "horizontal" if abs(dx) >= abs(dy) else "vertical"
    return {
        "id": int(wall.get("id") or 0),
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "center_x": (x1 + x2) / 2.0,
        "center_y": (y1 + y2) / 2.0,
        "min_x": float(np.min(polygon[:, 0])),
        "max_x": float(np.max(polygon[:, 0])),
        "min_y": float(np.min(polygon[:, 1])),
        "max_y": float(np.max(polygon[:, 1])),
        "thickness": thickness,
        "orientation": orientation,
    }


def _dedupe_sorted_positions(values: list[float], tolerance: float) -> list[float]:
    result: list[float] = []
    for value in sorted(float(item) for item in values):
        if not result or abs(value - result[-1]) > tolerance:
            result.append(value)
    return result


def build_exterior_dimension_specs(walls: list[dict], scale_factor: float) -> dict[str, ExteriorDimensionSpec]:
    if not walls:
        return {}

    descriptors = [_describe_wall_for_dimensions(wall, scale_factor) for wall in walls]
    bounds = {
        "min_x": min(float(descriptor["min_x"]) for descriptor in descriptors),
        "max_x": max(float(descriptor["max_x"]) for descriptor in descriptors),
        "min_y": min(float(descriptor["min_y"]) for descriptor in descriptors),
        "max_y": max(float(descriptor["max_y"]) for descriptor in descriptors),
    }
    median_thickness = float(np.median(np.array([float(item["thickness"]) for item in descriptors], dtype=np.float32)))
    external_tolerance = max(8.0, median_thickness * 0.65)
    touch_tolerance = max(5.0, median_thickness * 0.45)
    dedupe_tolerance = max(2.0, median_thickness * 0.16)

    horizontal_walls = [item for item in descriptors if item["orientation"] == "horizontal"]
    vertical_walls = [item for item in descriptors if item["orientation"] == "vertical"]

    top_walls = [item for item in horizontal_walls if abs(float(item["min_y"]) - bounds["min_y"]) <= external_tolerance]
    bottom_walls = [item for item in horizontal_walls if abs(float(item["max_y"]) - bounds["max_y"]) <= external_tolerance]
    left_walls = [item for item in vertical_walls if abs(float(item["min_x"]) - bounds["min_x"]) <= external_tolerance]
    right_walls = [item for item in vertical_walls if abs(float(item["max_x"]) - bounds["max_x"]) <= external_tolerance]

    top_inner = max((float(item["max_y"]) for item in top_walls), default=bounds["min_y"])
    bottom_inner = min((float(item["min_y"]) for item in bottom_walls), default=bounds["max_y"])
    left_inner = max((float(item["max_x"]) for item in left_walls), default=bounds["min_x"])
    right_inner = min((float(item["min_x"]) for item in right_walls), default=bounds["max_x"])

    top_axis_y = min((float(item["center_y"]) for item in top_walls), default=top_inner)
    bottom_axis_y = max((float(item["center_y"]) for item in bottom_walls), default=bottom_inner)
    left_axis_x = min((float(item["center_x"]) for item in left_walls), default=left_inner)
    right_axis_x = max((float(item["center_x"]) for item in right_walls), default=right_inner)

    left_ids = {int(item["id"]) for item in left_walls}
    right_ids = {int(item["id"]) for item in right_walls}
    top_ids = {int(item["id"]) for item in top_walls}
    bottom_ids = {int(item["id"]) for item in bottom_walls}

    def build_horizontal_spec(side: str, outer_coord: float, axis_y: float) -> ExteriorDimensionSpec | None:
        anchors = [bounds["min_x"], left_inner, right_inner, bounds["max_x"]]
        for descriptor in vertical_walls:
            descriptor_id = int(descriptor["id"])
            if descriptor_id in left_ids or descriptor_id in right_ids:
                continue
            end_distance = min(
                abs(float(descriptor["y1"]) - axis_y),
                abs(float(descriptor["y2"]) - axis_y),
            )
            if end_distance <= touch_tolerance:
                anchors.append(float(descriptor["center_x"]))
        unique = _dedupe_sorted_positions(
            [
                min(bounds["max_x"], max(bounds["min_x"], anchor))
                for anchor in anchors
            ],
            tolerance=dedupe_tolerance,
        )
        return ExteriorDimensionSpec(side=side, orientation="horizontal", outer_coord=outer_coord, anchors=tuple(unique)) if len(unique) >= 2 else None

    def build_vertical_spec(side: str, outer_coord: float, axis_x: float) -> ExteriorDimensionSpec | None:
        anchors = [bounds["min_y"], top_inner, bottom_inner, bounds["max_y"]]
        for descriptor in horizontal_walls:
            descriptor_id = int(descriptor["id"])
            if descriptor_id in top_ids or descriptor_id in bottom_ids:
                continue
            end_distance = min(
                abs(float(descriptor["x1"]) - axis_x),
                abs(float(descriptor["x2"]) - axis_x),
            )
            if end_distance <= touch_tolerance:
                anchors.append(float(descriptor["center_y"]))
        unique = _dedupe_sorted_positions(
            [
                min(bounds["max_y"], max(bounds["min_y"], anchor))
                for anchor in anchors
            ],
            tolerance=dedupe_tolerance,
        )
        return ExteriorDimensionSpec(side=side, orientation="vertical", outer_coord=outer_coord, anchors=tuple(unique)) if len(unique) >= 2 else None

    specs = {
        "top": build_horizontal_spec("top", bounds["min_y"], top_axis_y),
        "bottom": build_horizontal_spec("bottom", bounds["max_y"], bottom_axis_y),
        "left": build_vertical_spec("left", bounds["min_x"], left_axis_x),
        "right": build_vertical_spec("right", bounds["max_x"], right_axis_x),
    }
    return {side: spec for side, spec in specs.items() if spec is not None}


def choose_plan_rotation(
    floor_plan_data: dict,
    drawing_width: float,
    drawing_height: float,
) -> int:
    image_width = max(1.0, _as_float(floor_plan_data.get("image_width"), 800.0))
    image_height = max(1.0, _as_float(floor_plan_data.get("image_height"), 600.0))
    best_rotation = 0
    best_scale = -1.0

    for rotation_quarter_turns in (0, 1):
        rotated_width, rotated_height = _rotated_plan_size(
            image_width,
            image_height,
            rotation_quarter_turns,
        )
        scale = min(drawing_width / rotated_width, drawing_height / rotated_height)
        if scale > best_scale + 1e-9:
            best_scale = scale
            best_rotation = rotation_quarter_turns

    return best_rotation


class DrawingPage(Page):
    """DrawingPage-level configuration and drawing."""

    @staticmethod
    def _resolve_sheet_description(sheet_kind: str) -> str:
        mapping = {
            "zkspc": "План ЗКСПС",
            "sps": "План СПС",
            "soue": "План СОУЭ",
        }
        return mapping.get(sheet_kind, "Общие данные")

    def __init__(
        self,
        page_format: tuple[float, float] = PAGESIZE_A4,
        main_title_box_type: str = "1",
        creds: dict[str, str] = DEFAULT_CREDS_DICT,
        page_number: int = 1,
        borders_mm: dict[str, float] = DEFAULT_BORDERS,
        floor_plan_data: dict | None = None,
        title: str = "",
        sheet_kind: str = "generic",
    ):
        page_creds = dict(creds or {})
        page_creds["Title of the Drawing"] = self._resolve_sheet_description(sheet_kind)
        super().__init__(page_format, main_title_box_type, page_creds, page_number, borders_mm)
        self.floor_plan_data = floor_plan_data
        self.title = title
        self.sheet_kind = sheet_kind
        self.drawing_x = self.borders_mm["left"]
        self.drawing_y = self.borders_mm["bottom"] + MAIN_TITLE_BOX_DICT["1"][1] + 5 * mm
        self.drawing_width = self.page_width - self.borders_mm["left"] - self.borders_mm["right"]
        self.drawing_height = (
            self.page_height
            - self.borders_mm["top"]
            - self.borders_mm["bottom"]
            - MAIN_TITLE_BOX_DICT["1"][1]
            - 10 * mm
        )

    def _draw_walls(self, c, walls: list[dict], transform: PlanTransform) -> None:
        if not walls:
            return
        wall_mask = build_wall_mask(
            walls,
            transform.image_width,
            transform.image_height,
            transform.scale_factor,
        )
        wall_contours = extract_wall_contours(wall_mask)
        c.saveState()
        c.setStrokeColor(colors.black)
        c.setLineWidth(_wall_stroke_width(walls, transform))
        c.setLineCap(1)
        c.setLineJoin(1)
        for contour in wall_contours:
            contour = simplify_wall_contour(contour)
            path = c.beginPath()
            first_x, first_y = plan_point_to_pdf(contour[0][0], contour[0][1], transform)
            path.moveTo(first_x, first_y)
            for point in contour[1:]:
                pdf_x, pdf_y = plan_point_to_pdf(point[0], point[1], transform)
                path.lineTo(pdf_x, pdf_y)
            path.close()
            c.drawPath(path, stroke=1, fill=0)
        c.restoreState()

    def _draw_openings(self, c, openings: list[dict], walls: list[dict], transform: PlanTransform, *, builder) -> None:
        if not openings:
            return
        c.saveState()
        c.setStrokeColor(colors.black)
        c.setLineWidth(_wall_stroke_width(walls, transform))
        c.setLineCap(1)
        c.setLineJoin(1)
        for opening in openings:
            _draw_segments(c, builder(opening, walls, transform.scale_factor), transform)
        c.restoreState()

    def _draw_stairs(self, c, stairs: list[dict], transform: PlanTransform) -> None:
        if not stairs:
            return
        c.saveState()
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.7)
        c.setLineJoin(1)
        for stair in stairs:
            outline, step_segments = build_stair_segments(stair)
            path = c.beginPath()
            first_x, first_y = plan_point_to_pdf(outline[0][0], outline[0][1], transform)
            path.moveTo(first_x, first_y)
            for point in outline[1:]:
                pdf_x, pdf_y = plan_point_to_pdf(point[0], point[1], transform)
                path.lineTo(pdf_x, pdf_y)
            path.close()
            c.drawPath(path, stroke=1, fill=0)
            _draw_segments(c, step_segments, transform)
        c.restoreState()

    def _should_draw_exterior_dimensions(self) -> bool:
        return self.sheet_kind in {"generic", "zkspc", "sps", "soue"}

    def _resolve_dimension_gutters(
        self,
        drawing_width: float,
        drawing_height: float,
        walls: list[dict],
    ) -> dict[str, float]:
        if not walls or not self._should_draw_exterior_dimensions():
            return {"left": 0.0, "right": 0.0, "top": 0.0, "bottom": 0.0}
        horizontal_gutter = min(
            DIMENSION_PLAN_GUTTER,
            max(0.0, (drawing_width - DIMENSION_MIN_PLAN_WIDTH) / 2.0),
        )
        vertical_gutter = min(
            DIMENSION_PLAN_GUTTER,
            max(0.0, (drawing_height - DIMENSION_MIN_PLAN_HEIGHT) / 2.0),
        )
        return {
            "left": horizontal_gutter,
            "right": horizontal_gutter,
            "top": vertical_gutter,
            "bottom": vertical_gutter,
        }

    def _draw_dimension_arrow(self, c, tip: Point, direction: Point, size: float) -> None:
        dx, dy = direction
        length = math.hypot(dx, dy)
        if length < 1e-6 or size <= 0:
            return
        ux = dx / length
        uy = dy / length
        px = -uy
        py = ux
        base_x = tip[0] - (ux * size)
        base_y = tip[1] - (uy * size)
        half_width = size * 0.45
        path = c.beginPath()
        path.moveTo(tip[0], tip[1])
        path.lineTo(base_x + (px * half_width), base_y + (py * half_width))
        path.lineTo(base_x - (px * half_width), base_y - (py * half_width))
        path.close()
        c.drawPath(path, stroke=0, fill=1)

    def _draw_exterior_dimension_spec(
        self,
        c,
        spec: ExteriorDimensionSpec,
        transform: PlanTransform,
        line_width: float,
        placed_text_obstacles: list[dict[str, float]] | None = None,
    ) -> list[dict[str, float]]:
        local_text_obstacles: list[dict[str, float]] = list(placed_text_obstacles or [])
        dimension_text_bounds = _inflate_rect(
            self._plan_stage_bounds(transform),
            DIMENSION_LINE_OFFSET + DIMENSION_EXTENSION_LENGTH + max(DIMENSION_TEXT_FONT_SIZE * 3.0, 20.0),
        )
        c.saveState()
        c.setStrokeColor(colors.black)
        c.setFillColor(colors.black)
        c.setLineWidth(line_width)
        c.setLineCap(1)
        c.setLineJoin(1)
        plan_center_x, plan_center_y = plan_point_to_pdf(
            transform.image_width / 2.0,
            transform.image_height / 2.0,
            transform,
        )
        anchor_points = (
            [plan_point_to_pdf(anchor, spec.outer_coord, transform) for anchor in spec.anchors]
            if spec.orientation == "horizontal"
            else [plan_point_to_pdf(spec.outer_coord, anchor, transform) for anchor in spec.anchors]
        )
        if len(anchor_points) < 2:
            c.restoreState()
            return local_text_obstacles

        delta_x = abs(anchor_points[-1][0] - anchor_points[0][0])
        delta_y = abs(anchor_points[-1][1] - anchor_points[0][1])
        transformed_orientation = "horizontal" if delta_x >= delta_y else "vertical"

        if transformed_orientation == "horizontal":
            edge_y = sum(point[1] for point in anchor_points) / len(anchor_points)
            outward_sign = 1.0 if edge_y >= plan_center_y else -1.0
            dimension_y = edge_y + (outward_sign * DIMENSION_LINE_OFFSET)
            extension_end_y = edge_y + (outward_sign * DIMENSION_EXTENSION_LENGTH)

            for point_x, _point_y in anchor_points:
                c.line(point_x, edge_y, point_x, extension_end_y)

            for left_index in range(len(anchor_points) - 1):
                start_anchor = spec.anchors[left_index]
                end_anchor = spec.anchors[left_index + 1]
                start_x = anchor_points[left_index][0]
                end_x = anchor_points[left_index + 1][0]
                segment_length = abs(end_x - start_x)
                if segment_length < 0.5:
                    continue
                measured_mm = int(round(abs(end_anchor - start_anchor) * transform.scale_factor))
                if measured_mm <= 0:
                    continue
                label = str(measured_mm)
                label_width = c.stringWidth(label, DEFAULT_FONT_NAME, DIMENSION_TEXT_FONT_SIZE)
                fits_between_arrows = label_width <= max(0.0, segment_length - (2.0 * DIMENSION_ARROW_SIZE) - (2.0 * mm))
                ascent, descent = pdfmetrics.getAscentDescent(DEFAULT_FONT_NAME, DIMENSION_TEXT_FONT_SIZE)
                c.line(start_x, dimension_y, end_x, dimension_y)
                self._draw_dimension_arrow(c, (start_x, dimension_y), (1.0, 0.0), DIMENSION_ARROW_SIZE)
                self._draw_dimension_arrow(c, (end_x, dimension_y), (-1.0, 0.0), DIMENSION_ARROW_SIZE)
                c.setFont(DEFAULT_FONT_NAME, DIMENSION_TEXT_FONT_SIZE)
                preferred_center_x = (
                    (start_x + end_x) / 2.0
                    if fits_between_arrows
                    else max(start_x, end_x) + DIMENSION_ARROW_SIZE + (1.5 * mm) + (label_width / 2.0)
                )
                preferred_baseline_y = (
                    dimension_y + DIMENSION_TEXT_GAP + ascent
                    if outward_sign > 0
                    else dimension_y - DIMENSION_TEXT_GAP - ascent
                )
                preferred_metrics = _measure_text_rect(c, 0.0, 0.0, label, DIMENSION_TEXT_FONT_SIZE)
                preferred_rect = {
                    "x": preferred_center_x - (preferred_metrics["width"] / 2.0),
                    "y": preferred_baseline_y - (preferred_metrics["height"] * 0.62),
                    "width": preferred_metrics["width"],
                    "height": preferred_metrics["height"],
                }
                placement = _place_plan_text_pdf(
                    c,
                    text=label,
                    font_size=DIMENSION_TEXT_FONT_SIZE,
                    anchor=((start_x + end_x) / 2.0, dimension_y),
                    preferred_offset=(
                        preferred_rect["x"] - ((start_x + end_x) / 2.0),
                        preferred_rect["y"] - dimension_y,
                    ),
                    preferred_side=1 if outward_sign > 0 else -1,
                    segment=((start_x, dimension_y), (end_x, dimension_y)),
                    obstacles=local_text_obstacles,
                    bounds=dimension_text_bounds,
                    strategy="segment",
                )
                if placement is None or placement.get("rect") is None:
                    continue
                label_rect = placement["rect"]
                if placement.get("leader_polyline"):
                    c.saveState()
                    c.setLineWidth(max(0.4, line_width))
                    c.setDash(4, 3)
                    leader_path = c.beginPath()
                    leader_polyline = placement["leader_polyline"]
                    leader_path.moveTo(leader_polyline[0][0], leader_polyline[0][1])
                    for point in leader_polyline[1:]:
                        leader_path.lineTo(point[0], point[1])
                    c.drawPath(leader_path, stroke=1, fill=0)
                    c.restoreState()
                    local_text_obstacles.extend(_polyline_obstacles(leader_polyline, 2.0))
                c.drawCentredString(
                    label_rect["x"] + (label_rect["width"] / 2.0),
                    label_rect["y"] + (label_rect["height"] * 0.62),
                    label,
                )
                local_text_obstacles.append(label_rect)
        else:
            edge_x = sum(point[0] for point in anchor_points) / len(anchor_points)
            outward_sign = 1.0 if edge_x >= plan_center_x else -1.0
            dimension_x = edge_x + (outward_sign * DIMENSION_LINE_OFFSET)
            extension_end_x = edge_x + (outward_sign * DIMENSION_EXTENSION_LENGTH)

            for _point_x, point_y in anchor_points:
                c.line(edge_x, point_y, extension_end_x, point_y)

            for top_index in range(len(anchor_points) - 1):
                start_anchor = spec.anchors[top_index]
                end_anchor = spec.anchors[top_index + 1]
                start_y = anchor_points[top_index][1]
                end_y = anchor_points[top_index + 1][1]
                segment_length = abs(end_y - start_y)
                if segment_length < 0.5:
                    continue
                measured_mm = int(round(abs(end_anchor - start_anchor) * transform.scale_factor))
                if measured_mm <= 0:
                    continue
                label = str(measured_mm)
                label_width = c.stringWidth(label, DEFAULT_FONT_NAME, DIMENSION_TEXT_FONT_SIZE)
                fits_between_arrows = label_width <= max(0.0, segment_length - (2.0 * DIMENSION_ARROW_SIZE) - (2.0 * mm))
                c.line(dimension_x, start_y, dimension_x, end_y)
                self._draw_dimension_arrow(c, (dimension_x, start_y), (0.0, 1.0), DIMENSION_ARROW_SIZE)
                self._draw_dimension_arrow(c, (dimension_x, end_y), (0.0, -1.0), DIMENSION_ARROW_SIZE)
                preferred_center_y = (
                    (start_y + end_y) / 2.0
                    if fits_between_arrows
                    else max(start_y, end_y) + DIMENSION_ARROW_SIZE + (1.5 * mm) + (label_width / 2.0)
                )
                preferred_center_x = dimension_x + (outward_sign * DIMENSION_TEXT_GAP)
                preferred_rect = _measure_text_rect(
                    c,
                    preferred_center_x,
                    preferred_center_y,
                    label,
                    DIMENSION_TEXT_FONT_SIZE,
                    rotation=90.0,
                )
                placement = _place_plan_text_pdf(
                    c,
                    text=label,
                    font_size=DIMENSION_TEXT_FONT_SIZE,
                    anchor=(dimension_x, (start_y + end_y) / 2.0),
                    preferred_offset=(
                        preferred_rect["x"] - dimension_x,
                        preferred_rect["y"] - ((start_y + end_y) / 2.0),
                    ),
                    preferred_side=1 if outward_sign < 0 else -1,
                    segment=((dimension_x, start_y), (dimension_x, end_y)),
                    obstacles=local_text_obstacles,
                    bounds=dimension_text_bounds,
                    strategy="segment",
                    rotation=90.0,
                )
                if placement is None or placement.get("rect") is None:
                    continue
                label_rect = placement["rect"]
                if placement.get("leader_polyline"):
                    c.saveState()
                    c.setLineWidth(max(0.4, line_width))
                    c.setDash(4, 3)
                    leader_path = c.beginPath()
                    leader_polyline = placement["leader_polyline"]
                    leader_path.moveTo(leader_polyline[0][0], leader_polyline[0][1])
                    for point in leader_polyline[1:]:
                        leader_path.lineTo(point[0], point[1])
                    c.drawPath(leader_path, stroke=1, fill=0)
                    c.restoreState()
                    local_text_obstacles.extend(_polyline_obstacles(leader_polyline, 2.0))
                c.saveState()
                c.setFont(DEFAULT_FONT_NAME, DIMENSION_TEXT_FONT_SIZE)
                c.translate(label_rect["x"] + (label_rect["width"] / 2.0), label_rect["y"] + (label_rect["height"] / 2.0))
                c.rotate(90)
                c.drawCentredString(0.0, -(DIMENSION_TEXT_FONT_SIZE * 0.34), label)
                c.restoreState()
                local_text_obstacles.append(label_rect)

        c.restoreState()
        return local_text_obstacles

    def _draw_exterior_dimensions(self, c, walls: list[dict], transform: PlanTransform) -> list[dict[str, float]]:
        if not walls or not self._should_draw_exterior_dimensions():
            return []
        specs = build_exterior_dimension_specs(walls, transform.scale_factor)
        if not specs:
            return []
        line_width = max(0.25, _wall_stroke_width(walls, transform) * 0.5)
        placed_text_obstacles: list[dict[str, float]] = []
        for side in ("top", "bottom", "left", "right"):
            spec = specs.get(side)
            if spec is not None:
                placed_text_obstacles = self._draw_exterior_dimension_spec(
                    c,
                    spec,
                    transform,
                    line_width,
                    placed_text_obstacles=placed_text_obstacles,
                )
        return placed_text_obstacles

    def _draw_fire_alarms(self, c, fire_alarms: list[dict], transform: PlanTransform) -> None:
        for alarm in fire_alarms:
            x, y = plan_point_to_pdf(alarm["x"], alarm["y"], transform)
            draw_fire_alarm_symbol(c, x, y, alarm.get("device_type"))

    def _draw_soue_devices(self, c, devices: list[dict], transform: PlanTransform) -> None:
        for device in devices:
            x, y = plan_point_to_pdf(device["x"], device["y"], transform)
            draw_soue_device_symbol(
                c,
                x,
                y,
                device.get("device_type"),
                rotation_deg=_as_float(device.get("rotation_deg"), 0.0),
            )

    def _plan_stage_bounds(self, transform: PlanTransform) -> dict[str, float]:
        corners = [
            plan_point_to_pdf(0.0, 0.0, transform),
            plan_point_to_pdf(transform.image_width, 0.0, transform),
            plan_point_to_pdf(transform.image_width, transform.image_height, transform),
            plan_point_to_pdf(0.0, transform.image_height, transform),
        ]
        xs = [point[0] for point in corners]
        ys = [point[1] for point in corners]
        return {
            "x": min(xs),
            "y": min(ys),
            "width": max(xs) - min(xs),
            "height": max(ys) - min(ys),
        }

    def _collect_geometry_obstacles(
        self,
        walls: list[dict],
        doors: list[dict],
        windows: list[dict],
        stairs: list[dict],
        transform: PlanTransform,
    ) -> list[dict[str, float]]:
        obstacles: list[dict[str, float]] = []
        for wall in walls:
            polygon = wall_polygon(wall, transform.scale_factor)
            pdf_points = [plan_point_to_pdf(float(point[0]), float(point[1]), transform) for point in polygon]
            xs = [point[0] for point in pdf_points]
            ys = [point[1] for point in pdf_points]
            obstacles.append(_inflate_rect({
                "x": min(xs),
                "y": min(ys),
                "width": max(xs) - min(xs),
                "height": max(ys) - min(ys),
            }, 2.0))

        for opening in doors:
            for start, end in build_door_symbol_segments(opening, walls, transform.scale_factor):
                obstacles.append(_line_obstacle(plan_point_to_pdf(start[0], start[1], transform), plan_point_to_pdf(end[0], end[1], transform), 3.0))
        for opening in windows:
            for start, end in build_window_symbol_segments(opening, walls, transform.scale_factor):
                obstacles.append(_line_obstacle(plan_point_to_pdf(start[0], start[1], transform), plan_point_to_pdf(end[0], end[1], transform), 3.0))
        for stair in stairs:
            outline, step_segments = build_stair_segments(stair)
            outline_pdf = [plan_point_to_pdf(point[0], point[1], transform) for point in outline]
            xs = [point[0] for point in outline_pdf]
            ys = [point[1] for point in outline_pdf]
            obstacles.append(_inflate_rect({
                "x": min(xs),
                "y": min(ys),
                "width": max(xs) - min(xs),
                "height": max(ys) - min(ys),
            }, 3.0))
            for start, end in step_segments:
                obstacles.append(_line_obstacle(plan_point_to_pdf(start[0], start[1], transform), plan_point_to_pdf(end[0], end[1], transform), 2.0))
        return [obstacle for obstacle in obstacles if obstacle is not None]

    def _draw_cable_routes(
        self,
        c,
        routes: list[dict],
        transform: PlanTransform,
        *,
        base_obstacles: list[dict[str, float]],
        stage_bounds: dict[str, float],
        device_lookup: dict[object, Point] | None = None,
    ) -> list[dict[str, float]]:
        if not routes:
            return []

        display_map = build_display_cable_routes_pdf(
            routes,
            transform,
            spacing_step=PDF_CABLE_ROUTE_STROKE_WIDTH,
        )
        normalized_device_lookup = device_lookup or {}
        base_route_obstacles: list[dict[str, float]] = []
        route_display_data: dict[object, dict[str, object]] = {}
        for route in routes:
            route_id = route.get("id")
            display_polyline = display_map.get(route_id, [])
            base_polyline = display_polyline[:-1] if should_show_zc_terminator(route) and len(display_polyline) > 1 else display_polyline
            base_route_obstacles.extend(_polyline_obstacles(base_polyline, 3.0))
            if base_polyline:
                base_route_obstacles.append(_inflate_rect(_measure_text_rect(c, base_polyline[-1][0], base_polyline[-1][1], "", 10.8), 4.0))

        placed_zc_obstacles: list[dict[str, float]] = []
        for route in routes:
            route_id = route.get("id")
            display_polyline = display_map.get(route_id, [])
            should_show_zc = should_show_zc_terminator(route)
            base_polyline = display_polyline[:-1] if should_show_zc and len(display_polyline) > 1 else display_polyline
            zc_point = (
                _resolve_zc_terminator_point_pdf(
                    route,
                    display_polyline,
                    normalized_device_lookup,
                    base_obstacles + base_route_obstacles + placed_zc_obstacles,
                )
                if should_show_zc and display_polyline
                else None
            )
            final_polyline = [*base_polyline, zc_point] if zc_point is not None else list(base_polyline)
            own_tail_obstacles = _zc_candidate_obstacles(base_polyline[-1], zc_point) if zc_point is not None and base_polyline else []
            route_display_data[route_id] = {
                "polyline": final_polyline,
                "zc_point": zc_point,
                "own_tail_obstacles": own_tail_obstacles,
            }
            placed_zc_obstacles.extend(own_tail_obstacles)

        route_obstacles = base_route_obstacles + placed_zc_obstacles

        c.saveState()
        c.setLineWidth(PDF_CABLE_ROUTE_STROKE_WIDTH)
        c.setLineCap(1)
        c.setLineJoin(1)
        for route in routes:
            route_id = route.get("id")
            display_polyline = route_display_data.get(route_id, {}).get("polyline", display_map.get(route_id, []))
            if len(display_polyline) < 2:
                continue
            route_color = SOUE_COLOR if str(route.get("subsystem_type") or "sps") == "soue" else colors.red
            c.setStrokeColor(route_color)
            path = c.beginPath()
            path.moveTo(display_polyline[0][0], display_polyline[0][1])
            for point in display_polyline[1:]:
                path.lineTo(point[0], point[1])
            c.drawPath(path, stroke=1, fill=0)
            should_show_zc = should_show_zc_terminator(route)
            if should_show_zc:
                zc_point = route_display_data.get(route_id, {}).get("zc_point") or display_polyline[-1]
                _draw_zc_terminator(c, zc_point[0], zc_point[1])
        c.restoreState()

        placed_obstacles: list[dict[str, float]] = []
        for route in routes:
            route_id = route.get("id")
            display_polyline = route_display_data.get(route_id, {}).get("polyline", display_map.get(route_id, []))
            should_show_zc = should_show_zc_terminator(route)
            if not should_show_zc or not display_polyline:
                continue
            anchor_x, anchor_y = display_polyline[-1]
            own_tail_obstacles = route_display_data.get(route_id, {}).get("own_tail_obstacles", [])
            placement = (
                _place_plan_text_pdf(
                    c,
                    text=ZC_LABEL_TEXT,
                    font_size=ZC_LABEL_FONT_SIZE,
                    anchor=(anchor_x, anchor_y),
                    obstacles=base_obstacles + [
                        obstacle
                        for obstacle in route_obstacles
                        if obstacle not in own_tail_obstacles
                    ] + placed_obstacles,
                    bounds=stage_bounds,
                    strategy="anchor",
                    symbol_half_width=5.4,
                    symbol_half_height=5.4,
                    preferred_vector=_terminal_direction(display_polyline),
                    preferred_offset=(
                        (float(route.get("zc_label_dx")), float(route.get("zc_label_dy")))
                        if route.get("zc_label_dx") is not None and route.get("zc_label_dy") is not None
                        else None
                    ),
                )
                or _get_zc_label_layout_pdf(
                    c,
                    display_polyline,
                    base_obstacles + [
                        obstacle
                        for obstacle in route_obstacles
                        if obstacle not in own_tail_obstacles
                    ] + placed_obstacles,
                    stage_bounds,
                )
            )
            if placement is None or placement.get("rect") is None:
                continue
            label_rect = placement["rect"]
            label_color = SOUE_COLOR if str(route.get("subsystem_type") or "sps") == "soue" else colors.red
            if placement.get("leader_polyline"):
                c.saveState()
                c.setStrokeColor(label_color)
                c.setLineWidth(0.8)
                c.setDash(4, 3)
                leader_path = c.beginPath()
                leader_polyline = placement["leader_polyline"]
                leader_path.moveTo(leader_polyline[0][0], leader_polyline[0][1])
                for point in leader_polyline[1:]:
                    leader_path.lineTo(point[0], point[1])
                c.drawPath(leader_path, stroke=1, fill=0)
                c.restoreState()
                placed_obstacles.extend(_polyline_obstacles(leader_polyline, 3.0))
            c.saveState()
            c.setFont(DEFAULT_FONT_NAME, ZC_LABEL_FONT_SIZE)
            c.setFillColor(label_color)
            c.drawCentredString(
                label_rect["x"] + (label_rect["width"] / 2.0),
                label_rect["y"] + (label_rect["height"] * 0.14),
                ZC_LABEL_TEXT,
            )
            c.restoreState()
            placed_obstacles.append(label_rect)
        return route_obstacles + placed_obstacles

    def _draw_signal_instruments(
        self,
        c,
        instruments: list[dict],
        transform: PlanTransform,
        *,
        obstacles: list[dict[str, float]],
        stage_bounds: dict[str, float],
    ) -> list[dict[str, float]]:
        if not instruments:
            return []

        symbol_obstacles: list[dict[str, float]] = []
        control_labels: list[tuple[dict, dict[str, float], tuple[float, float], str]] = []
        for instrument in instruments:
            x, y = plan_point_to_pdf(instrument["x"], instrument["y"], transform)
            half_width, half_height = draw_signal_instrument_symbol(c, x, y, instrument.get("instrument_type"))
            symbol_obstacles.append({
                "x": x - half_width,
                "y": y - half_height,
                "width": half_width * 2.0,
                "height": half_height * 2.0,
            })
            label_text = _get_signal_instrument_label_text(instrument)
            if label_text:
                control_labels.append((instrument, {"x": x, "y": y}, (half_width, half_height), label_text))

        placed_obstacles: list[dict[str, float]] = []
        for instrument, anchor, halves, label_text in control_labels:
            placement = _place_plan_text_pdf(
                c,
                text=label_text,
                font_size=SIGNAL_LABEL_FONT_SIZE,
                anchor=(anchor["x"], anchor["y"]),
                preferred_offset=(
                    (float(instrument.get("label_dx")), float(instrument.get("label_dy")))
                    if instrument.get("label_dx") is not None and instrument.get("label_dy") is not None
                    else None
                ),
                symbol_half_width=halves[0],
                symbol_half_height=halves[1],
                obstacles=obstacles + symbol_obstacles + placed_obstacles,
                bounds=stage_bounds,
            )
            if placement is None or placement.get("rect") is None:
                fallback_rect = _measure_text_rect_from_offset(
                    c,
                    anchor["x"],
                    anchor["y"],
                    label_text,
                    SIGNAL_LABEL_FONT_SIZE,
                    halves[0] + 8.0,
                    -(SIGNAL_LABEL_FONT_SIZE + 2.0),
                )
                if fallback_rect is None:
                    continue
                placement = {"rect": fallback_rect}
            label_rect = placement["rect"]
            if placement.get("leader_polyline"):
                c.saveState()
                c.setStrokeColor(colors.black)
                c.setLineWidth(0.8)
                c.setDash(4, 3)
                leader_path = c.beginPath()
                leader_polyline = placement["leader_polyline"]
                leader_path.moveTo(leader_polyline[0][0], leader_polyline[0][1])
                for point in leader_polyline[1:]:
                    leader_path.lineTo(point[0], point[1])
                c.drawPath(leader_path, stroke=1, fill=0)
                c.restoreState()
                placed_obstacles.extend(_polyline_obstacles(leader_polyline, 3.0))
            c.saveState()
            c.setFont(DEFAULT_FONT_NAME, SIGNAL_LABEL_FONT_SIZE)
            c.setFillColor(colors.black)
            c.drawCentredString(
                label_rect["x"] + (label_rect["width"] / 2.0),
                label_rect["y"] + (label_rect["height"] * 0.14),
                label_text,
            )
            c.restoreState()
            placed_obstacles.append(label_rect)
        return symbol_obstacles + placed_obstacles

    def _draw_soue_device_annotations(
        self,
        c,
        devices: list[dict],
        floor_number: object | None,
        transform: PlanTransform,
        *,
        obstacles: list[dict[str, float]],
        stage_bounds: dict[str, float],
    ) -> list[dict[str, float]]:
        if not devices:
            return []

        symbol_obstacles: list[dict[str, float]] = []
        labels: list[tuple[dict, dict[str, float], tuple[float, float], str]] = []
        type_counts: dict[str, int] = {"siren": 0, "non_siren": 0}
        for device in devices:
            x, y = plan_point_to_pdf(device["x"], device["y"], transform)
            rotation_deg = _as_float(device.get("rotation_deg"), 0.0)
            half_width, half_height = _soue_device_symbol_half_extents(
                device.get("device_type"),
                rotation_deg=rotation_deg,
            )
            symbol_obstacles.append({
                "x": x - half_width,
                "y": y - half_height,
                "width": half_width * 2.0,
                "height": half_height * 2.0,
            })
            counter_key = _soue_device_counter_key(device.get("device_type"))
            type_counts[counter_key] = type_counts.get(counter_key, 0) + 1
            label_text = _get_soue_device_code(device, floor_number, type_counts[counter_key])
            if label_text:
                labels.append((device, {"x": x, "y": y}, (half_width, half_height), label_text))

        placed_obstacles: list[dict[str, float]] = []
        label_color = SOUE_COLOR
        for device, anchor, halves, label_text in labels:
            placement = _place_plan_text_pdf(
                c,
                text=label_text,
                font_size=SIGNAL_LABEL_FONT_SIZE,
                anchor=(anchor["x"], anchor["y"]),
                preferred_offset=(
                    (float(device.get("label_dx")), float(device.get("label_dy")))
                    if device.get("label_dx") is not None and device.get("label_dy") is not None
                    else None
                ),
                symbol_half_width=halves[0],
                symbol_half_height=halves[1],
                obstacles=obstacles + symbol_obstacles + placed_obstacles,
                bounds=stage_bounds,
            )
            if placement is None or placement.get("rect") is None:
                continue
            label_rect = placement["rect"]
            if placement.get("leader_polyline"):
                c.saveState()
                c.setStrokeColor(label_color)
                c.setLineWidth(0.8)
                c.setDash(4, 3)
                leader_path = c.beginPath()
                leader_polyline = placement["leader_polyline"]
                leader_path.moveTo(leader_polyline[0][0], leader_polyline[0][1])
                for point in leader_polyline[1:]:
                    leader_path.lineTo(point[0], point[1])
                c.drawPath(leader_path, stroke=1, fill=0)
                c.restoreState()
                placed_obstacles.extend(_polyline_obstacles(leader_polyline, 3.0))
            c.saveState()
            c.setFont(DEFAULT_FONT_NAME, SIGNAL_LABEL_FONT_SIZE)
            c.setFillColor(label_color)
            c.drawCentredString(
                label_rect["x"] + (label_rect["width"] / 2.0),
                label_rect["y"] + (label_rect["height"] * 0.14),
                label_text,
            )
            c.restoreState()
            placed_obstacles.append(label_rect)
        return symbol_obstacles + placed_obstacles

    def _sheet_signal_routes(self, floor_plan_data: dict) -> list[dict]:
        routes = list(floor_plan_data.get("cable_routes", []) or [])
        if self.sheet_kind == "soue":
            common_routes = [
                route
                for route in _filter_items_by_system_type(routes, COMMON_SIGNAL_SYSTEM)
                if str(route.get("subsystem_type") or "sps") == "soue"
            ]
            if common_routes or not _all_items_missing_system_type(routes):
                return common_routes
            return [route for route in routes if str(route.get("subsystem_type") or "sps") == "soue"]
        if self.sheet_kind == "sps":
            return [
                route
                for route in _filter_items_by_system_type(routes, _active_floor_plan_signal_system(floor_plan_data))
                if str(route.get("subsystem_type") or "sps") == "sps"
            ]
        return routes

    def _draw_fire_alarm_annotations(
        self,
        c,
        fire_alarms: list[dict],
        floor_number: object | None,
        transform: PlanTransform,
        *,
        obstacles: list[dict[str, float]],
        stage_bounds: dict[str, float],
    ) -> list[dict[str, float]]:
        if not fire_alarms:
            return []

        sorted_alarms = list(fire_alarms)
        symbol_obstacles: list[dict[str, float]] = []
        anchors: list[tuple[dict, Point]] = []
        for index, alarm in enumerate(sorted_alarms, start=1):
            x, y = plan_point_to_pdf(alarm["x"], alarm["y"], transform)
            symbol_obstacles.append({
                "x": x - 7.0,
                "y": y - 7.0,
                "width": 14.0,
                "height": 14.0,
            })
            anchors.append((alarm, (x, y)))

        placed_obstacles: list[dict[str, float]] = []
        for index, (alarm, anchor) in enumerate(anchors, start=1):
            label_text = _get_fire_alarm_code(alarm, floor_number, index)
            placement = _place_plan_text_pdf(
                c,
                text=label_text,
                font_size=FIRE_ALARM_LABEL_FONT_SIZE,
                anchor=anchor,
                preferred_offset=(
                    (float(alarm.get("label_dx")), float(alarm.get("label_dy")))
                    if alarm.get("label_dx") is not None and alarm.get("label_dy") is not None
                    else None
                ),
                symbol_half_width=7.0,
                symbol_half_height=7.0,
                obstacles=obstacles + symbol_obstacles + placed_obstacles,
                bounds=stage_bounds,
            )
            if placement is None or placement.get("rect") is None:
                continue
            label_rect = placement["rect"]
            if placement.get("leader_polyline"):
                c.saveState()
                c.setStrokeColor(colors.red)
                c.setLineWidth(0.8)
                c.setDash(4, 3)
                leader_path = c.beginPath()
                leader_polyline = placement["leader_polyline"]
                leader_path.moveTo(leader_polyline[0][0], leader_polyline[0][1])
                for point in leader_polyline[1:]:
                    leader_path.lineTo(point[0], point[1])
                c.drawPath(leader_path, stroke=1, fill=0)
                c.restoreState()
                placed_obstacles.extend(_polyline_obstacles(leader_polyline, 3.0))
            c.saveState()
            c.setFont(DEFAULT_FONT_NAME, FIRE_ALARM_LABEL_FONT_SIZE)
            c.setFillColor(colors.red)
            c.drawCentredString(
                label_rect["x"] + (label_rect["width"] / 2.0),
                label_rect["y"] + (label_rect["height"] * 0.14),
                label_text,
            )
            c.restoreState()
            placed_obstacles.append(label_rect)
        return symbol_obstacles + placed_obstacles

    def _draw_zkspc_overlays(
        self,
        c,
        floor_plan_data: dict,
        transform: PlanTransform,
        obstacles: list[dict[str, float]] | None = None,
    ) -> list[dict[str, float]]:
        rooms = floor_plan_data.get("rooms") or []
        rooms_by_id = {
            int(room["id"]): room
            for room in rooms
            if room.get("id") is not None
        }
        floor_plan_id = int(floor_plan_data.get("id") or 0)
        style_map = build_zkspc_style_map(floor_plan_data)
        stage_bounds = self._plan_stage_bounds(transform)
        placed_label_obstacles: list[dict[str, float]] = list(obstacles or [])

        for zone in floor_plan_data.get("zkspc_zones") or []:
            zone_style = get_zkspc_style(
                int(zone.get("zone_number") or 1),
                floor_plan_id=floor_plan_id,
                style_map=style_map,
            )
            centers: list[Point] = []
            for room_id in zone.get("room_ids") or []:
                room = rooms_by_id.get(int(room_id))
                if room is None or room.get("room_type") == "необслуживаемое":
                    continue
                bounds = _room_bounds(room)
                points = room.get("boundary_points") or []
                if bounds is None or len(points) < 3:
                    continue
                centers.append(_room_center(room) or ((bounds[0] + bounds[2]) / 2.0, (bounds[1] + bounds[3]) / 2.0))

                polygon_path = c.beginPath()
                first_x, first_y = plan_point_to_pdf(points[0][0], points[0][1], transform)
                polygon_path.moveTo(first_x, first_y)
                for point in points[1:]:
                    pdf_x, pdf_y = plan_point_to_pdf(point[0], point[1], transform)
                    polygon_path.lineTo(pdf_x, pdf_y)
                polygon_path.close()

                min_x, min_y = plan_point_to_pdf(bounds[0], bounds[1], transform)
                max_x, max_y = plan_point_to_pdf(bounds[2], bounds[3], transform)
                room_width = max_x - min_x
                room_height = max_y - min_y

                c.saveState()
                c.clipPath(polygon_path, stroke=0, fill=0)
                c.setFillColor(zone_style["fill_color"])
                c.rect(min_x, min_y, room_width, room_height, stroke=0, fill=1)
                c.setStrokeColor(zone_style["hatch_color"])
                c.setLineWidth(0.6)
                hatch_spacing = float(zone_style["hatch_spacing"])
                offset = bounds[0] - (bounds[3] - bounds[1])
                while offset <= bounds[2] + (bounds[3] - bounds[1]):
                    start = plan_point_to_pdf(offset, bounds[1], transform)
                    end = plan_point_to_pdf(offset + (bounds[3] - bounds[1]), bounds[3], transform)
                    c.line(start[0], start[1], end[0], end[1])
                    offset += hatch_spacing
                c.restoreState()
            if centers:
                center_x = sum(point[0] for point in centers) / len(centers)
                center_y = sum(point[1] for point in centers) / len(centers)
                polygons = [
                    [plan_point_to_pdf(float(point[0]), float(point[1]), transform) for point in room.get("boundary_points") or []]
                    for room_id in zone.get("room_ids") or []
                    for room in [rooms_by_id.get(int(room_id))]
                    if room is not None and room.get("room_type") != "РЅРµРѕР±СЃР»СѓР¶РёРІР°РµРјРѕРµ" and len(room.get("boundary_points") or []) >= 3
                ]
                placement = _place_plan_text_pdf(
                    c,
                    text=str(zone_style["label"]),
                    font_size=11,
                    anchor=plan_point_to_pdf(center_x, center_y, transform),
                    obstacles=placed_label_obstacles,
                    bounds=stage_bounds,
                    strategy="region",
                    region_constraint={
                        "polygons": polygons,
                        "preferred_points": [plan_point_to_pdf(point[0], point[1], transform) for point in centers],
                    },
                )
                if placement is None or placement.get("rect") is None:
                    continue
                label_rect = placement["rect"]
                if placement.get("leader_polyline"):
                    c.saveState()
                    c.setStrokeColor(zone_style["label_color"])
                    c.setLineWidth(0.8)
                    c.setDash(4, 3)
                    leader_path = c.beginPath()
                    leader_polyline = placement["leader_polyline"]
                    leader_path.moveTo(leader_polyline[0][0], leader_polyline[0][1])
                    for point in leader_polyline[1:]:
                        leader_path.lineTo(point[0], point[1])
                    c.drawPath(leader_path, stroke=1, fill=0)
                    c.restoreState()
                    placed_label_obstacles.extend(_polyline_obstacles(leader_polyline, 3.0))
                c.saveState()
                c.setFillColor(zone_style["label_color"])
                c.setFont(DEFAULT_FONT_NAME, 11)
                c.drawCentredString(
                    label_rect["x"] + (label_rect["width"] / 2.0),
                    label_rect["y"] + (label_rect["height"] * 0.14),
                    str(zone_style["label"]),
                )
                c.restoreState()
                placed_label_obstacles.append(label_rect)
        return placed_label_obstacles

    def _draw_unserviceable_room_crosses(self, c, rooms: list[dict], transform: PlanTransform) -> None:
        c.saveState()
        c.setStrokeColor(colors.black)
        c.setLineWidth(0.7)
        for room in rooms:
            if room.get("room_type") != "необслуживаемое":
                continue
            bounds = _room_bounds(room)
            if bounds is None:
                continue
            top_left = plan_point_to_pdf(bounds[0], bounds[1], transform)
            bottom_right = plan_point_to_pdf(bounds[2], bounds[3], transform)
            top_right = plan_point_to_pdf(bounds[2], bounds[1], transform)
            bottom_left = plan_point_to_pdf(bounds[0], bounds[3], transform)
            c.line(top_left[0], top_left[1], bottom_right[0], bottom_right[1])
            c.line(top_right[0], top_right[1], bottom_left[0], bottom_left[1])
        c.restoreState()

    def _draw_room_number_circles(
        self,
        c,
        numbered_rooms: list[dict[str, object]],
        transform: PlanTransform,
        obstacles: list[dict[str, float]] | None = None,
    ) -> list[dict[str, float]]:
        if not numbered_rooms:
            return []
        radius = compute_room_circle_radius(numbered_rooms, transform)
        font_size = max(8.0, min(12.0, radius * 1.05))
        stage_bounds = self._plan_stage_bounds(transform)
        placed_obstacles: list[dict[str, float]] = list(obstacles or [])
        c.saveState()
        c.setStrokeColor(colors.black)
        c.setFillColor(colors.white)
        c.setLineWidth(0.7)
        c.setFont(DEFAULT_FONT_NAME, font_size)
        for item in numbered_rooms:
            badge_layout = _find_room_badge_rect(
                c,
                item["room"],
                str(item["number"]),
                radius,
                font_size,
                transform,
                placed_obstacles,
                stage_bounds,
            )
            if badge_layout is None or badge_layout.get("rect") is None:
                center_x, center_y = find_room_badge_center(item["room"], radius, transform) or item["center"]
                pdf_x, pdf_y = plan_point_to_pdf(center_x, center_y, transform)
                fallback_rect = {
                    "x": pdf_x - radius,
                    "y": pdf_y - radius,
                    "width": radius * 2.0,
                    "height": radius * 2.0,
                }
                if any(_rects_intersect(fallback_rect, obstacle) for obstacle in placed_obstacles) or not _rect_inside_bounds(fallback_rect, stage_bounds):
                    continue
                badge_rect = fallback_rect
            else:
                badge_rect = badge_layout["rect"]
                pdf_x, pdf_y = _rect_center(badge_rect)
                if badge_layout.get("leader_polyline"):
                    c.saveState()
                    c.setStrokeColor(colors.black)
                    c.setLineWidth(0.7)
                    c.setDash(4, 3)
                    leader_path = c.beginPath()
                    leader_polyline = badge_layout["leader_polyline"]
                    leader_path.moveTo(leader_polyline[0][0], leader_polyline[0][1])
                    for point in leader_polyline[1:]:
                        leader_path.lineTo(point[0], point[1])
                    c.drawPath(leader_path, stroke=1, fill=0)
                    c.restoreState()
                    placed_obstacles.extend(_polyline_obstacles(leader_polyline, 2.0))
            c.circle(pdf_x, pdf_y, radius, stroke=1, fill=1)
            c.setFillColor(colors.black)
            c.drawCentredString(pdf_x, pdf_y - (font_size * 0.34), str(item["number"]))
            c.setFillColor(colors.white)
            placed_obstacles.append(badge_rect)
        c.restoreState()
        return placed_obstacles

    def _measure_explication_layout(self, c, numbered_rooms: list[dict[str, object]]) -> dict[str, object] | None:
        if self.sheet_kind != "zkspc" or not numbered_rooms:
            return None

        font_name = DEFAULT_FONT_NAME
        font_size = 10.0
        title_height = 7.0 * mm
        header_height = 6.0 * mm
        row_height = 6.0 * mm
        max_table_height = max(45.0 * mm, self.drawing_height * 0.38)
        max_rows_per_part = max(1, int((max_table_height - title_height - header_height) // row_height))
        parts = split_explication_rows(numbered_rooms, max_rows_per_part)

        def measure_part(rows: list[dict[str, object]]) -> dict[str, object]:
            headers = ("номер", "наименование", "площадь, м^2")
            values = [
                [headers[0], *(str(item["number"]) for item in rows)],
                [headers[1], *(str(item["name"]) for item in rows)],
                [headers[2], *(f"{float(item['area_sqm']):.2f}" for item in rows)],
            ]
            column_widths = [
                max(c.stringWidth(value, font_name, font_size) for value in column_values) + (4.0 * mm)
                for column_values in values
            ]
            return {
                "rows": rows,
                "column_widths": column_widths,
                "width": sum(column_widths),
            }

        measured_parts = [measure_part(part) for part in parts]
        max_rows = max(len(part["rows"]) for part in measured_parts)
        table_height = title_height + header_height + (max_rows * row_height)
        return {
            "parts": measured_parts,
            "font_name": font_name,
            "font_size": font_size,
            "title_height": title_height,
            "header_height": header_height,
            "row_height": row_height,
            "width": sum(part["width"] for part in measured_parts),
            "height": table_height,
        }

    def _estimate_plan_scale(
        self,
        floor_plan_data: dict,
        walls: list[dict],
        drawing_width: float,
        drawing_height: float,
    ) -> tuple[float, int]:
        usable_width = max(40.0 * mm, drawing_width)
        usable_height = max(40.0 * mm, drawing_height)
        gutters = self._resolve_dimension_gutters(usable_width, usable_height, walls)
        plan_width = max(40.0 * mm, usable_width - gutters["left"] - gutters["right"])
        plan_height = max(40.0 * mm, usable_height - gutters["top"] - gutters["bottom"])
        rotation_quarter_turns = choose_plan_rotation(floor_plan_data, plan_width, plan_height)
        image_width = max(1.0, _as_float(floor_plan_data.get("image_width"), 800.0))
        image_height = max(1.0, _as_float(floor_plan_data.get("image_height"), 600.0))
        rotated_width, rotated_height = _rotated_plan_size(
            image_width,
            image_height,
            rotation_quarter_turns,
        )
        scale = min(plan_width / rotated_width, plan_height / rotated_height)
        return scale, rotation_quarter_turns

    def _build_content_layout(self, c, numbered_rooms: list[dict[str, object]]) -> dict[str, object]:
        content_x = self.drawing_x + DRAWING_SAFE_MARGIN
        content_y = self.drawing_y + DRAWING_SAFE_MARGIN
        content_width = max(40.0 * mm, self.drawing_width - (2.0 * DRAWING_SAFE_MARGIN))
        content_height = max(40.0 * mm, self.drawing_height - (2.0 * DRAWING_SAFE_MARGIN))
        explication_layout = self._measure_explication_layout(c, numbered_rooms)
        walls = (self.floor_plan_data or {}).get("walls", []) or []

        candidates: list[dict[str, object]] = []

        def push_candidate(
            placement: str,
            plan_x: float,
            plan_y: float,
            plan_width: float,
            plan_height: float,
            *,
            explication_x: float | None = None,
            explication_y: float | None = None,
        ) -> None:
            if plan_width < 40.0 * mm or plan_height < 40.0 * mm:
                return
            scale, rotation_quarter_turns = self._estimate_plan_scale(
                self.floor_plan_data or {},
                walls,
                plan_width,
                plan_height,
            )
            candidates.append(
                {
                    "placement": placement,
                    "plan_x": plan_x,
                    "plan_y": plan_y,
                    "plan_width": plan_width,
                    "plan_height": plan_height,
                    "scale": scale,
                    "rotation_quarter_turns": rotation_quarter_turns,
                    "explication_layout": explication_layout,
                    "explication_x": explication_x,
                    "explication_y": explication_y,
                }
            )

        if explication_layout:
            table_width = min(float(explication_layout["width"]), content_width)
            table_height = min(float(explication_layout["height"]), content_height)

            push_candidate(
                "bottom",
                content_x,
                content_y + table_height + EXPLICATION_GAP,
                content_width,
                content_height - table_height - EXPLICATION_GAP,
                explication_x=content_x + max(0.0, (content_width - table_width) / 2.0),
                explication_y=content_y,
            )
            push_candidate(
                "right",
                content_x,
                content_y,
                content_width - table_width - EXPLICATION_GAP,
                content_height,
                explication_x=content_x + content_width - table_width,
                explication_y=content_y,
            )

        if not candidates:
            push_candidate(
                "full",
                content_x,
                content_y,
                content_width,
                content_height,
            )

        return max(
            candidates,
            key=lambda item: (
                float(item["scale"]),
                float(item["plan_width"]) * float(item["plan_height"]),
                1 if item["placement"] == "right" else 0,
            ),
        )

    def _draw_explication_table(
        self,
        c,
        layout: dict[str, object],
        numbered_rooms: list[dict[str, object]],
        *,
        x: float | None = None,
        y: float | None = None,
    ) -> None:
        if not layout or not numbered_rooms:
            return

        title = "Экспликация помещений"
        headers = ("номер", "наименование", "площадь, м^2")
        x = self.drawing_x if x is None else x
        y = self.drawing_y if y is None else y
        width = float(layout["width"])
        height = float(layout["height"])
        title_height = float(layout["title_height"])
        header_height = float(layout["header_height"])
        row_height = float(layout["row_height"])
        font_name = str(layout["font_name"])
        font_size = float(layout["font_size"])
        parts = list(layout["parts"])

        c.saveState()
        c.setStrokeColor(colors.black)
        c.setFillColor(colors.black)
        c.setLineWidth(0.6)
        c.rect(x, y, width, height, stroke=1, fill=0)
        c.line(x, y + height - title_height, x + width, y + height - title_height)
        c.setFont(font_name, font_size)
        c.drawCentredString(x + (width / 2.0), y + height - title_height + 1.9 * mm, title)

        current_x = x
        for part_index, part in enumerate(parts):
            part_width = float(part["width"])
            if part_index > 0:
                c.line(current_x, y, current_x, y + height - title_height)
            c.line(current_x, y + height - title_height - header_height, current_x + part_width, y + height - title_height - header_height)

            column_widths = list(part["column_widths"])
            column_x = current_x
            for width_index, column_width in enumerate(column_widths[:-1], start=1):
                column_x += float(column_width)
                c.line(column_x, y, column_x, y + height - title_height)

            row_count = len(part["rows"])
            for row_index in range(1, row_count + 1):
                line_y = y + height - title_height - header_height - (row_index * row_height)
                c.line(current_x, line_y, current_x + part_width, line_y)

            header_x = current_x
            for header, column_width in zip(headers, column_widths):
                c.drawCentredString(header_x + (float(column_width) / 2.0), y + height - title_height - header_height + 1.8 * mm, header)
                header_x += float(column_width)

            for row_index, row in enumerate(part["rows"], start=1):
                row_top = y + height - title_height - header_height - ((row_index - 1) * row_height)
                text_y = row_top - row_height + 1.8 * mm
                value_x = current_x
                values = (
                    str(row["number"]),
                    str(row["name"]),
                    f"{float(row['area_sqm']):.2f}",
                )
                for value, column_width in zip(values, column_widths):
                    c.drawCentredString(value_x + (float(column_width) / 2.0), text_y, value)
                    value_x += float(column_width)

            current_x += part_width

        c.restoreState()

    def draw_floor_plan_elements(
        self,
        c,
        floor_plan_data: dict,
        *,
        drawing_x: float | None = None,
        drawing_y: float | None = None,
        drawing_width: float | None = None,
        drawing_height: float | None = None,
        numbered_rooms: list[dict[str, object]] | None = None,
        rotation_quarter_turns: int | None = None,
    ) -> None:
        """Render vector floor plan elements on the PDF page."""
        if not floor_plan_data:
            return

        target_x = drawing_x if drawing_x is not None else self.drawing_x
        target_y = drawing_y if drawing_y is not None else self.drawing_y
        target_width = drawing_width if drawing_width is not None else self.drawing_width
        target_height = drawing_height if drawing_height is not None else self.drawing_height

        walls = floor_plan_data.get("walls", []) or []
        doors = floor_plan_data.get("doors", []) or []
        windows = floor_plan_data.get("windows", []) or []
        stairs = floor_plan_data.get("stairs", []) or []
        gutters = self._resolve_dimension_gutters(target_width, target_height, walls)
        plan_width = max(40.0 * mm, target_width - gutters["left"] - gutters["right"])
        plan_height = max(40.0 * mm, target_height - gutters["top"] - gutters["bottom"])
        plan_rotation = (
            rotation_quarter_turns
            if rotation_quarter_turns is not None
            else choose_plan_rotation(floor_plan_data, plan_width, plan_height)
        )

        transform = compute_plan_transform(
            floor_plan_data,
            target_x + gutters["left"],
            target_y + gutters["bottom"],
            plan_width,
            plan_height,
            rotation_quarter_turns=plan_rotation,
        )

        zkspc_obstacles: list[dict[str, float]] = []
        if self.sheet_kind == "zkspc":
            zkspc_geometry_obstacles = self._collect_geometry_obstacles(walls, doors, windows, stairs, transform)
            zkspc_obstacles = self._draw_zkspc_overlays(
                c,
                floor_plan_data,
                transform,
                obstacles=zkspc_geometry_obstacles,
            )

        self._draw_walls(c, walls, transform)
        self._draw_openings(c, doors, walls, transform, builder=build_door_symbol_segments)
        self._draw_openings(c, windows, walls, transform, builder=build_window_symbol_segments)
        self._draw_stairs(c, stairs, transform)

        if self.sheet_kind in {"generic", "sps"}:
            sheet_fire_alarms = _visible_fire_alarms_for_sheet(floor_plan_data, self.sheet_kind)
            sheet_routes = self._sheet_signal_routes(floor_plan_data)
            sheet_instruments = _visible_signal_instruments_for_sheet(floor_plan_data, self.sheet_kind)
            stage_bounds = self._plan_stage_bounds(transform)
            geometry_obstacles = self._collect_geometry_obstacles(walls, doors, windows, stairs, transform)
            for alarm in sheet_fire_alarms:
                alarm_x, alarm_y = plan_point_to_pdf(alarm["x"], alarm["y"], transform)
                geometry_obstacles.append({
                    "x": alarm_x - 7.0,
                    "y": alarm_y - 7.0,
                    "width": 14.0,
                    "height": 14.0,
                })
            for instrument in sheet_instruments:
                instrument_x, instrument_y = plan_point_to_pdf(instrument["x"], instrument["y"], transform)
                if instrument.get("instrument_type") == "control_panel":
                    half_width = (6.0 * mm * 1.6) / 2.0
                    half_height = (6.0 * mm * 0.8) / 2.0
                else:
                    half_width = (6.0 * mm) / 2.0
                    half_height = half_width
                geometry_obstacles.append({
                    "x": instrument_x - half_width,
                    "y": instrument_y - half_height,
                    "width": half_width * 2.0,
                    "height": half_height * 2.0,
                })
            cable_route_obstacles = self._draw_cable_routes(
                c,
                sheet_routes,
                transform,
                base_obstacles=geometry_obstacles,
                stage_bounds=stage_bounds,
                device_lookup={
                    alarm.get("id"): plan_point_to_pdf(alarm["x"], alarm["y"], transform)
                    for alarm in sheet_fire_alarms
                    if alarm.get("id") is not None
                },
            )
            self._draw_fire_alarms(
                c,
                sheet_fire_alarms,
                transform,
            )
            fire_alarm_obstacles = self._draw_fire_alarm_annotations(
                c,
                sheet_fire_alarms,
                floor_plan_data.get("floor_number"),
                transform,
                obstacles=geometry_obstacles + cable_route_obstacles,
                stage_bounds=stage_bounds,
            )
            self._draw_signal_instruments(
                c,
                sheet_instruments,
                transform,
                obstacles=geometry_obstacles + cable_route_obstacles + fire_alarm_obstacles,
                stage_bounds=stage_bounds,
            )

        if self.sheet_kind == "soue":
            sheet_routes = self._sheet_signal_routes(floor_plan_data)
            soue_devices = _visible_soue_devices_for_sheet(floor_plan_data, self.sheet_kind)
            sheet_instruments = _visible_signal_instruments_for_sheet(floor_plan_data, self.sheet_kind)
            stage_bounds = self._plan_stage_bounds(transform)
            geometry_obstacles = self._collect_geometry_obstacles(walls, doors, windows, stairs, transform)
            for device in soue_devices:
                device_x, device_y = plan_point_to_pdf(device["x"], device["y"], transform)
                half_width, half_height = _soue_device_symbol_half_extents(
                    device.get("device_type"),
                    rotation_deg=_as_float(device.get("rotation_deg"), 0.0),
                )
                geometry_obstacles.append({
                    "x": device_x - half_width,
                    "y": device_y - half_height,
                    "width": half_width * 2.0,
                    "height": half_height * 2.0,
                })
            for instrument in sheet_instruments:
                instrument_x, instrument_y = plan_point_to_pdf(instrument["x"], instrument["y"], transform)
                if instrument.get("instrument_type") == "control_panel":
                    half_width = (6.0 * mm * 1.6) / 2.0
                    half_height = (6.0 * mm * 0.8) / 2.0
                else:
                    half_width = (6.0 * mm) / 2.0
                    half_height = half_width
                geometry_obstacles.append({
                    "x": instrument_x - half_width,
                    "y": instrument_y - half_height,
                    "width": half_width * 2.0,
                    "height": half_height * 2.0,
                })
            cable_route_obstacles = self._draw_cable_routes(
                c,
                sheet_routes,
                transform,
                base_obstacles=geometry_obstacles,
                stage_bounds=stage_bounds,
                device_lookup={},
            )
            self._draw_soue_devices(c, soue_devices, transform)
            soue_device_obstacles = self._draw_soue_device_annotations(
                c,
                soue_devices,
                floor_plan_data.get("floor_number"),
                transform,
                obstacles=geometry_obstacles + cable_route_obstacles,
                stage_bounds=stage_bounds,
            )
            self._draw_signal_instruments(
                c,
                sheet_instruments,
                transform,
                obstacles=geometry_obstacles + cable_route_obstacles + soue_device_obstacles,
                stage_bounds=stage_bounds,
            )

        if self.sheet_kind == "zkspc":
            self._draw_unserviceable_room_crosses(c, floor_plan_data.get("rooms", []) or [], transform)
            self._draw_room_number_circles(c, numbered_rooms or [], transform, obstacles=zkspc_obstacles)

        self._draw_exterior_dimensions(c, walls, transform)

    def draw(self, c):
        """Draw page with floor plan elements."""
        c.setPageSize((self.page_width, self.page_height))
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        self.draw_outer_border(c)

        should_draw_top_title = bool(self.title) and self.sheet_kind not in {"zkspc", "sps", "soue"}
        if should_draw_top_title:
            self.fit_text_in_box(
                c,
                self.title,
                self.drawing_x,
                self.page_height - self.borders_mm["top"] - 15 * mm,
                self.drawing_width,
                10 * mm,
                CENTER,
                font_size=14,
                bold=True,
            )

        if self.floor_plan_data:
            numbered_rooms = build_room_numbering(self.floor_plan_data.get("rooms") or [])
            content_layout = self._build_content_layout(c, numbered_rooms)
            layout = content_layout.get("explication_layout")
            if layout and content_layout.get("explication_x") is not None and content_layout.get("explication_y") is not None:
                self.draw_floor_plan_elements(
                    c,
                    self.floor_plan_data,
                    drawing_x=float(content_layout["plan_x"]),
                    drawing_y=float(content_layout["plan_y"]),
                    drawing_width=float(content_layout["plan_width"]),
                    drawing_height=float(content_layout["plan_height"]),
                    numbered_rooms=numbered_rooms,
                    rotation_quarter_turns=int(content_layout["rotation_quarter_turns"]),
                )
                self._draw_explication_table(
                    c,
                    layout,
                    numbered_rooms,
                    x=float(content_layout["explication_x"]),
                    y=float(content_layout["explication_y"]),
                )
            else:
                self.draw_floor_plan_elements(
                    c,
                    self.floor_plan_data,
                    drawing_x=float(content_layout["plan_x"]),
                    drawing_y=float(content_layout["plan_y"]),
                    drawing_width=float(content_layout["plan_width"]),
                    drawing_height=float(content_layout["plan_height"]),
                    numbered_rooms=numbered_rooms,
                    rotation_quarter_turns=int(content_layout["rotation_quarter_turns"]),
                )

        if self.page_number > 0:
            self.draw_main_title_box(c, self.main_title_box_type)
            self.fill_main_title_box(c, self.main_title_box_type)

        c.showPage()
