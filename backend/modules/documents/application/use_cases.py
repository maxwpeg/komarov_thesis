"""Explicit application use cases for documents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.config import settings
from backend.errors import AppError
from backend.modules.documents.infrastructure.pdf_adapter import PdfGeneratorAdapter
from backend.modules.documents.infrastructure.sqlalchemy_repository import SqlAlchemyDocumentReadRepository
from backend.modules.shared.infrastructure.runtime import NoOpEventPublisher


@dataclass(slots=True)
class DocumentsUseCases:
    """Document generation use cases."""

    repository: SqlAlchemyDocumentReadRepository
    pdf_port: PdfGeneratorAdapter
    events: Any | None = None

    def __post_init__(self) -> None:
        if self.events is None:
            self.events = NoOpEventPublisher()

    def generate_project_pdf(self, project_id: int) -> str:
        project = self.repository.get_project(project_id)
        floor_plans = self.repository.list_project_floor_plans(project_id)
        if not floor_plans:
            raise AppError(400, "floor_plans_missing", "No floor plans found for this project")
        pdf_path = self.pdf_port.generate(
            project_data=project.to_dict(),
            floor_plans_data=[floor_plan.to_dict(include_elements=True) for floor_plan in floor_plans],
            output_dir=str(settings.outputs_dir),
        )
        self.events.publish(
            "project_pdf_generated",
            {"category": "documents", "use_case": "GenerateProjectPdf", "project_id": project_id},
        )
        return pdf_path
