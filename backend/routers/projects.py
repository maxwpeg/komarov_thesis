"""Project routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.dependencies import get_project_use_cases
from backend.mappers import project_read
from backend.modules.projects.application.use_cases import ProjectUseCases
from backend.schemas import MessageRead, ProjectCreate, ProjectRead, ProjectUpdate


router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.post("", response_model=ProjectRead)
def create_project(
    payload: ProjectCreate,
    service: ProjectUseCases = Depends(get_project_use_cases),
) -> ProjectRead:
    return project_read(service.create_project(payload))


@router.get("", response_model=list[ProjectRead])
def list_projects(
    skip: int = 0,
    limit: int = 100,
    service: ProjectUseCases = Depends(get_project_use_cases),
) -> list[ProjectRead]:
    return [project_read(project) for project in service.list_projects(skip=skip, limit=limit)]


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(
    project_id: int,
    service: ProjectUseCases = Depends(get_project_use_cases),
) -> ProjectRead:
    return project_read(service.get_project(project_id))


@router.patch("/{project_id}", response_model=ProjectRead)
def update_project(
    project_id: int,
    payload: ProjectUpdate,
    service: ProjectUseCases = Depends(get_project_use_cases),
) -> ProjectRead:
    return project_read(service.update_project(project_id, payload))


@router.delete("/{project_id}", response_model=MessageRead)
def delete_project(
    project_id: int,
    service: ProjectUseCases = Depends(get_project_use_cases),
) -> MessageRead:
    service.delete_project(project_id)
    return MessageRead(message="Project deleted successfully")
