from __future__ import annotations

import io

import cv2
import numpy as np
import pytest
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from backend.bootstrap import register_pdf_fonts
from DrawingPage import (
    DRAWING_SAFE_MARGIN,
    DIMENSION_LINE_OFFSET,
    EXPLICATION_GAP,
    DrawingPage,
    ExteriorDimensionSpec,
    PlanTransform,
    build_display_cable_routes_pdf,
    build_exterior_dimension_specs,
    build_room_numbering,
    build_stair_segments,
    build_door_symbol_segments,
    choose_plan_rotation,
    build_zkspc_style_map,
    build_wall_mask,
    build_window_symbol_segments,
    extract_wall_contours,
    find_room_badge_center,
    get_zkspc_style,
    _find_room_badge_rect,
    _place_plan_text_pdf,
    _rects_intersect,
    _resolve_zc_terminator_point_pdf,
    resolve_opening_wall,
    wall_polygon,
)
from consts import DIMENSION_ARROW_SIZE, DIMENSION_TEXT_FONT_SIZE, DIMENSION_TEXT_GAP, PAGESIZE_A3_LANDSCAPE


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


def test_wall_contours_hide_internal_segments_for_parallel_overlap():
    walls = [
        {"id": 1, "x1": 20, "y1": 60, "x2": 80, "y2": 60, "thickness": 20, "alignment": "left"},
        {"id": 2, "x1": 60, "y1": 60, "x2": 120, "y2": 60, "thickness": 20, "alignment": "right"},
    ]

    contours = extract_wall_contours(build_wall_mask(walls, 140, 120, 1.0))
    raster = _rasterize_contours(contours, (120, 140))

    assert raster[60, 70] == 0
    assert raster[50, 20] == 255
    assert raster[50, 120] == 255


def test_wall_polygon_ignores_legacy_alignment_flags():
    center_polygon = wall_polygon(
        {"x1": 10, "y1": 20, "x2": 90, "y2": 20, "thickness": 200, "alignment": "center"},
        10.0,
    )
    left_polygon = wall_polygon(
        {"x1": 10, "y1": 20, "x2": 90, "y2": 20, "thickness": 200, "alignment": "left"},
        10.0,
    )
    right_polygon = wall_polygon(
        {"x1": 10, "y1": 20, "x2": 90, "y2": 20, "thickness": 200, "alignment": "right"},
        10.0,
    )

    assert np.array_equal(center_polygon, left_polygon)
    assert np.array_equal(center_polygon, right_polygon)


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


@pytest.mark.skip(reason="Legacy mojibake assertion retained in history; covered by a clean replacement below.")
def test_get_zkspc_style_is_deterministic_for_zone_and_floor():
    style_a = get_zkspc_style(3, floor_plan_id=12)
    style_b = get_zkspc_style(3, floor_plan_id=12)
    style_c = get_zkspc_style(4, floor_plan_id=12)

    assert style_a["color_hex"] == style_b["color_hex"]
    assert style_a["hatch_spacing"] == style_b["hatch_spacing"]
    assert style_a["label"] == "ЗКСПС №3"
    assert style_c["color_hex"] != style_a["color_hex"]


def test_build_room_numbering_orders_rooms_top_to_bottom_then_left_to_right():
    numbered = build_room_numbering(
        [
            {"id": 1, "name": "South", "area_sqm": 14.0, "boundary_points": [[0, 50], [30, 50], [30, 80], [0, 80]], "center_x": 15, "center_y": 65},
            {"id": 2, "name": "North West", "area_sqm": 10.0, "boundary_points": [[0, 0], [30, 0], [30, 30], [0, 30]], "center_x": 15, "center_y": 15},
            {"id": 3, "name": "North East", "area_sqm": 12.0, "boundary_points": [[40, 0], [70, 0], [70, 30], [40, 30]], "center_x": 55, "center_y": 15},
        ]
    )

    assert [item["room"]["id"] for item in numbered] == [2, 3, 1]
    assert [item["number"] for item in numbered] == [1, 2, 3]


