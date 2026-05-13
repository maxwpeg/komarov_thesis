"""SQLAlchemy-backed project repository."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from backend.auth import ensure_owner_user_can_be_assigned
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

    def list(
        self,
        skip: int = 0,
        limit: int = 100,
        owner_user_id: int | None = None,
        include_deleted: bool = False,
        deleted_only: bool = False,
    ) -> list[ProjectRecord]:
        query = self.session.query(ProjectModel).options(
            selectinload(ProjectModel.owner_user),
            selectinload(ProjectModel.deleted_by_user),
        )
        if owner_user_id is not None:
            query = query.filter(ProjectModel.owner_user_id == owner_user_id)
        if deleted_only:
            query = query.filter(ProjectModel.deleted_at.is_not(None))
        elif not include_deleted:
            query = query.filter(ProjectModel.deleted_at.is_(None))
        query = query.order_by(ProjectModel.created_at.desc(), ProjectModel.id.desc())
        projects = query.offset(skip).limit(limit).all()
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
        owner = (
            ensure_owner_user_can_be_assigned(self.session, payload.owner_user_id)
            if payload.owner_user_id is not None
            else None
        )
        project = ProjectModel(
            name=payload.name,
            project_type=payload.project_type,
            number=number,
            year=year,
            code=build_project_code(number=number, year=year, project_type=payload.project_type),
            contractor=payload.contractor,
            engineer=owner.full_name if owner is not None else payload.engineer,
            cpe=payload.cpe,
            checker=payload.checker,
            facility=payload.facility,
            facility_genitive=payload.facility_genitive,
            facility_instrumental=payload.facility_instrumental,
            facility_address=payload.facility_address,
            project_description=payload.project_description,
            stage=payload.stage,
            number_of_floors=payload.number_of_floors,
            owner_user_id=owner.id if owner is not None else None,
        )
        counter.last_number = number
        self.session.add(project)
        self.session.flush()
        self.session.refresh(project)
        return ProjectRecord.from_model(project)

    def update(self, project_id: int, payload: ProjectUpdate) -> ProjectRecord:
        project = self._get_model(project_id)
        previous_year = project.year
        updates = payload.model_dump(exclude_unset=True)
        owner = None
        if "owner_user_id" in updates:
            owner = ensure_owner_user_can_be_assigned(self.session, updates["owner_user_id"])
            updates["owner_user_id"] = owner.id if owner is not None else None
            if owner is not None:
                updates["engineer"] = owner.full_name
        elif "engineer" in updates and project.owner_user is not None:
            updates["engineer"] = project.owner_user.full_name
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
        self.session.refresh(project)
        return ProjectRecord.from_model(project)

    def soft_delete(self, project_id: int, deleted_by_user_id: int | None = None) -> None:
        project = self._get_model(project_id)
        now = datetime.now(timezone.utc)
        project.deleted_at = now
        project.deleted_by_user_id = deleted_by_user_id
        project.updated_at = now
        self.session.flush()

    def permanently_delete(self, project_id: int) -> None:
        project = self._get_model(project_id, include_deleted=True)
        self.session.delete(project)
        self.session.flush()

    def _get_model(self, project_id: int, *, include_deleted: bool = False) -> ProjectModel:
        project = (
            self.session.query(ProjectModel)
            .options(selectinload(ProjectModel.owner_user), selectinload(ProjectModel.deleted_by_user))
            .filter(ProjectModel.id == project_id)
            .first()
        )
        if project is None or (project.deleted_at is not None and not include_deleted):
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
