"""Project application service."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.errors import AppError
from backend.models import Project as ProjectModel
from backend.models import ProjectYearCounter
from backend.project_codes import build_project_code, normalize_project_code
from backend.schemas import ProjectCreate, ProjectUpdate


class ProjectService:
    """Application service for project operations."""

    def __init__(self, db: Session):
        self.db = db

    def list_projects(self, skip: int = 0, limit: int = 100) -> list[ProjectModel]:
        return self.db.query(ProjectModel).offset(skip).limit(limit).all()

    def get_project(self, project_id: int) -> ProjectModel:
        project = self.db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if project is None:
            raise AppError(404, "project_not_found", "Project not found")
        normalized_code = normalize_project_code(project.code)
        if normalized_code != project.code:
            project.code = normalized_code
            project.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(project)
        return project

    def create_project(self, payload: ProjectCreate) -> ProjectModel:
        year = payload.year
        counter = self._get_or_create_year_counter(year)
        number = counter.last_number + 1
        code = build_project_code(number=number, year=year, project_type=payload.project_type)

        project = ProjectModel(
            name=payload.name,
            project_type=payload.project_type,
            number=number,
            year=year,
            code=code,
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
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def update_project(self, project_id: int, payload: ProjectUpdate) -> ProjectModel:
        project = self.get_project(project_id)
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
        self.db.commit()
        self.db.refresh(project)
        return project

    def delete_project(self, project_id: int) -> None:
        project = self.get_project(project_id)
        self.db.delete(project)
        self.db.commit()

    def _get_or_create_year_counter(self, year: int) -> ProjectYearCounter:
        counter = (
            self.db.query(ProjectYearCounter)
            .filter(ProjectYearCounter.year == year)
            .first()
        )
        existing_max = (
            self.db.query(func.max(ProjectModel.number))
            .filter(ProjectModel.year == year)
            .scalar()
        ) or 0

        if counter is None:
            counter = ProjectYearCounter(year=year, last_number=existing_max)
            self.db.add(counter)
            self.db.flush()
            return counter

        if counter.last_number < existing_max:
            counter.last_number = existing_max
            self.db.flush()

        return counter

    def _smallest_free_project_number(self, year: int, exclude_project_id: int | None = None) -> int:
        query = self.db.query(ProjectModel.number).filter(ProjectModel.year == year)
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