def test_build_stair_segments_uses_requested_axis_and_step_count():
    outline, step_segments = build_stair_segments(
        {
            "x": 10,
            "y": 20,
            "width": 80,
            "height": 40,
            "rotation_deg": 0,
            "step_count": 5,
            "step_axis": "horizontal",
        }
    )

    assert outline == [(10.0, 20.0), (90.0, 20.0), (90.0, 60.0), (10.0, 60.0)]
    assert len(step_segments) == 4
    assert step_segments[0] == ((26.0, 20.0), (26.0, 60.0))


def test_get_zkspc_style_uses_clean_label_and_is_stable():
    style_a = get_zkspc_style(3, floor_plan_id=12)
    style_b = get_zkspc_style(3, floor_plan_id=12)
    style_c = get_zkspc_style(4, floor_plan_id=12)

    assert style_a["color_hex"] == style_b["color_hex"]
    assert style_a["hatch_spacing"] == style_b["hatch_spacing"]
    assert style_a["label"] == "ЗКСПС №3"
    assert style_c["color_hex"] != style_a["color_hex"]


def test_build_zkspc_style_map_assigns_contrasting_colors_to_neighboring_zones():
    floor_plan_data = {
        "id": 7,
        "rooms": [
            {"id": 1, "boundary_points": [[0, 0], [50, 0], [50, 40], [0, 40]]},
            {"id": 2, "boundary_points": [[50, 0], [100, 0], [100, 40], [50, 40]]},
            {"id": 3, "boundary_points": [[0, 50], [50, 50], [50, 90], [0, 90]]},
        ],
        "zkspc_zones": [
            {"id": 1, "zone_number": 1, "room_ids": [1]},
            {"id": 2, "zone_number": 2, "room_ids": [2]},
            {"id": 3, "zone_number": 3, "room_ids": [3]},
        ],
    }

    style_map_a = build_zkspc_style_map(floor_plan_data)
    style_map_b = build_zkspc_style_map(floor_plan_data)

    assert style_map_a[1]["color_hex"] == style_map_b[1]["color_hex"]
    assert style_map_a[1]["color_hex"] != style_map_a[2]["color_hex"]
    assert style_map_a[1]["label"] == "ЗКСПС №1"
    assert style_map_a[1]["label_color"] == colors.black


def test_find_room_badge_center_prefers_top_left_but_stays_inside_polygon():
    room = {
        "id": 1,
        "boundary_points": [[20, 0], [80, 0], [80, 80], [0, 80], [0, 20], [20, 20]],
    }
    transform = PlanTransform(
        image_width=100.0,
        image_height=100.0,
        scale=1.0,
        offset_x=0.0,
        offset_y=0.0,
        scale_factor=10.0,
    )

    badge_center = find_room_badge_center(room, radius=10.0, transform=transform)

    assert badge_center is not None
    assert badge_center[0] >= 20.0
    assert badge_center[1] <= 35.0
    assert badge_center[0] < 45.0


def test_build_exterior_dimension_specs_collects_external_thickness_and_internal_junctions():
    walls = [
        {"id": 1, "x1": 40, "y1": 40, "x2": 360, "y2": 40, "thickness": 200},
        {"id": 2, "x1": 360, "y1": 40, "x2": 360, "y2": 200, "thickness": 200},
        {"id": 3, "x1": 360, "y1": 200, "x2": 40, "y2": 200, "thickness": 200},
        {"id": 4, "x1": 40, "y1": 200, "x2": 40, "y2": 40, "thickness": 200},
        {"id": 5, "x1": 200, "y1": 40, "x2": 200, "y2": 200, "thickness": 200},
        {"id": 6, "x1": 40, "y1": 120, "x2": 360, "y2": 120, "thickness": 200},
    ]

    specs = build_exterior_dimension_specs(walls, scale_factor=10.0)

    assert specs["top"].anchors == (30.0, 50.0, 200.0, 350.0, 370.0)
    assert specs["bottom"].anchors == (30.0, 50.0, 200.0, 350.0, 370.0)
    assert specs["left"].anchors == (30.0, 50.0, 120.0, 190.0, 210.0)
    assert specs["right"].anchors == (30.0, 50.0, 120.0, 190.0, 210.0)


