"""PDF routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from backend.dependencies import get_documents_use_cases
from backend.modules.documents.application.use_cases import DocumentsUseCases


router = APIRouter(tags=["pdf"])


@router.post("/api/projects/{project_id}/generate-pdf")
def generate_pdf(
    project_id: int,
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> FileResponse:
    pdf_path = service.generate_project_pdf(project_id)
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=pdf_path.split("/")[-1].split("\\")[-1],
    )
