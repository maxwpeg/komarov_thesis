"""Project routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.auth import AuthenticatedUser, require_current_user, require_project_access
from backend.dependencies import get_project_use_cases
from backend.mappers import project_read
from backend.modules.projects.application.use_cases import ProjectUseCases
from backend.schemas import MessageRead, ProjectCreate, ProjectRead, ProjectUpdate


router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectRead)
def create_project(
    payload: ProjectCreate,
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: ProjectUseCases = Depends(get_project_use_cases),
) -> ProjectRead:
    if current_user.is_engineer:
        payload = ProjectCreate.model_validate(
            {
                **payload.model_dump(),
                "owner_user_id": current_user.id,
            }
        )
    return project_read(service.create_project(payload))


@router.get("", response_model=list[ProjectRead])
def list_projects(
    skip: int = 0,
    limit: int = 100,
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: ProjectUseCases = Depends(get_project_use_cases),
) -> list[ProjectRead]:
    owner_user_id = None if current_user.is_developer else current_user.id
    return [
        project_read(project)
        for project in service.list_projects(skip=skip, limit=limit, owner_user_id=owner_user_id)
    ]


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: int,
    _: AuthenticatedUser = Depends(require_project_access),
    service: ProjectUseCases = Depends(get_project_use_cases),
) -> ProjectRead:
    return project_read(service.get_project(project_id))


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    current_user: AuthenticatedUser = Depends(require_project_access),
    service: ProjectUseCases = Depends(get_project_use_cases),
) -> ProjectRead:
    if current_user.is_engineer:
        payload = ProjectUpdate.model_validate(payload.model_dump(exclude_unset=True, exclude={"owner_user_id"}))
    return project_read(service.update_project(project_id, payload))


@router.delete("/{project_id}", response_model=MessageRead)
def delete_project(
    project_id: int,
    _: AuthenticatedUser = Depends(require_project_access),
    service: ProjectUseCases = Depends(get_project_use_cases),
) -> MessageRead:
    service.delete_project(project_id)
    return MessageRead(message="Project deleted successfully")
