"""PDF generator adapter."""

from __future__ import annotations

from backend.pdf_generator import generate_project_pdf


class PdfGeneratorAdapter:
    """Adapter around the legacy PDF generator function."""

    def generate(self, *, project_data: dict, floor_plans_data: list[dict], output_dir: str) -> str:
        return generate_project_pdf(
            project_data=project_data,
            floor_plans_data=floor_plans_data,
            output_dir=output_dir,
        )
