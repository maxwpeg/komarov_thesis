"""Repository and adapter contracts for documents."""

from __future__ import annotations

from typing import Protocol


class DocumentReadRepository(Protocol):
    """Read-side contract for project PDF generation."""

    def get_project(self, project_id: int):
        """Return a project aggregate."""

    def list_project_floor_plans(self, project_id: int) -> list:
        """Return floor plans for a project."""

    def get_project_equipment_specification(self, project_id: int) -> dict:
        """Return a rendered, editable equipment specification for the project."""

    def get_project_power_consumption_calculation(self, project_id: int) -> dict:
        """Return the rendered power consumption calculation payload for the project."""

    def get_project_general_data(self, project_id: int) -> dict:
        """Return the rendered general data payload for the project."""

    def get_project_general_instructions(self, project_id: int) -> dict:
        """Return the rendered general instructions payload for the project."""

    def get_project_conventional_symbols(self, project_id: int) -> dict:
        """Return the rendered conventional symbols payload for the project."""

    def get_project_additional_info(self, project_id: int) -> dict:
        """Return the rendered additional info payload for the project."""

    def update_project_power_consumption_calculation(self, project_id: int, payload) -> dict:
        """Persist editable power consumption calculation overrides for the project."""

    def update_project_general_data(self, project_id: int, payload) -> dict:
        """Persist editable general data overrides for the project."""

    def update_project_general_instructions(self, project_id: int, payload) -> dict:
        """Persist editable general instructions overrides for the project."""

    def update_project_additional_info(self, project_id: int, payload) -> dict:
        """Persist the project-level additional info text."""


class PdfPort(Protocol):
    """Adapter contract for PDF generation."""

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
        """Generate a PDF and return the file path."""
