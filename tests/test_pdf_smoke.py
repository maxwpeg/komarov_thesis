"""PDF smoke tests."""

from __future__ import annotations

from pathlib import Path

from backend.bootstrap import register_pdf_fonts
from backend.pdf_generator import generate_project_pdf


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
                "fire_alarms": [{"id": 1, "x": 200, "y": 120, "device_type": "IP212"}],
            }
        ],
        output_dir=str(tmp_path),
    )
    assert Path(pdf_path).exists()
    assert Path(pdf_path).suffix == ".pdf"