def test_choose_plan_rotation_prefers_quarter_turn_for_tall_plan_in_wide_area():
    rotation = choose_plan_rotation(
        {
            "image_width": 180,
            "image_height": 420,
        },
        drawing_width=320,
        drawing_height=180,
    )

    assert rotation == 1


def test_explication_layout_stays_inside_safe_area_and_does_not_overlap_plan():
    register_pdf_fonts()
    page = DrawingPage(
        page_format=PAGESIZE_A3_LANDSCAPE,
        page_number=1,
        sheet_kind="zkspc",
        floor_plan_data={
            "id": 10,
            "image_width": 400,
            "image_height": 260,
            "scale_factor": 10.0,
            "walls": [
                {"id": 1, "x1": 30, "y1": 30, "x2": 370, "y2": 30, "thickness": 200},
                {"id": 2, "x1": 370, "y1": 30, "x2": 370, "y2": 230, "thickness": 200},
                {"id": 3, "x1": 370, "y1": 230, "x2": 30, "y2": 230, "thickness": 200},
                {"id": 4, "x1": 30, "y1": 230, "x2": 30, "y2": 30, "thickness": 200},
            ],
            "rooms": [
                {"id": 1, "name": "A", "area_sqm": 12.0, "boundary_points": [[40, 40], [180, 40], [180, 120], [40, 120]], "center_x": 110, "center_y": 80},
                {"id": 2, "name": "B", "area_sqm": 16.0, "boundary_points": [[190, 40], [360, 40], [360, 120], [190, 120]], "center_x": 275, "center_y": 80},
                {"id": 3, "name": "C", "area_sqm": 18.0, "boundary_points": [[40, 130], [180, 130], [180, 220], [40, 220]], "center_x": 110, "center_y": 175},
                {"id": 4, "name": "D", "area_sqm": 22.0, "boundary_points": [[190, 130], [360, 130], [360, 220], [190, 220]], "center_x": 275, "center_y": 175},
            ],
            "zkspc_zones": [
                {"id": 1, "zone_number": 1, "room_ids": [1, 2, 3, 4]},
            ],
        },
    )
    numbered_rooms = build_room_numbering(page.floor_plan_data["rooms"])
    content_layout = page._build_content_layout(canvas.Canvas(io.BytesIO()), numbered_rooms)
    tolerance = 1e-6

    content_left = page.drawing_x + DRAWING_SAFE_MARGIN
    content_bottom = page.drawing_y + DRAWING_SAFE_MARGIN
    content_right = page.drawing_x + page.drawing_width - DRAWING_SAFE_MARGIN
    content_top = page.drawing_y + page.drawing_height - DRAWING_SAFE_MARGIN

    assert float(content_layout["plan_x"]) >= content_left - tolerance
    assert float(content_layout["plan_y"]) >= content_bottom - tolerance
    assert float(content_layout["plan_x"]) + float(content_layout["plan_width"]) <= content_right + tolerance
    assert float(content_layout["plan_y"]) + float(content_layout["plan_height"]) <= content_top + tolerance

    table = content_layout["explication_layout"]
    assert table is not None

    explication_x = float(content_layout["explication_x"])
    explication_y = float(content_layout["explication_y"])
    explication_width = float(table["width"])
    explication_height = float(table["height"])
    assert explication_x >= content_left - tolerance
    assert explication_y >= content_bottom - tolerance
    assert explication_x + explication_width <= content_right + tolerance
    assert explication_y + explication_height <= content_top + tolerance

    plan_left = float(content_layout["plan_x"])
    plan_bottom = float(content_layout["plan_y"])
    plan_right = plan_left + float(content_layout["plan_width"])
    plan_top = plan_bottom + float(content_layout["plan_height"])
    table_right = explication_x + explication_width
    table_top = explication_y + explication_height
    horizontal_gap = min(abs(plan_left - table_right), abs(explication_x - plan_right))
    vertical_gap = min(abs(plan_bottom - table_top), abs(explication_y - plan_top))

    assert plan_right <= explication_x - EXPLICATION_GAP or table_right <= plan_left - EXPLICATION_GAP or plan_top <= explication_y - EXPLICATION_GAP or table_top <= plan_bottom - EXPLICATION_GAP
    assert max(horizontal_gap, vertical_gap) >= EXPLICATION_GAP


