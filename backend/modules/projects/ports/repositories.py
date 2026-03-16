"""Repository contracts for the projects module."""

from __future__ import annotations

from typing import Protocol

from backend.modules.projects.domain.entities import ProjectRecord
from backend.schemas import ProjectCreate, ProjectUpdate


class ProjectRepository(Protocol):
    """Persistence contract for projects."""

    def list(self, skip: int = 0, limit: int = 100) -> list[ProjectRecord]:
        """Return paginated project snapshots."""

    def get(self, project_id: int) -> ProjectRecord:
        """Return a single project snapshot or raise."""

    def create(self, payload: ProjectCreate) -> ProjectRecord:
        """Create a new project snapshot."""

    def update(self, project_id: int, payload: ProjectUpdate) -> ProjectRecord:
        """Update and return a project snapshot."""

    def delete(self, project_id: int) -> None:
        """Delete a project."""
