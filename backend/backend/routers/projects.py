"""Project routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query

from backend.audit import record_audit_event
from backend.auth import AuthenticatedUser, require_current_user, require_developer, require_project_access
from backend.database import get_db
from backend.dependencies import get_project_use_cases
from backend.mappers import project_read
from backend.modules.projects.application.use_cases import ProjectUseCases
from backend.schemas import MessageRead, ProjectCreate, ProjectRead, ProjectUpdate
from sqlalchemy.orm import Session


router = APIRouter(prefix="/api/projects", tags=["projects"])


def _parse_datetime_filter(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    return datetime.fromisoformat(normalized)


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
    owner_user_id: int | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None),
    facility: str | None = Query(None),
    project_number: int | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    current_user: AuthenticatedUser = Depends(require_current_user),
    service: ProjectUseCases = Depends(get_project_use_cases),
) -> list[ProjectRead]:
    if not current_user.is_developer:
        owner_user_id = current_user.id
    include_deleted = current_user.is_developer and str(status or "").strip().lower() in {"deleted", "trash"}
    return [
        project_read(project)
        for project in service.list_projects(
            skip=skip,
            limit=limit,
            owner_user_id=owner_user_id,
            include_deleted=include_deleted,
            status=status,
            search=search,
            facility=facility,
            project_number=project_number,
            date_from=_parse_datetime_filter(date_from),
            date_to=_parse_datetime_filter(date_to),
        )
    ]


@router.get("/trash", response_model=list[ProjectRead])
def list_deleted_projects(
    skip: int = 0,
    limit: int = 100,
    owner_user_id: int | None = Query(None),
    search: str | None = Query(None),
    facility: str | None = Query(None),
    project_number: int | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    _: AuthenticatedUser = Depends(require_developer),
    service: ProjectUseCases = Depends(get_project_use_cases),
) -> list[ProjectRead]:
    return [
        project_read(project)
        for project in service.list_projects(
            skip=skip,
            limit=limit,
            owner_user_id=owner_user_id,
            deleted_only=True,
            search=search,
            facility=facility,
            project_number=project_number,
            date_from=_parse_datetime_filter(date_from),
            date_to=_parse_datetime_filter(date_to),
        )
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
    current_user: AuthenticatedUser = Depends(require_project_access),
    service: ProjectUseCases = Depends(get_project_use_cases),
) -> MessageRead:
    service.soft_delete_project(project_id, deleted_by_user_id=current_user.id)
    return MessageRead(message="Project moved to trash")


@router.delete("/{project_id}/permanent", response_model=MessageRead)
def permanently_delete_project(
    project_id: int,
    current_user: AuthenticatedUser = Depends(require_developer),
    db: Session = Depends(get_db),
    service: ProjectUseCases = Depends(get_project_use_cases),
) -> MessageRead:
    service.permanently_delete_project(project_id)
    record_audit_event(
        db,
        "project_permanently_deleted",
        category="projects",
        use_case="PermanentlyDeleteProject",
        user_id=current_user.id,
        project_id=project_id,
    )
    db.commit()
    return MessageRead(message="Project permanently deleted")
