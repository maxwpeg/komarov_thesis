"""PDF smoke tests."""

from __future__ import annotations

import io
from pathlib import Path

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

import DrawingPage as drawing_page_module
from backend.bootstrap import register_pdf_fonts
from backend.pdf_generator import generate_project_pdf
from DrawingPage import DrawingPage, PlanTransform, _get_soue_device_code, _soue_device_symbol_half_extents
from Project import Project
from consts import PAGESIZE_A3_LANDSCAPE, PAGESIZE_A4


class _RecordedPath:
    def __init__(self):
        self.operations: list[tuple[str, float, float]] = []

    def moveTo(self, x, y):
        self.operations.append(("moveTo", float(x), float(y)))

    def lineTo(self, x, y):
        self.operations.append(("lineTo", float(x), float(y)))

    def close(self):
        self.operations.append(("close", 0.0, 0.0))


class _RecordedCanvas:
    def __init__(self):
        self.paths: list[_RecordedPath] = []

    def saveState(self):
        return None

    def restoreState(self):
        return None

    def setStrokeColor(self, *_args, **_kwargs):
        return None

    def setFillColor(self, *_args, **_kwargs):
        return None

    def setLineWidth(self, *_args, **_kwargs):
        return None

    def setLineCap(self, *_args, **_kwargs):
        return None

    def setLineJoin(self, *_args, **_kwargs):
        return None

    def rect(self, *_args, **_kwargs):
        return None

    def line(self, *_args, **_kwargs):
        return None

    def beginPath(self):
        path = _RecordedPath()
        self.paths.append(path)
        return path

    def drawPath(self, *_args, **_kwargs):
        return None


def test_generate_project_pdf_smoke(tmp_path: Path):
    register_pdf_fonts()
    pdf_path = generate_project_pdf(
        project_data={
            "project_type": "PS",
            "number": 1,
            "year": 2026,
            "contractor": "Contractor",
            "engineer": "Engineer",
            "cpe": "CPE",
            "checker": "Checker",
            "facility": "Facility",
            "facility_address": "Address",
            "project_description": "Description",
            "stage": "R",
        },
        floor_plans_data=[
            {
                "id": 1,
                "name": "Floor 1",
                "floor_number": 1,
                "image_width": 400,
                "image_height": 240,
                "scale_factor": 10.0,
                "walls": [
                    {"id": 1, "x1": 40, "y1": 40, "x2": 360, "y2": 40, "thickness": 200},
                    {"id": 2, "x1": 360, "y1": 40, "x2": 360, "y2": 200, "thickness": 200},
                    {"id": 3, "x1": 360, "y1": 200, "x2": 40, "y2": 200, "thickness": 200},
                    {"id": 4, "x1": 40, "y1": 200, "x2": 40, "y2": 40, "thickness": 200},
                ],
                "doors": [
                    {"id": 1, "x": 160, "y": 35, "width": 60, "height": 10, "wall_id": 1},
                ],
                "windows": [
                    {"id": 1, "x": 355, "y": 90, "width": 10, "height": 70, "wall_id": 2},
                ],
                "fire_alarms": [{"id": 1, "x": 200, "y": 120, "device_type": "smoke_detector", "zone": "1", "address": "1"}],
                "signal_instruments": [{"id": 2, "x": 70, "y": 70, "instrument_type": "control_panel"}],
                "cable_routes": [
                    {
                        "id": 3,
                        "system_type": "non_addressable",
                        "route_kind": "zone_loop",
                        "route_number": 1,
                        "polyline_points": [[70, 70], [70, 120], [200, 120], [214.4, 120]],
                    }
                ],
            }
        ],
        output_dir=str(tmp_path),
    )
    assert Path(pdf_path).exists()
    assert Path(pdf_path).suffix == ".pdf"


def test_special_sheet_kinds_skip_top_centered_title(monkeypatch):
    register_pdf_fonts()
    captured_titles: list[str] = []
    page = DrawingPage(
        page_format=PAGESIZE_A3_LANDSCAPE,
        page_number=1,
        title="ЗКСПС - Floor 1",
        sheet_kind="zkspc",
    )

    monkeypatch.setattr(page, "draw_outer_border", lambda _canvas: None)
    monkeypatch.setattr(page, "draw_main_title_box", lambda _canvas, _box_type: None)
    monkeypatch.setattr(page, "fill_main_title_box", lambda _canvas, _box_type: None)
    monkeypatch.setattr(page, "fit_text_in_box", lambda _canvas, text, *_args, **_kwargs: captured_titles.append(text))

    page.draw(canvas.Canvas(io.BytesIO()))

    assert captured_titles == []


