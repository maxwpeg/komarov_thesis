"""Repository contracts for the projects module."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from backend.modules.projects.domain.entities import ProjectRecord
from backend.schemas import ProjectCreate, ProjectUpdate


class ProjectRepository(Protocol):
    """Persistence contract for projects."""

    def list(
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
        """Return paginated project snapshots."""

    def get(self, project_id: int) -> ProjectRecord:
        """Return a single project snapshot or raise."""

    def create(self, payload: ProjectCreate) -> ProjectRecord:
        """Create a new project snapshot."""

    def update(self, project_id: int, payload: ProjectUpdate) -> ProjectRecord:
        """Update and return a project snapshot."""

    def soft_delete(self, project_id: int, deleted_by_user_id: int | None = None) -> None:
        """Move a project to trash."""

    def permanently_delete(self, project_id: int) -> None:
        """Delete a project and its children permanently."""
