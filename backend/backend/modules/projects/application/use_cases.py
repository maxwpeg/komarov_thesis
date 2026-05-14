"""Project application use cases."""

from __future__ import annotations

from datetime import datetime

from backend.modules.projects.domain.entities import ProjectRecord
from backend.modules.projects.ports.repositories import ProjectRepository
from backend.modules.shared.application.unit_of_work import UnitOfWork
from backend.schemas import ProjectCreate, ProjectUpdate


class ProjectUseCases:
    """Application facade for the projects bounded context."""

    def __init__(self, repository: ProjectRepository, uow: UnitOfWork):
        self.repository = repository
        self.uow = uow

    def list_projects(
        self,
        skip: int = 0,
        limit: int = 100,
        owner_user_id: int | None = None,
        include_deleted: bool = False,
        deleted_only: bool = False,
        status: str | None = None,
        search: str | None = None,
        facility: str | None = None,
        project_number: int | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[ProjectRecord]:
        return self.repository.list(
            skip=skip,
            limit=limit,
            owner_user_id=owner_user_id,
            include_deleted=include_deleted,
            deleted_only=deleted_only,
            status=status,
            search=search,
            facility=facility,
            project_number=project_number,
            date_from=date_from,
            date_to=date_to,
        )

    def get_project(self, project_id: int) -> ProjectRecord:
        return self.repository.get(project_id)

    def create_project(self, payload: ProjectCreate) -> ProjectRecord:
        return self._write(lambda: self.repository.create(payload))

    def update_project(self, project_id: int, payload: ProjectUpdate) -> ProjectRecord:
        return self._write(lambda: self.repository.update(project_id, payload))

    def soft_delete_project(self, project_id: int, deleted_by_user_id: int | None = None) -> None:
        self._write(lambda: self.repository.soft_delete(project_id, deleted_by_user_id=deleted_by_user_id))

    def permanently_delete_project(self, project_id: int) -> None:
        self._write(lambda: self.repository.permanently_delete(project_id))

    def delete_project(self, project_id: int) -> None:
        self.soft_delete_project(project_id)

    def _write(self, operation):
        try:
            result = operation()
            self.uow.commit()
            return result
        except Exception:
            self.uow.rollback()
            raise
