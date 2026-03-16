from __future__ import annotations

import math
from dataclasses import dataclass

import cv2
import numpy as np
from reportlab.lib import colors

from Page import Page
from consts import *

Point = tuple[float, float]
Segment = tuple[Point, Point]


@dataclass(frozen=True)
class PlanTransform:
    image_width: float
    image_height: float
    scale: float
    offset_x: float
    offset_y: float
    scale_factor: float


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
) -> PlanTransform:
    image_width = max(1.0, _as_float(floor_plan_data.get("image_width"), 800.0))
    image_height = max(1.0, _as_float(floor_plan_data.get("image_height"), 600.0))
    scale = min(drawing_width / image_width, drawing_height / image_height)
    scaled_width = image_width * scale
    scaled_height = image_height * scale
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
    )


def plan_point_to_pdf(x: float, y: float, transform: PlanTransform) -> Point:
    return (
        transform.offset_x + float(x) * transform.scale,
        transform.offset_y + float(y) * transform.scale,
    )


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


def wall_thickness_px(wall: dict, scale_factor: float) -> float:
    thickness_mm = _as_float(wall.get("thickness"), 200.0)
    return max(1.0, thickness_mm / max(scale_factor, 1e-6))


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
    thickness = wall_thickness_px(wall, scale_factor)
    half = thickness / 2.0
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)

    if length < 1e-6:
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
            [x1 + nx * half, y1 + ny * half],
            [x2 + nx * half, y2 + ny * half],
            [x2 - nx * half, y2 - ny * half],
            [x1 - nx * half, y1 - ny * half],
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

        t = ((center_x - x1) * dx + (center_y - y1) * dy) / (length * length)
        along = t * length
        signed = ((center_x - x1) * dy - (center_y - y1) * dx) / length
        distance = abs(signed)

        thickness = wall_thickness_px(wall, scale_factor)
        max_distance = max(thickness * 1.5, min(width, height, 40.0))
        within_projection = -projection_margin <= along <= (length + projection_margin)
        within_thickness = distance <= max_distance
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
    half_thickness = wall_thickness_px(wall, scale_factor) / 2.0
    span = _opening_half_span(opening, ux, uy)
    center_x = _as_float(opening.get("x"), 0.0) + _as_float(opening.get("width"), 0.0) / 2.0
    center_y = (
        _as_float(opening.get("y"), 0.0) + _as_float(opening.get("height"), 0.0) / 2.0
    )

    start_center = (center_x - ux * span, center_y - uy * span)
    end_center = (center_x + ux * span, center_y + uy * span)
    start_segment = (
        (start_center[0] - nx * half_thickness, start_center[1] - ny * half_thickness),
        (start_center[0] + nx * half_thickness, start_center[1] + ny * half_thickness),
    )
    end_segment = (
        (end_center[0] - nx * half_thickness, end_center[1] - ny * half_thickness),
        (end_center[0] + nx * half_thickness, end_center[1] + ny * half_thickness),
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


class DrawingPage(Page):
    """DrawingPage-level configuration and drawing."""

    def __init__(
        self,
        page_format: tuple[float, float] = PAGESIZE_A4,
        main_title_box_type: str = "1",
        creds: dict[str, str] = DEFAULT_CREDS_DICT,
        page_number: int = 1,
        borders_mm: dict[str, float] = DEFAULT_BORDERS,
        floor_plan_data: dict | None = None,
        title: str = "",
    ):
        super().__init__(page_format, main_title_box_type, creds, page_number, borders_mm)
        self.floor_plan_data = floor_plan_data
        self.title = title
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

    def draw_floor_plan_elements(self, c, floor_plan_data: dict):
        """Render vector floor plan elements on the PDF page."""
        if not floor_plan_data:
            return

        transform = compute_plan_transform(
            floor_plan_data,
            self.drawing_x,
            self.drawing_y,
            self.drawing_width,
            self.drawing_height,
        )
        walls = floor_plan_data.get("walls", [])
        doors = floor_plan_data.get("doors", [])
        windows = floor_plan_data.get("windows", [])
        wall_line_width = _wall_stroke_width(walls, transform)

        if walls:
            wall_mask = build_wall_mask(
                walls,
                transform.image_width,
                transform.image_height,
                transform.scale_factor,
            )
            wall_contours = extract_wall_contours(wall_mask)
            c.saveState()
            c.setStrokeColor(colors.black)
            c.setLineWidth(wall_line_width)
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

        if doors:
            c.saveState()
            c.setStrokeColor(colors.black)
            c.setLineWidth(wall_line_width)
            c.setLineCap(1)
            c.setLineJoin(1)
            for door in doors:
                _draw_segments(
                    c,
                    build_door_symbol_segments(door, walls, transform.scale_factor),
                    transform,
                )
            c.restoreState()

        if windows:
            c.saveState()
            c.setStrokeColor(colors.black)
            c.setLineWidth(wall_line_width)
            c.setLineCap(1)
            c.setLineJoin(1)
            for window in windows:
                _draw_segments(
                    c,
                    build_window_symbol_segments(window, walls, transform.scale_factor),
                    transform,
                )
            c.restoreState()

        fire_alarms = floor_plan_data.get("fire_alarms", [])
        if fire_alarms:
            for alarm in fire_alarms:
                x, y = plan_point_to_pdf(alarm["x"], alarm["y"], transform)
                draw_fire_alarm_symbol(c, x, y, alarm.get("device_type"))

    def draw(self, c):
        """Draw page with floor plan elements."""
        c.setPageSize((self.page_width, self.page_height))
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        self.draw_outer_border(c)

        if self.title:
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
            self.draw_floor_plan_elements(c, self.floor_plan_data)

        if self.page_number > 0:
            self.draw_main_title_box(c, self.main_title_box_type)
            self.fill_main_title_box(c, self.main_title_box_type)

        c.showPage()
