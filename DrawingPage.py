from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics

from Page import Page
from consts import *

Point = tuple[float, float]
Segment = tuple[Point, Point]

DISPLAY_ROUTE_SPACING = 4.0
ZC_LABEL_TEXT = "ZC"
ARK_LABEL_TEXT = "ARK"
ZC_LABEL_FONT_SIZE = 8.0
FIRE_ALARM_LABEL_FONT_SIZE = 8.0
SIGNAL_LABEL_FONT_SIZE = 9.0


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


def draw_fire_alarm_symbol(c, x: float, y: float, device_type: str | None, size: float = 4.5 * mm) -> None:
    half = size / 2.0
    c.saveState()
    c.setStrokeColor(colors.red)
    c.setFillColor(colors.white)
    c.setLineWidth(max(0.7, size * 0.08))
    c.rect(x - half, y - half, size, size, stroke=1, fill=1)

    if device_type == "manual_call_point":
        c.line(x, y - size * 0.10, x - size * 0.18, y + size * 0.08)
        c.line(x - size * 0.18, y + size * 0.08, x - size * 0.34, y + size * 0.28)
        c.line(x, y - size * 0.10, x + size * 0.18, y + size * 0.08)
        c.line(x + size * 0.18, y + size * 0.08, x + size * 0.34, y + size * 0.28)
        c.line(x, y - size * 0.10, x, y - size * 0.34)
    else:
        c.line(x - size * 0.28, y - size * 0.20, x - size * 0.10, y + size * 0.08)
        c.line(x - size * 0.10, y + size * 0.08, x + size * 0.04, y - size * 0.05)
        c.line(x + size * 0.04, y - size * 0.05, x + size * 0.26, y + size * 0.22)

    c.restoreState()


def _get_fire_alarm_code(alarm: dict, floor_number: object | None, fallback_number: int = 1) -> str:
    floor_text = str(floor_number if floor_number is not None else 1).strip() or "1"
    prefix = "BTM" if alarm.get("device_type") == "manual_call_point" else "BTH"
    loop = str(alarm.get("zone") or 1).strip() or "1"
    address = str(alarm.get("address") or fallback_number).strip() or str(fallback_number)
    return f"{floor_text}{prefix}{loop}.{address}"


def _measure_text_rect(c, center_x: float, center_y: float, text: str, font_size: float, padding_x: float = 3.0) -> dict[str, float]:
    width = c.stringWidth(str(text or ""), DEFAULT_FONT_NAME, font_size) + (padding_x * 2.0)
    height = max(font_size + 2.0, font_size * 1.2)
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
) -> dict[str, float] | None:
    if dx is None or dy is None:
        return None
    width = c.stringWidth(str(text or ""), DEFAULT_FONT_NAME, font_size) + (padding_x * 2.0)
    height = max(font_size + 2.0, font_size * 1.2)
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
) -> dict[str, float]:
    horizontal_gap = symbol_half_width + 8.0
    vertical_gap = symbol_half_height + 8.0
    side_gap = symbol_half_height + 6.0
    candidates = [
        _measure_text_rect(c, anchor_x + horizontal_gap, anchor_y, text, font_size),
        _measure_text_rect(c, anchor_x + horizontal_gap, anchor_y - vertical_gap, text, font_size),
        _measure_text_rect(c, anchor_x + horizontal_gap, anchor_y + vertical_gap, text, font_size),
        _measure_text_rect(c, anchor_x - horizontal_gap, anchor_y, text, font_size),
        _measure_text_rect(c, anchor_x - horizontal_gap, anchor_y - vertical_gap, text, font_size),
        _measure_text_rect(c, anchor_x - horizontal_gap, anchor_y + vertical_gap, text, font_size),
        _measure_text_rect(c, anchor_x, anchor_y - side_gap, text, font_size),
        _measure_text_rect(c, anchor_x, anchor_y + side_gap, text, font_size),
    ]

    for candidate in candidates:
        if not _rect_inside_bounds(candidate, bounds):
            continue
        if any(_rects_intersect(candidate, obstacle) for obstacle in obstacles):
            continue
        return candidate
    return candidates[0]


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


def _spread_offsets(count: int) -> list[float]:
    if count <= 1:
        return [0.0]
    midpoint = (count - 1) / 2.0
    return [(index - midpoint) * DISPLAY_ROUTE_SPACING for index in range(count)]


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


def build_display_cable_routes_pdf(routes: list[dict], transform: PlanTransform) -> dict[object, list[Point]]:
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
        offsets = _spread_offsets(len(ordered))
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


