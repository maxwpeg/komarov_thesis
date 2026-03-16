"""SQLAlchemy-backed project repository."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.errors import AppError
from backend.modules.shared.infrastructure.persistence.models import Project as ProjectModel
from backend.modules.shared.infrastructure.persistence.models import ProjectYearCounter
from backend.modules.projects.domain.entities import ProjectRecord
from backend.modules.projects.ports.repositories import ProjectRepository
from backend.project_codes import build_project_code, normalize_project_code
from backend.schemas import ProjectCreate, ProjectUpdate


class SqlAlchemyProjectRepository(ProjectRepository):
    """Repository implementation over the current SQLAlchemy schema."""

    def __init__(self, session: Session):
        self.session = session

    def list(self, skip: int = 0, limit: int = 100) -> list[ProjectRecord]:
        projects = self.session.query(ProjectModel).offset(skip).limit(limit).all()
        return [ProjectRecord.from_model(project) for project in projects]

    def get(self, project_id: int) -> ProjectRecord:
        project = self._get_model(project_id)
        normalized_code = normalize_project_code(project.code)
        if normalized_code != project.code:
            project.code = normalized_code
            project.updated_at = datetime.now(timezone.utc)
            self.session.flush()
        return ProjectRecord.from_model(project)

    def create(self, payload: ProjectCreate) -> ProjectRecord:
        year = payload.year
        counter = self._get_or_create_year_counter(year)
        number = counter.last_number + 1
        project = ProjectModel(
            name=payload.name,
            project_type=payload.project_type,
            number=number,
            year=year,
            code=build_project_code(number=number, year=year, project_type=payload.project_type),
            contractor=payload.contractor,
            engineer=payload.engineer,
            cpe=payload.cpe,
            checker=payload.checker,
            facility=payload.facility,
            facility_address=payload.facility_address,
            project_description=payload.project_description,
            stage=payload.stage,
            number_of_floors=payload.number_of_floors,
        )
        counter.last_number = number
        self.session.add(project)
        self.session.flush()
        return ProjectRecord.from_model(project)

    def update(self, project_id: int, payload: ProjectUpdate) -> ProjectRecord:
        project = self._get_model(project_id)
        previous_year = project.year
        updates = payload.model_dump(exclude_unset=True)
        for field, value in updates.items():
            setattr(project, field, value)

        if "year" in updates and project.year != previous_year:
            project.number = self._smallest_free_project_number(project.year, exclude_project_id=project.id)
            target_counter = self._get_or_create_year_counter(project.year)
            target_counter.last_number = max(target_counter.last_number, project.number)

        if "year" in updates or "project_type" in updates:
            project.code = build_project_code(
                number=project.number,
                year=project.year,
                project_type=project.project_type,
            )

        project.updated_at = datetime.now(timezone.utc)
        self.session.flush()
        return ProjectRecord.from_model(project)

    def delete(self, project_id: int) -> None:
        project = self._get_model(project_id)
        self.session.delete(project)
        self.session.flush()

    def _get_model(self, project_id: int) -> ProjectModel:
        project = self.session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if project is None:
            raise AppError(404, "project_not_found", "Project not found")
        return project

    def _get_or_create_year_counter(self, year: int) -> ProjectYearCounter:
        counter = self.session.query(ProjectYearCounter).filter(ProjectYearCounter.year == year).first()
        existing_max = (
            self.session.query(func.max(ProjectModel.number))
            .filter(ProjectModel.year == year)
            .scalar()
        ) or 0
        if counter is None:
            counter = ProjectYearCounter(year=year, last_number=existing_max)
            self.session.add(counter)
            self.session.flush()
            return counter
        if counter.last_number < existing_max:
            counter.last_number = existing_max
            self.session.flush()
        return counter

    def _smallest_free_project_number(self, year: int, exclude_project_id: int | None = None) -> int:
        query = self.session.query(ProjectModel.number).filter(ProjectModel.year == year)
        if exclude_project_id is not None:
            query = query.filter(ProjectModel.id != exclude_project_id)

        used_numbers = sorted(number for (number,) in query.all() if number is not None)
        candidate = 1
        for number in used_numbers:
            if number < candidate:
                continue
            if number != candidate:
                break
            candidate += 1
        return candidate