def test_generic_sheet_kind_keeps_top_centered_title(monkeypatch):
    register_pdf_fonts()
    captured_titles: list[str] = []
    page = DrawingPage(
        page_format=PAGESIZE_A3_LANDSCAPE,
        page_number=1,
        title="СПС - Floor 1",
        sheet_kind="generic",
    )

    monkeypatch.setattr(page, "draw_outer_border", lambda _canvas: None)
    monkeypatch.setattr(page, "draw_main_title_box", lambda _canvas, _box_type: None)
    monkeypatch.setattr(page, "fill_main_title_box", lambda _canvas, _box_type: None)
    monkeypatch.setattr(page, "fit_text_in_box", lambda _canvas, text, *_args, **_kwargs: captured_titles.append(text))

    page.draw(canvas.Canvas(io.BytesIO()))

    assert captured_titles == ["СПС - Floor 1"]


def test_sheet_kind_sets_title_of_the_drawing_field():
    register_pdf_fonts()

    assert DrawingPage(page_format=PAGESIZE_A3_LANDSCAPE, page_number=1, sheet_kind="zkspc").creds["Title of the Drawing"] == "План ЗКСПС"
    assert DrawingPage(page_format=PAGESIZE_A3_LANDSCAPE, page_number=1, sheet_kind="sps").creds["Title of the Drawing"] == "План СПС"
    assert DrawingPage(page_format=PAGESIZE_A3_LANDSCAPE, page_number=1, sheet_kind="soue").creds["Title of the Drawing"] == "План СОУЭ"
    assert DrawingPage(page_format=PAGESIZE_A3_LANDSCAPE, page_number=1, sheet_kind="generic").creds["Title of the Drawing"] == "Общие данные"