def _get_zc_label_layout_pdf(c, polyline: list[Point], obstacles: list[dict[str, float]], bounds: dict[str, float] | None) -> dict[str, float] | None:
    if not polyline:
        return None
    end = polyline[-1]
    direction = _terminal_direction(polyline)
    normal = (-direction[1], direction[0])
    label_rect = _measure_text_rect(c, 0.0, 0.0, ZC_LABEL_TEXT, ZC_LABEL_FONT_SIZE)
    terminator_size = 10.8
    forward_distance = (terminator_size / 2.0) + (label_rect["width"] / 2.0) + 6.0
    side_distance = (label_rect["height"] / 2.0) + 6.0
    candidates = [
        _measure_text_rect(c, end[0] + (direction[0] * forward_distance), end[1] + (direction[1] * forward_distance), ZC_LABEL_TEXT, ZC_LABEL_FONT_SIZE),
        _measure_text_rect(c, end[0] + (direction[0] * forward_distance) + (normal[0] * side_distance), end[1] + (direction[1] * forward_distance) + (normal[1] * side_distance), ZC_LABEL_TEXT, ZC_LABEL_FONT_SIZE),
        _measure_text_rect(c, end[0] + (direction[0] * forward_distance) - (normal[0] * side_distance), end[1] + (direction[1] * forward_distance) - (normal[1] * side_distance), ZC_LABEL_TEXT, ZC_LABEL_FONT_SIZE),
        _measure_text_rect(c, end[0] - (direction[0] * forward_distance), end[1] - (direction[1] * forward_distance), ZC_LABEL_TEXT, ZC_LABEL_FONT_SIZE),
    ]
    for candidate in candidates:
        if not _rect_inside_bounds(candidate, bounds):
            continue
        if any(_rects_intersect(candidate, obstacle) for obstacle in obstacles):
            continue
        return candidate
    return candidates[0]


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
    ) -> None:
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
            return

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
                text_x = (
                    (start_x + end_x) / 2.0
                    if fits_between_arrows
                    else max(start_x, end_x) + DIMENSION_ARROW_SIZE + (1.5 * mm) + (label_width / 2.0)
                )
                text_y = (
                    dimension_y + DIMENSION_TEXT_GAP + ascent
                    if outward_sign > 0
                    else dimension_y - DIMENSION_TEXT_GAP - ascent
                )
                c.drawCentredString(
                    text_x,
                    text_y,
                    label,
                )
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
                c.saveState()
                c.setFont(DEFAULT_FONT_NAME, DIMENSION_TEXT_FONT_SIZE)
                text_y = (
                    (start_y + end_y) / 2.0
                    if fits_between_arrows
                    else max(start_y, end_y) + DIMENSION_ARROW_SIZE + (1.5 * mm) + (label_width / 2.0)
                )
                c.translate(dimension_x + (outward_sign * DIMENSION_TEXT_GAP), text_y)
                c.rotate(90)
                c.drawCentredString(0.0, -(DIMENSION_TEXT_FONT_SIZE * 0.34), label)
                c.restoreState()

        c.restoreState()

    def _draw_exterior_dimensions(self, c, walls: list[dict], transform: PlanTransform) -> None:
        if not walls or not self._should_draw_exterior_dimensions():
            return
        specs = build_exterior_dimension_specs(walls, transform.scale_factor)
        if not specs:
            return
        line_width = max(0.25, _wall_stroke_width(walls, transform) * 0.5)
        for side in ("top", "bottom", "left", "right"):
            spec = specs.get(side)
            if spec is not None:
                self._draw_exterior_dimension_spec(c, spec, transform, line_width)

    def _draw_fire_alarms(self, c, fire_alarms: list[dict], transform: PlanTransform) -> None:
        for alarm in fire_alarms:
            x, y = plan_point_to_pdf(alarm["x"], alarm["y"], transform)
            draw_fire_alarm_symbol(c, x, y, alarm.get("device_type"))

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
    ) -> list[dict[str, float]]:
        if not routes:
            return []

        display_map = build_display_cable_routes_pdf(routes, transform)
        route_obstacles: list[dict[str, float]] = []
        for route in routes:
            route_id = route.get("id")
            display_polyline = display_map.get(route_id, [])
            route_obstacles.extend(_polyline_obstacles(display_polyline, 3.0))
            if display_polyline:
                route_obstacles.append(_inflate_rect(_measure_text_rect(c, display_polyline[-1][0], display_polyline[-1][1], "", 10.8), 4.0))

        c.saveState()
        c.setStrokeColor(colors.red)
        c.setLineWidth(1.6)
        c.setLineCap(1)
        c.setLineJoin(1)
        for route in routes:
            route_id = route.get("id")
            display_polyline = display_map.get(route_id, [])
            if len(display_polyline) < 2:
                continue
            path = c.beginPath()
            path.moveTo(display_polyline[0][0], display_polyline[0][1])
            for point in display_polyline[1:]:
                path.lineTo(point[0], point[1])
            c.drawPath(path, stroke=1, fill=0)
            should_show_zc = route.get("system_type") == "non_addressable" and route.get("route_kind") in {"zone_loop", "manual_line"}
            if should_show_zc:
                _draw_zc_terminator(c, display_polyline[-1][0], display_polyline[-1][1])
        c.restoreState()

        placed_labels: list[dict[str, float]] = []
        for route in routes:
            route_id = route.get("id")
            display_polyline = display_map.get(route_id, [])
            should_show_zc = route.get("system_type") == "non_addressable" and route.get("route_kind") in {"zone_loop", "manual_line"}
            if not should_show_zc or not display_polyline:
                continue
            anchor_x, anchor_y = display_polyline[-1]
            label_rect = _measure_text_rect_from_offset(
                c,
                anchor_x,
                anchor_y,
                ZC_LABEL_TEXT,
                ZC_LABEL_FONT_SIZE,
                route.get("zc_label_dx"),
                route.get("zc_label_dy"),
            ) or _get_zc_label_layout_pdf(
                c,
                display_polyline,
                base_obstacles + route_obstacles + placed_labels,
                stage_bounds,
            )
            if label_rect is None:
                continue
            c.saveState()
            c.setFont(DEFAULT_FONT_NAME, ZC_LABEL_FONT_SIZE)
            c.setFillColor(colors.red)
            c.drawCentredString(
                label_rect["x"] + (label_rect["width"] / 2.0),
                label_rect["y"] + (label_rect["height"] * 0.14),
                ZC_LABEL_TEXT,
            )
            c.restoreState()
            placed_labels.append(label_rect)
        return route_obstacles + placed_labels

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
            label_text = str(instrument.get("name") or "").strip() or (
                ARK_LABEL_TEXT if instrument.get("instrument_type") == "control_panel" else ""
            )
            if label_text:
                control_labels.append((instrument, {"x": x, "y": y}, (half_width, half_height), label_text))

        placed_labels: list[dict[str, float]] = []
        for instrument, anchor, halves, label_text in control_labels:
            label_rect = _measure_text_rect_from_offset(
                c,
                anchor["x"],
                anchor["y"],
                label_text,
                SIGNAL_LABEL_FONT_SIZE,
                instrument.get("label_dx"),
                instrument.get("label_dy"),
            ) or _place_symbol_label(
                c,
                anchor_x=anchor["x"],
                anchor_y=anchor["y"],
                text=label_text,
                font_size=SIGNAL_LABEL_FONT_SIZE,
                symbol_half_width=halves[0],
                symbol_half_height=halves[1],
                obstacles=obstacles + symbol_obstacles + placed_labels,
                bounds=stage_bounds,
            )
            c.saveState()
            c.setFont(DEFAULT_FONT_NAME, SIGNAL_LABEL_FONT_SIZE)
            c.setFillColor(colors.black)
            c.drawCentredString(
                label_rect["x"] + (label_rect["width"] / 2.0),
                label_rect["y"] + (label_rect["height"] * 0.14),
                label_text,
            )
            c.restoreState()
            placed_labels.append(label_rect)
        return symbol_obstacles + placed_labels

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

        sorted_alarms = sorted(
            fire_alarms,
            key=lambda alarm: (
                str(alarm.get("zone") or ""),
                str(alarm.get("address") or ""),
                float(alarm.get("x") or 0.0),
                float(alarm.get("y") or 0.0),
            ),
        )
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

        placed_labels: list[dict[str, float]] = []
        for index, (alarm, anchor) in enumerate(anchors, start=1):
            label_text = _get_fire_alarm_code(alarm, floor_number, index)
            label_rect = _measure_text_rect_from_offset(
                c,
                anchor[0],
                anchor[1],
                label_text,
                FIRE_ALARM_LABEL_FONT_SIZE,
                alarm.get("label_dx"),
                alarm.get("label_dy"),
            ) or _place_symbol_label(
                c,
                anchor_x=anchor[0],
                anchor_y=anchor[1],
                text=label_text,
                font_size=FIRE_ALARM_LABEL_FONT_SIZE,
                symbol_half_width=7.0,
                symbol_half_height=7.0,
                obstacles=obstacles + symbol_obstacles + placed_labels,
                bounds=stage_bounds,
            )
            c.saveState()
            c.setFont(DEFAULT_FONT_NAME, FIRE_ALARM_LABEL_FONT_SIZE)
            c.setFillColor(colors.red)
            c.drawCentredString(
                label_rect["x"] + (label_rect["width"] / 2.0),
                label_rect["y"] + (label_rect["height"] * 0.14),
                label_text,
            )
            c.restoreState()
            placed_labels.append(label_rect)
        return symbol_obstacles + placed_labels

    def _draw_zkspc_overlays(self, c, floor_plan_data: dict, transform: PlanTransform) -> None:
        rooms = floor_plan_data.get("rooms") or []
        rooms_by_id = {
            int(room["id"]): room
            for room in rooms
            if room.get("id") is not None
        }
        floor_plan_id = int(floor_plan_data.get("id") or 0)
        style_map = build_zkspc_style_map(floor_plan_data)

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
                pdf_x, pdf_y = plan_point_to_pdf(center_x, center_y, transform)
                c.saveState()
                c.setFillColor(zone_style["label_color"])
                c.setFont(DEFAULT_FONT_NAME, 11)
                c.drawCentredString(pdf_x, pdf_y, str(zone_style["label"]))
                c.restoreState()

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

    def _draw_room_number_circles(self, c, numbered_rooms: list[dict[str, object]], transform: PlanTransform) -> None:
        if not numbered_rooms:
            return
        radius = compute_room_circle_radius(numbered_rooms, transform)
        font_size = max(8.0, min(12.0, radius * 1.05))
        c.saveState()
        c.setStrokeColor(colors.black)
        c.setFillColor(colors.white)
        c.setLineWidth(0.7)
        c.setFont(DEFAULT_FONT_NAME, font_size)
        for item in numbered_rooms:
            center_x, center_y = find_room_badge_center(item["room"], radius, transform) or item["center"]
            pdf_x, pdf_y = plan_point_to_pdf(center_x, center_y, transform)
            c.circle(pdf_x, pdf_y, radius, stroke=1, fill=1)
            c.setFillColor(colors.black)
            c.drawCentredString(pdf_x, pdf_y - (font_size * 0.34), str(item["number"]))
            c.setFillColor(colors.white)
        c.restoreState()

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

        if self.sheet_kind == "zkspc":
            self._draw_zkspc_overlays(c, floor_plan_data, transform)

        self._draw_walls(c, walls, transform)
        self._draw_openings(c, doors, walls, transform, builder=build_door_symbol_segments)
        self._draw_openings(c, windows, walls, transform, builder=build_window_symbol_segments)
        self._draw_stairs(c, stairs, transform)

        if self.sheet_kind in {"generic", "sps"}:
            stage_bounds = self._plan_stage_bounds(transform)
            geometry_obstacles = self._collect_geometry_obstacles(walls, doors, windows, stairs, transform)
            for alarm in floor_plan_data.get("fire_alarms", []) or []:
                alarm_x, alarm_y = plan_point_to_pdf(alarm["x"], alarm["y"], transform)
                geometry_obstacles.append({
                    "x": alarm_x - 7.0,
                    "y": alarm_y - 7.0,
                    "width": 14.0,
                    "height": 14.0,
                })
            for instrument in floor_plan_data.get("signal_instruments", []) or []:
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
                floor_plan_data.get("cable_routes", []) or [],
                transform,
                base_obstacles=geometry_obstacles,
                stage_bounds=stage_bounds,
            )
            fire_alarm_obstacles = self._draw_fire_alarm_annotations(
                c,
                floor_plan_data.get("fire_alarms", []) or [],
                floor_plan_data.get("floor_number"),
                transform,
                obstacles=geometry_obstacles + cable_route_obstacles,
                stage_bounds=stage_bounds,
            )
            self._draw_signal_instruments(
                c,
                floor_plan_data.get("signal_instruments", []) or [],
                transform,
                obstacles=geometry_obstacles + cable_route_obstacles + fire_alarm_obstacles,
                stage_bounds=stage_bounds,
            )

        if self.sheet_kind == "zkspc":
            self._draw_unserviceable_room_crosses(c, floor_plan_data.get("rooms", []) or [], transform)
            self._draw_room_number_circles(c, numbered_rooms or [], transform)

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
