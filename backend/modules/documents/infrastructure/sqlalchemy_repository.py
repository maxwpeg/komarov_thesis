"""SQLAlchemy repository for document generation."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.errors import AppError
from backend.modules.shared.infrastructure.persistence.models import FloorPlan as FloorPlanModel
from backend.modules.shared.infrastructure.persistence.models import Project as ProjectModel


class SqlAlchemyDocumentReadRepository:
    """Read repository for project document generation."""

    def __init__(self, session: Session):
        self.session = session

    def get_project(self, project_id: int) -> ProjectModel:
        project = self.session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if project is None:
            raise AppError(404, "project_not_found", "Project not found")
        return project

    def list_project_floor_plans(self, project_id: int) -> list[FloorPlanModel]:
        return self.session.query(FloorPlanModel).filter(FloorPlanModel.project_id == project_id).all()
