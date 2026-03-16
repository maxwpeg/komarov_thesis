"""Compatibility shim for PDF generation."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.modules.documents.application.use_cases import DocumentsUseCases
from backend.modules.documents.infrastructure.pdf_adapter import PdfGeneratorAdapter
from backend.modules.documents.infrastructure.sqlalchemy_repository import SqlAlchemyDocumentReadRepository


class PdfService:
    """Backward-compatible wrapper over modular document use cases."""

    def __init__(self, db: Session):
        self._use_cases = DocumentsUseCases(
            repository=SqlAlchemyDocumentReadRepository(db),
            pdf_port=PdfGeneratorAdapter(),
        )

    def generate_project_pdf(self, project_id: int) -> str:
        return self._use_cases.generate_project_pdf(project_id)