def test_exterior_dimension_spec_uses_fixed_arrow_and_text_sizes(monkeypatch):
    register_pdf_fonts()
    page = DrawingPage(page_format=PAGESIZE_A3_LANDSCAPE, page_number=1)
    canvas_obj = canvas.Canvas(io.BytesIO())
    transform = PlanTransform(
        image_width=200.0,
        image_height=120.0,
        scale=1.0,
        offset_x=0.0,
        offset_y=0.0,
        scale_factor=10.0,
    )
    spec = ExteriorDimensionSpec(
        side="top",
        orientation="horizontal",
        outer_coord=20.0,
        anchors=(20.0, 80.0, 160.0),
    )
    arrow_sizes: list[float] = []
    captured_text_sizes: list[float] = []

    monkeypatch.setattr(page, "_draw_dimension_arrow", lambda _canvas, _tip, _direction, size: arrow_sizes.append(size))
    original_draw_centred_string = canvas_obj.drawCentredString

    def capture_draw_centred_string(x, y, text):
        captured_text_sizes.append(canvas_obj._fontsize)
        return original_draw_centred_string(x, y, text)

    monkeypatch.setattr(canvas_obj, "drawCentredString", capture_draw_centred_string)

    page._draw_exterior_dimension_spec(canvas_obj, spec, transform, 0.5)

    assert arrow_sizes
    assert all(size == DIMENSION_ARROW_SIZE for size in arrow_sizes)
    assert captured_text_sizes
    assert all(size == DIMENSION_TEXT_FONT_SIZE for size in captured_text_sizes)


def test_short_horizontal_dimension_label_moves_outside_segment():
    register_pdf_fonts()
    page = DrawingPage(page_format=PAGESIZE_A3_LANDSCAPE, page_number=1)
    canvas_obj = canvas.Canvas(io.BytesIO())
    transform = PlanTransform(
        image_width=100.0,
        image_height=100.0,
        scale=1.0,
        offset_x=0.0,
        offset_y=0.0,
        scale_factor=100.0,
    )
    spec = ExteriorDimensionSpec(
        side="top",
        orientation="horizontal",
        outer_coord=20.0,
        anchors=(10.0, 16.0),
    )
    captured_positions: list[tuple[float, float, str]] = []
    original_draw_centred_string = canvas_obj.drawCentredString

    def capture_draw_centred_string(x, y, text):
        captured_positions.append((x, y, text))
        return original_draw_centred_string(x, y, text)

    canvas_obj.drawCentredString = capture_draw_centred_string

    page._draw_exterior_dimension_spec(canvas_obj, spec, transform, 0.5)

    assert captured_positions
    text_x, text_y, text_value = captured_positions[0]
    dimension_y = 20.0 - DIMENSION_LINE_OFFSET
    assert text_value == "600"
    assert text_x > 16.0 + DIMENSION_ARROW_SIZE
    assert text_y < dimension_y - (DIMENSION_TEXT_GAP - 0.1)


