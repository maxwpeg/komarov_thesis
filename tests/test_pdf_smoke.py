"""PDF smoke tests."""

from __future__ import annotations

import io
from pathlib import Path

from reportlab.pdfgen import canvas

from backend.bootstrap import register_pdf_fonts
from backend.pdf_generator import generate_project_pdf
from DrawingPage import DrawingPage
from consts import PAGESIZE_A3_LANDSCAPE


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
