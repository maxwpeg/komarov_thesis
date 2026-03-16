"""Repository and adapter contracts for documents."""

from __future__ import annotations

from typing import Protocol


class DocumentReadRepository(Protocol):
    """Read-side contract for project PDF generation."""

    def get_project(self, project_id: int):
        """Return a project aggregate."""

    def list_project_floor_plans(self, project_id: int) -> list:
        """Return floor plans for a project."""


class PdfPort(Protocol):
    """Adapter contract for PDF generation."""

    def generate(self, *, project_data: dict, floor_plans_data: list[dict], output_dir: str) -> str:
        """Generate a PDF and return the file path."""