def test_bottom_horizontal_dimension_label_keeps_visual_gap_from_line():
    register_pdf_fonts()
    page = DrawingPage(page_format=PAGESIZE_A3_LANDSCAPE, page_number=1)
    canvas_obj = canvas.Canvas(io.BytesIO())
    transform = PlanTransform(
        image_width=100.0,
        image_height=100.0,
        scale=1.0,
        offset_x=0.0,
        offset_y=0.0,
        scale_factor=100.0,
    )
    spec = ExteriorDimensionSpec(
        side="bottom",
        orientation="horizontal",
        outer_coord=80.0,
        anchors=(10.0, 60.0),
    )
    captured_positions: list[tuple[float, float, str]] = []
    original_draw_centred_string = canvas_obj.drawCentredString

    def capture_draw_centred_string(x, y, text):
        captured_positions.append((x, y, text))
        return original_draw_centred_string(x, y, text)

    canvas_obj.drawCentredString = capture_draw_centred_string

    page._draw_exterior_dimension_spec(canvas_obj, spec, transform, 0.5)

    assert captured_positions
    _text_x, text_y, text_value = captured_positions[0]
    dimension_y = 80.0 + DIMENSION_LINE_OFFSET
    assert text_value == "5000"
    assert text_y > dimension_y + (DIMENSION_TEXT_GAP + (DIMENSION_TEXT_FONT_SIZE * 0.4))


def test_place_plan_text_pdf_returns_none_when_every_slot_is_blocked():
    register_pdf_fonts()
    canvas_obj = canvas.Canvas(io.BytesIO())

    placement = _place_plan_text_pdf(
        canvas_obj,
        text="ARK",
        font_size=10,
        anchor=(40.0, 20.0),
        obstacles=[{"x": 0.0, "y": 0.0, "width": 80.0, "height": 40.0}],
        bounds={"x": 0.0, "y": 0.0, "width": 80.0, "height": 40.0},
        strategy="anchor",
        symbol_half_width=8.0,
        symbol_half_height=8.0,
    )

    assert placement is None


def test_room_badge_layout_avoids_existing_label_obstacles():
    register_pdf_fonts()
    canvas_obj = canvas.Canvas(io.BytesIO())
    transform = PlanTransform(
        image_width=120.0,
        image_height=80.0,
        scale=1.0,
        offset_x=0.0,
        offset_y=0.0,
        scale_factor=10.0,
    )
    room = {
        "id": 1,
        "boundary_points": [[10, 10], [110, 10], [110, 70], [10, 70]],
        "center_x": 60,
        "center_y": 40,
    }
    blocking_label = {"x": 10.0, "y": 10.0, "width": 42.0, "height": 20.0}

    badge_layout = _find_room_badge_rect(
        canvas_obj,
        room,
        "1",
        radius=8.0,
        font_size=10.0,
        transform=transform,
        obstacles=[blocking_label],
        bounds={"x": 0.0, "y": 0.0, "width": 120.0, "height": 80.0},
    )

    assert badge_layout is not None
    assert badge_layout["rect"] is not None
    assert not _rects_intersect(badge_layout["rect"], blocking_label)


def test_display_cable_routes_pdf_spreads_overlapping_segments():
    transform = PlanTransform(
        image_width=200.0,
        image_height=120.0,
        scale=1.0,
        offset_x=0.0,
        offset_y=0.0,
        scale_factor=10.0,
    )

    routes = [
        {"id": 1, "route_number": 1, "polyline_points": [[10, 10], [10, 60], [80, 60]]},
        {"id": 2, "route_number": 2, "polyline_points": [[10, 10], [10, 60], [80, 60]]},
    ]

    display = build_display_cable_routes_pdf(routes, transform)

    assert display[1] != display[2]
    assert display[1][0][0] == pytest.approx(9.2)
    assert display[1][1][0] == pytest.approx(9.2)
    assert display[2][0][0] == pytest.approx(10.8)
    assert display[2][1][0] == pytest.approx(10.8)
    assert display[1][2][1] == pytest.approx(59.2)
    assert display[2][2][1] == pytest.approx(60.8)


