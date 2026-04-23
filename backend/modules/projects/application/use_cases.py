"""Project application use cases."""

from __future__ import annotations

from backend.modules.projects.domain.entities import ProjectRecord
from backend.modules.projects.ports.repositories import ProjectRepository
from backend.modules.shared.application.unit_of_work import UnitOfWork
from backend.schemas import ProjectCreate, ProjectUpdate


class ProjectUseCases:
    """Application facade for the projects bounded context."""

    def __init__(self, repository: ProjectRepository, uow: UnitOfWork):
        self.repository = repository
        self.uow = uow

    def list_projects(self, skip: int = 0, limit: int = 100, owner_user_id: int | None = None) -> list[ProjectRecord]:
        return self.repository.list(skip=skip, limit=limit, owner_user_id=owner_user_id)

    def get_project(self, project_id: int) -> ProjectRecord:
        return self.repository.get(project_id)

    def create_project(self, payload: ProjectCreate) -> ProjectRecord:
        return self._write(lambda: self.repository.create(payload))

    def update_project(self, project_id: int, payload: ProjectUpdate) -> ProjectRecord:
        return self._write(lambda: self.repository.update(project_id, payload))

    def delete_project(self, project_id: int) -> None:
        self._write(lambda: self.repository.delete(project_id))

    def _write(self, operation):
        try:
            result = operation()
            self.uow.commit()
            return result
        except Exception:
            self.uow.rollback()
            raise
