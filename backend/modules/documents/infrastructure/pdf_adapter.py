"""PDF generator adapter."""

from __future__ import annotations

from backend.pdf_generator import generate_project_pdf


class PdfGeneratorAdapter:
    """Adapter around the legacy PDF generator function."""

    def generate(
        self,
        *,
        project_data: dict,
        floor_plans_data: list[dict],
        general_data: dict | None,
        general_instructions: dict | None,
        conventional_symbols: dict | None,
        equipment_specification: dict | None,
        power_consumption_calculation: dict | None,
        additional_info: dict | None,
        output_dir: str,
    ) -> str:
        return generate_project_pdf(
            project_data=project_data,
            floor_plans_data=floor_plans_data,
            general_data=general_data,
            general_instructions=general_instructions,
            conventional_symbols=conventional_symbols,
            equipment_specification=equipment_specification,
            power_consumption_calculation=power_consumption_calculation,
            additional_info=additional_info,
            output_dir=output_dir,
        )