def test_display_cable_routes_pdf_spreads_four_overlapping_segments_symmetrically():
    transform = PlanTransform(
        image_width=200.0,
        image_height=120.0,
        scale=1.0,
        offset_x=0.0,
        offset_y=0.0,
        scale_factor=10.0,
    )

    routes = [
        {"id": 1, "route_number": 1, "polyline_points": [[10, 10], [10, 60]]},
        {"id": 2, "route_number": 2, "polyline_points": [[10, 10], [10, 60]]},
        {"id": 3, "route_number": 3, "polyline_points": [[10, 10], [10, 60]]},
        {"id": 4, "route_number": 4, "polyline_points": [[10, 10], [10, 60]]},
    ]

    display = build_display_cable_routes_pdf(routes, transform)

    assert display[1][0][0] == pytest.approx(7.6)
    assert display[2][0][0] == pytest.approx(9.2)
    assert display[3][0][0] == pytest.approx(10.8)
    assert display[4][0][0] == pytest.approx(12.4)


def test_resolve_zc_terminator_point_pdf_uses_side_candidate_when_forward_is_blocked():
    zc_point = _resolve_zc_terminator_point_pdf(
        {"device_ids": [11]},
        [(0.0, 0.0), (26.0, 0.0), (40.0, 0.0), (59.4, 0.0)],
        {11: (40.0, 0.0)},
        [{"x": 48.0, "y": -8.0, "width": 20.0, "height": 16.0}],
    )

    assert zc_point == (40.0, -19.4)


def test_generic_sheet_draws_ark_and_zc_labels_for_signal_design():
    register_pdf_fonts()
    page = DrawingPage(
        page_format=PAGESIZE_A3_LANDSCAPE,
        page_number=1,
        sheet_kind="generic",
        floor_plan_data={
            "id": 1,
            "name": "Floor 1",
            "floor_number": 1,
            "image_width": 200,
            "image_height": 120,
            "scale_factor": 10.0,
            "walls": [
                {"id": 1, "x1": 20, "y1": 20, "x2": 180, "y2": 20, "thickness": 200},
                {"id": 2, "x1": 180, "y1": 20, "x2": 180, "y2": 100, "thickness": 200},
                {"id": 3, "x1": 180, "y1": 100, "x2": 20, "y2": 100, "thickness": 200},
                {"id": 4, "x1": 20, "y1": 100, "x2": 20, "y2": 20, "thickness": 200},
            ],
            "doors": [{"id": 1, "x": 80, "y": 15, "width": 40, "height": 10, "wall_id": 1}],
            "windows": [],
            "stairs": [],
            "fire_alarms": [{"id": 11, "x": 90, "y": 60, "device_type": "smoke_detector", "zone": "1", "address": "1"}],
            "signal_instruments": [{"id": 21, "x": 30, "y": 30, "instrument_type": "control_panel"}],
            "cable_routes": [{
                "id": 31,
                "system_type": "non_addressable",
                "route_kind": "zone_loop",
                "route_number": 1,
                "polyline_points": [[30, 30], [30, 60], [90, 60], [104.4, 60]],
            }],
        },
    )
    drawing = io.BytesIO()
    canvas_obj = canvas.Canvas(drawing)
    captured_strings: list[str] = []
    original_draw_centred_string = canvas_obj.drawCentredString

    def capture_draw_centred_string(x, y, text):
        captured_strings.append(str(text))
        return original_draw_centred_string(x, y, text)

    canvas_obj.drawCentredString = capture_draw_centred_string
    page.draw(canvas_obj)

    assert "ARK" in captured_strings
    assert "ZC" in captured_strings