def test_soue_sheet_draws_only_soue_devices_and_routes(monkeypatch):
    register_pdf_fonts()
    page = DrawingPage(
        page_format=PAGESIZE_A3_LANDSCAPE,
        page_number=1,
        title="СОУЭ - Floor 1",
        sheet_kind="soue",
    )
    captured: dict[str, list[dict]] = {
        "routes": [],
        "devices": [],
        "instruments": [],
        "fire_alarms": [],
    }

    monkeypatch.setattr(page, "_draw_walls", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(page, "_draw_openings", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(page, "_draw_stairs", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(page, "_draw_exterior_dimensions", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(page, "_collect_geometry_obstacles", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(page, "_draw_cable_routes", lambda _c, routes, *_args, **_kwargs: captured["routes"].extend(routes) or [])
    monkeypatch.setattr(page, "_draw_soue_devices", lambda _c, devices, *_args, **_kwargs: captured["devices"].extend(devices))
    monkeypatch.setattr(page, "_draw_soue_device_annotations", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(page, "_draw_signal_instruments", lambda _c, instruments, *_args, **_kwargs: captured["instruments"].extend(instruments))
    monkeypatch.setattr(page, "_draw_fire_alarms", lambda _c, alarms, *_args, **_kwargs: captured["fire_alarms"].extend(alarms))

    page.draw_floor_plan_elements(
        canvas.Canvas(io.BytesIO()),
        {
            "id": 1,
            "name": "Floor 1",
            "floor_number": 1,
            "image_width": 400,
            "image_height": 240,
            "scale_factor": 10.0,
            "walls": [
                {"id": 1, "x1": 40, "y1": 40, "x2": 360, "y2": 40, "thickness": 200},
                {"id": 2, "x1": 360, "y1": 40, "x2": 360, "y2": 200, "thickness": 200},
                {"id": 3, "x1": 360, "y1": 200, "x2": 40, "y2": 200, "thickness": 200},
                {"id": 4, "x1": 40, "y1": 200, "x2": 40, "y2": 40, "thickness": 200},
            ],
            "doors": [],
            "windows": [],
            "stairs": [],
            "fire_alarms": [{"id": 10, "x": 200, "y": 120, "device_type": "smoke_detector"}],
            "soue_devices": [
                {"id": 20, "x": 180, "y": 60, "device_type": "exit_sign", "device_model": "Выход-12"},
                {"id": 21, "x": 200, "y": 160, "device_type": "siren", "device_model": "Комптид-1"},
            ],
            "signal_instruments": [{"id": 30, "x": 70, "y": 70, "instrument_type": "control_panel"}],
            "cable_routes": [
                {
                    "id": 40,
                    "route_kind": "zone_loop",
                    "route_number": 1,
                    "subsystem_type": "sps",
                    "polyline_points": [[70, 70], [70, 120], [200, 120]],
                },
                {
                    "id": 41,
                    "route_kind": "siren_loop",
                    "route_number": 1,
                    "subsystem_type": "soue",
                    "polyline_points": [[70, 70], [120, 70], [180, 60]],
                },
            ],
        },
    )

    assert [route["id"] for route in captured["routes"]] == [41]
    assert [device["id"] for device in captured["devices"]] == [20, 21]
    assert [instrument["id"] for instrument in captured["instruments"]] == [30]
    assert captured["fire_alarms"] == []


def test_soue_device_code_uses_floor_and_type_specific_prefix():
    assert _get_soue_device_code({"device_type": "exit_sign", "device_number": 3}, floor_number=2) == "2BIAL2.3"
    assert _get_soue_device_code({"device_type": "siren", "device_number": 4}, floor_number=5) == "5BIAS1.4"


def test_sps_sheet_matches_editor_branch_visibility_without_instrument_deduplication(monkeypatch):
    register_pdf_fonts()
    page = DrawingPage(
        page_format=PAGESIZE_A3_LANDSCAPE,
        page_number=1,
        title="РЎРџРЎ - Floor 1",
        sheet_kind="sps",
    )
    captured: dict[str, list[dict]] = {
        "routes": [],
        "alarms": [],
        "instruments": [],
    }

    monkeypatch.setattr(page, "_draw_walls", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(page, "_draw_openings", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(page, "_draw_stairs", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(page, "_draw_exterior_dimensions", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(page, "_collect_geometry_obstacles", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(page, "_draw_cable_routes", lambda _c, routes, *_args, **_kwargs: captured["routes"].extend(routes) or [])
    monkeypatch.setattr(page, "_draw_fire_alarms", lambda _c, alarms, *_args, **_kwargs: captured["alarms"].extend(alarms))
    monkeypatch.setattr(page, "_draw_fire_alarm_annotations", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(page, "_draw_signal_instruments", lambda _c, instruments, *_args, **_kwargs: captured["instruments"].extend(instruments))

    page.draw_floor_plan_elements(
        canvas.Canvas(io.BytesIO()),
        {
            "id": 1,
            "name": "Floor 1",
            "floor_number": 1,
            "active_signal_system_type": "addressable",
            "image_width": 400,
            "image_height": 240,
            "scale_factor": 10.0,
            "walls": [
                {"id": 1, "x1": 40, "y1": 40, "x2": 360, "y2": 40, "thickness": 200},
                {"id": 2, "x1": 360, "y1": 40, "x2": 360, "y2": 200, "thickness": 200},
                {"id": 3, "x1": 360, "y1": 200, "x2": 40, "y2": 200, "thickness": 200},
                {"id": 4, "x1": 40, "y1": 200, "x2": 40, "y2": 40, "thickness": 200},
            ],
            "doors": [],
            "windows": [],
            "stairs": [],
            "fire_alarms": [
                {"id": 10, "x": 180, "y": 120, "device_type": "smoke_detector", "system_type": "addressable"},
                {"id": 11, "x": 220, "y": 120, "device_type": "manual_call_point", "system_type": "non_addressable"},
            ],
            "signal_instruments": [
                {"id": 30, "x": 70, "y": 70, "instrument_type": "control_panel", "system_type": "common"},
                {"id": 31, "x": 70, "y": 70, "instrument_type": "loop_controller", "system_type": "common", "name": "Контроллер"},
                {"id": 32, "x": 70, "y": 70, "instrument_type": "control_panel", "system_type": "addressable"},
            ],
            "cable_routes": [
                {
                    "id": 40,
                    "route_kind": "address_loop",
                    "route_number": 1,
                    "system_type": "addressable",
                    "subsystem_type": "sps",
                    "polyline_points": [[70, 70], [70, 120], [180, 120]],
                },
                {
                    "id": 41,
                    "route_kind": "zone_loop",
                    "route_number": 2,
                    "system_type": "non_addressable",
                    "subsystem_type": "sps",
                    "polyline_points": [[70, 70], [70, 140], [220, 120]],
                },
                {
                    "id": 42,
                    "route_kind": "siren_loop",
                    "route_number": 1,
                    "system_type": "common",
                    "subsystem_type": "soue",
                    "polyline_points": [[70, 70], [100, 70], [140, 80]],
                },
            ],
        },
    )

    assert [route["id"] for route in captured["routes"]] == [40]
    assert [alarm["id"] for alarm in captured["alarms"]] == [10]
    assert [instrument["id"] for instrument in captured["instruments"]] == [30, 31]


def test_soue_annotations_use_single_bial2_sequence_for_all_non_sirens(monkeypatch):
    register_pdf_fonts()
    page = DrawingPage(page_format=PAGESIZE_A3_LANDSCAPE, page_number=1, sheet_kind="soue")
    captured_strings: list[str] = []
    transform = PlanTransform(
        image_width=300.0,
        image_height=200.0,
        scale=1.0,
        offset_x=0.0,
        offset_y=0.0,
        scale_factor=10.0,
    )
    canvas_obj = canvas.Canvas(io.BytesIO())
    original_draw_centred_string = canvas_obj.drawCentredString

    monkeypatch.setattr(
        drawing_page_module,
        "_place_plan_text_pdf",
        lambda *_args, **kwargs: {
            "rect": {
                "x": float(kwargs["anchor"][0]) - 10.0,
                "y": float(kwargs["anchor"][1]) - 5.0,
                "width": 20.0,
                "height": 10.0,
            }
        },
    )

    def capture_draw_centred_string(x, y, text):
        captured_strings.append(str(text))
        return original_draw_centred_string(x, y, text)

    canvas_obj.drawCentredString = capture_draw_centred_string

    page._draw_soue_device_annotations(
        canvas_obj,
        [
            {"id": 1, "x": 40, "y": 40, "device_type": "exit_sign"},
            {"id": 2, "x": 80, "y": 40, "device_type": "speech"},
            {"id": 3, "x": 120, "y": 40, "device_type": "siren"},
        ],
        floor_number=2,
        transform=transform,
        obstacles=[],
        stage_bounds={"x": 0.0, "y": 0.0, "width": 200.0, "height": 200.0},
    )

    assert captured_strings == ["2BIAL2.1", "2BIAL2.2", "2BIAS1.1"]


def test_non_siren_soue_devices_share_same_pdf_footprint():
    assert _soue_device_symbol_half_extents("exit_sign") == _soue_device_symbol_half_extents("speech")


def test_siren_pdf_footprint_matches_editor_reference_geometry():
    half_width, half_height = _soue_device_symbol_half_extents("siren")

    assert abs(half_width - ((10.2 / 18.0) * 4.5 * mm)) < 1e-6
    assert abs(half_height - ((22.0 / 18.0) * 4.5 * mm)) < 1e-6


def test_smoke_fire_alarm_symbol_uses_editor_inner_polyline_geometry():
    recorded_canvas = _RecordedCanvas()

    drawing_page_module.draw_fire_alarm_symbol(recorded_canvas, 100.0, 50.0, "smoke_detector", size=18.0)

    assert len(recorded_canvas.paths) == 1
    assert recorded_canvas.paths[0].operations == [
        ("moveTo", 102.2, 43.4),
        ("lineTo", 98.8, 49.2),
        ("lineTo", 102.6, 49.2),
        ("lineTo", 97.8, 56.6),
        ("lineTo", 101.2, 50.8),
        ("lineTo", 97.4, 50.8),
    ]


def test_signal_instrument_label_falls_back_when_auto_placement_returns_none(monkeypatch):
    register_pdf_fonts()
    page = DrawingPage(page_format=PAGESIZE_A3_LANDSCAPE, page_number=1, sheet_kind="sps")
    captured_strings: list[str] = []
    transform = PlanTransform(
        image_width=300.0,
        image_height=200.0,
        scale=1.0,
        offset_x=0.0,
        offset_y=0.0,
        scale_factor=10.0,
    )
    canvas_obj = canvas.Canvas(io.BytesIO())
    original_draw_centred_string = canvas_obj.drawCentredString

    monkeypatch.setattr(drawing_page_module, "_place_plan_text_pdf", lambda *_args, **_kwargs: None)

    def capture_draw_centred_string(x, y, text):
        captured_strings.append(str(text))
        return original_draw_centred_string(x, y, text)

    canvas_obj.drawCentredString = capture_draw_centred_string

    page._draw_signal_instruments(
        canvas_obj,
        [
            {
                "id": 30,
                "x": 70,
                "y": 70,
                "instrument_type": "control_panel",
                "equipment_name": "",
                "name": "",
            }
        ],
        transform,
        obstacles=[],
        stage_bounds={"x": 0.0, "y": 0.0, "width": 200.0, "height": 200.0},
    )

    assert "ARK" in captured_strings


def test_generated_pdf_filename_uses_facility_name_with_cyrillic(tmp_path: Path):
    register_pdf_fonts()
    pdf_path = generate_project_pdf(
        project_data={
            "project_type": "PS",
            "number": 7,
            "year": 2026,
            "contractor": "Подрядчик",
            "engineer": "Инженер",
            "cpe": "ГИП",
            "checker": "Проверил",
            "facility": "АССП Тестовый объект",
            "facility_address": "Адрес",
            "project_description": "Описание",
            "stage": "Р",
        },
        floor_plans_data=[
            {
                "id": 1,
                "name": "Floor 1",
                "floor_number": 1,
                "image_width": 200,
                "image_height": 100,
                "scale_factor": 10.0,
                "walls": [],
                "doors": [],
                "windows": [],
                "stairs": [],
                "rooms": [],
                "dimensions": [],
                "fire_alarms": [],
                "soue_devices": [],
                "signal_instruments": [],
                "cable_routes": [],
                "zkspc_zones": [],
            }
        ],
        output_dir=str(tmp_path),
    )
    generated_name = Path(pdf_path).name
    assert generated_name.startswith("АССП Тестовый объект")
    assert generated_name.endswith(".pdf")


def test_project_launch_inserts_equipment_specification_one_sheet_later(monkeypatch):
    calls: list[str] = []
    project = Project(
        project_type="PS",
        number=1,
        year=2026,
        creds={"Facility": "Facility"},
        number_of_floors=0,
        floor_plans_data=[],
        general_instructions={
            "page_title": "Общие указания",
            "heading": "ОБЩИЕ УКАЗАНИЯ.",
            "local_sheet_title": "Общие указания",
            "blocks": [],
        },
        conventional_symbols={
            "page_title": "Условные графические обозначения",
            "heading": "УСЛОВНЫЕ ГРАФИЧЕСКИЕ ОБОЗНАЧЕНИЯ",
            "rows": [],
            "decode_lines": [],
        },
        equipment_specification={
            "project_id": 1,
            "page_title": "Spec",
            "column_headers": ["A", "B", "C", "D", "E", "F", "G", "H", "I"],
            "sections": [],
            "warnings": [],
        },
        power_consumption_calculation={
            "project_id": 1,
            "page_title": "Power",
            "categories": [],
            "summary_rows": [],
            "final_text": "Battery text",
        },
        additional_info={
            "page_title": "Доп. сведения",
            "heading": "ДОП. СВЕДЕНИЯ",
            "local_sheet_title": "Доп. сведения",
            "text": "Текст",
            "is_empty": False,
            "blocks": [{"kind": "paragraph", "text": "Текст"}],
        },
    )

    monkeypatch.setattr(project, "add_title_page", lambda signed=False: calls.append(f"title:{signed}"))
    monkeypatch.setattr(
        project,
        "add_general_data_page",
        lambda general_data=None, pagesize=PAGESIZE_A3_LANDSCAPE: calls.append("general_data"),
    )
    monkeypatch.setattr(
        project,
        "add_general_instructions_pages",
        lambda instructions=None, segments=None, pagesize=PAGESIZE_A4: calls.append("general_instructions"),
    )
    monkeypatch.setattr(
        project,
        "add_conventional_symbols_pages",
        lambda conventional_symbols=None, segments=None, pagesize=PAGESIZE_A4: calls.append("conventional_symbols"),
    )
    monkeypatch.setattr(project, "add_page", lambda pagesize, mtbox_type="1": calls.append(f"page:{pagesize}:{mtbox_type}"))
    monkeypatch.setattr(project, "add_drawing_page_with_image", lambda **kwargs: calls.append(f"drawing:{kwargs.get('sheet_kind')}"))
    monkeypatch.setattr(
        project,
        "add_equipment_specification_page",
        lambda specification=None, pagesize=PAGESIZE_A3_LANDSCAPE: calls.append("specification"),
    )
    monkeypatch.setattr(
        project,
        "add_power_consumption_calculation_pages",
        lambda calculation=None, pagesize=PAGESIZE_A4: calls.append("power"),
    )
    monkeypatch.setattr(
        project,
        "add_additional_info_pages",
        lambda additional_info=None, segments=None, pagesize=PAGESIZE_A4: calls.append("additional_info"),
    )

    project.launch()

    assert calls[:6] == [
        "title:False",
        "title:True",
        "general_data",
        "general_instructions",
        "conventional_symbols",
        f"page:{PAGESIZE_A4}:1",
    ]
    assert calls[-4:] == [f"page:{PAGESIZE_A3_LANDSCAPE}:1", "specification", "power", "additional_info"]
