"""Background task API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.auth import AuthenticatedUser, require_current_user, require_developer
from backend.database import get_db
from backend.errors import AppError
from backend.mappers import background_task_read
from backend.schemas import BackgroundTaskRead, BackgroundTaskSummaryRead
from backend.services.background_task_service import BackgroundTaskService


router = APIRouter(tags=["system"], dependencies=[Depends(require_current_user)])


def _ensure_task_access(task, current_user: AuthenticatedUser) -> None:
    if current_user.is_developer:
        return
    if task.requested_by_user_id == current_user.id:
        return
    raise AppError(403, "background_task_access_denied", "You do not have access to this background task")


@router.get("/api/background-tasks", response_model=list[BackgroundTaskSummaryRead])
def list_background_tasks(
    status: str | None = Query(None),
    task_type: str | None = Query(None),
    requested_by_user_id: int | None = Query(None),
    project_id: int | None = Query(None),
    floor_plan_id: int | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
) -> list[BackgroundTaskSummaryRead]:
    if not current_user.is_developer:
        requested_by_user_id = current_user.id
    service = BackgroundTaskService(db)
    return [
        BackgroundTaskSummaryRead.model_validate(background_task_read(task))
        for task in service.list_tasks(
            requested_by_user_id=requested_by_user_id,
            project_id=project_id,
            floor_plan_id=floor_plan_id,
            status=status,
            task_type=task_type,
            limit=limit,
        )
    ]


@router.get("/api/background-tasks/{task_id}", response_model=BackgroundTaskRead)
def get_background_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: AuthenticatedUser = Depends(require_current_user),
) -> BackgroundTaskRead:
    service = BackgroundTaskService(db)
    task = service.get_task(task_id)
    _ensure_task_access(task, current_user)
    return background_task_read(task)


@router.post("/api/background-tasks/{task_id}/cancel", response_model=BackgroundTaskRead)
def cancel_background_task(
    task_id: int,
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_developer),
) -> BackgroundTaskRead:
    service = BackgroundTaskService(db)
    task = service.cancel(task_id, message="Task canceled by administrator")
    return background_task_read(task)
