"""Step-by-step pipeline routes."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy.orm import Session

from backend.auth import AuthenticatedUser, require_floor_plan_access
from backend.background_jobs import (
    TASK_PIPELINE_DETECT_OPENINGS,
    TASK_PIPELINE_DETECT_ROOMS,
    TASK_PIPELINE_DETECT_WALLS,
    TASK_PIPELINE_DETECT_ZKSPC,
    dedupe_key_for_task,
)
from backend.database import get_db
from backend.dependencies import get_pipeline_use_cases
from backend.mappers import background_task_read
from backend.mappers import floor_plan_read
from backend.modules.pipeline.application.errors import WallValidationError
from backend.modules.pipeline.application.use_cases import PipelineUseCases
from backend.schemas import (
    BackgroundTaskRead,
    PipelineCommitResult,
    PipelineOpeningsCommitRequest,
    PipelineStepFeedbackRead,
    PipelineStepFeedbackRequest,
    PipelineRoomsCommitRequest,
    PipelineStateRead,
    PipelineWallsCommitRequest,
    PipelineZkspcCommitRequest,
)
from backend.services.background_task_service import BackgroundTaskService


router = APIRouter(tags=["pipeline"], dependencies=[Depends(require_floor_plan_access)])


def _submit_step_feedback(
    floor_plan_id: int,
    step: Literal["walls", "openings"],
    payload: PipelineStepFeedbackRequest,
    service: PipelineUseCases,
) -> PipelineStepFeedbackRead:
    return PipelineStepFeedbackRead.model_validate(
        service.submit_step_feedback(
            floor_plan_id,
            step,
            step_revision=payload.step_revision,
            issue_tags=payload.issue_tags,
            notes=payload.notes,
        )
    )


@router.get("/api/floor-plans/{floor_plan_id}/pipeline-state", response_model=PipelineStateRead)
def get_pipeline_state(
    floor_plan_id: int,
    service: PipelineUseCases = Depends(get_pipeline_use_cases),
) -> PipelineStateRead:
    return service.get_pipeline_state(floor_plan_id)


@router.post(
    "/api/floor-plans/{floor_plan_id}/pipeline/walls/detect",
    response_model=BackgroundTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def detect_walls(
    floor_plan_id: int,
    current_user: AuthenticatedUser = Depends(require_floor_plan_access),
    db: Session = Depends(get_db),
) -> BackgroundTaskRead:
    task = BackgroundTaskService(db).enqueue(
        task_type=TASK_PIPELINE_DETECT_WALLS,
        requested_by_user_id=current_user.id,
        floor_plan_id=floor_plan_id,
        payload={"floor_plan_id": floor_plan_id},
        dedupe_key=dedupe_key_for_task(TASK_PIPELINE_DETECT_WALLS, floor_plan_id=floor_plan_id),
        resource_path=f"/floor-plans/{floor_plan_id}",
    )
    return background_task_read(task)


@router.post("/api/floor-plans/{floor_plan_id}/pipeline/walls/commit", response_model=PipelineCommitResult)
def commit_walls(
    floor_plan_id: int,
    payload: PipelineWallsCommitRequest,
    service: PipelineUseCases = Depends(get_pipeline_use_cases),
) -> PipelineCommitResult:
    try:
        floor_plan, state = service.commit_walls(floor_plan_id, payload)
    except WallValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "walls_missing_dimensions",
                "missing_wall_ids": exc.missing_wall_ids,
            },
        ) from exc
    return PipelineCommitResult(
        message="Walls validated and committed",
        floor_plan=floor_plan_read(floor_plan, include_elements=True),
        pipeline_state=state,
    )


@router.post(
    "/api/floor-plans/{floor_plan_id}/pipeline/openings/detect",
    response_model=BackgroundTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def detect_openings(
    floor_plan_id: int,
    current_user: AuthenticatedUser = Depends(require_floor_plan_access),
    db: Session = Depends(get_db),
) -> BackgroundTaskRead:
    task = BackgroundTaskService(db).enqueue(
        task_type=TASK_PIPELINE_DETECT_OPENINGS,
        requested_by_user_id=current_user.id,
        floor_plan_id=floor_plan_id,
        payload={"floor_plan_id": floor_plan_id},
        dedupe_key=dedupe_key_for_task(TASK_PIPELINE_DETECT_OPENINGS, floor_plan_id=floor_plan_id),
        resource_path=f"/floor-plans/{floor_plan_id}",
    )
    return background_task_read(task)


@router.post("/api/floor-plans/{floor_plan_id}/pipeline/openings/commit", response_model=PipelineCommitResult)
def commit_openings(
    floor_plan_id: int,
    payload: PipelineOpeningsCommitRequest,
    service: PipelineUseCases = Depends(get_pipeline_use_cases),
) -> PipelineCommitResult:
    floor_plan, state = service.commit_openings(floor_plan_id, payload)
    return PipelineCommitResult(
        message="Openings validated and committed",
        floor_plan=floor_plan_read(floor_plan, include_elements=True),
        pipeline_state=state,
    )


@router.post("/api/floor-plans/{floor_plan_id}/pipeline/walls/feedback", response_model=PipelineStepFeedbackRead)
def submit_walls_feedback(
    floor_plan_id: int,
    payload: PipelineStepFeedbackRequest,
    service: PipelineUseCases = Depends(get_pipeline_use_cases),
) -> PipelineStepFeedbackRead:
    return _submit_step_feedback(floor_plan_id, "walls", payload, service)


@router.post("/api/floor-plans/{floor_plan_id}/pipeline/openings/feedback", response_model=PipelineStepFeedbackRead)
def submit_openings_feedback(
    floor_plan_id: int,
    payload: PipelineStepFeedbackRequest,
    service: PipelineUseCases = Depends(get_pipeline_use_cases),
) -> PipelineStepFeedbackRead:
    return _submit_step_feedback(floor_plan_id, "openings", payload, service)


@router.post("/api/floor-plans/{floor_plan_id}/pipeline/{step}/feedback", response_model=PipelineStepFeedbackRead)
def submit_step_feedback(
    floor_plan_id: int,
    step: Literal["walls", "openings"],
    payload: PipelineStepFeedbackRequest,
    service: PipelineUseCases = Depends(get_pipeline_use_cases),
) -> PipelineStepFeedbackRead:
    return _submit_step_feedback(floor_plan_id, step, payload, service)


@router.post(
    "/api/floor-plans/{floor_plan_id}/pipeline/rooms/detect",
    response_model=BackgroundTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def detect_rooms(
    floor_plan_id: int,
    current_user: AuthenticatedUser = Depends(require_floor_plan_access),
    db: Session = Depends(get_db),
) -> BackgroundTaskRead:
    task = BackgroundTaskService(db).enqueue(
        task_type=TASK_PIPELINE_DETECT_ROOMS,
        requested_by_user_id=current_user.id,
        floor_plan_id=floor_plan_id,
        payload={"floor_plan_id": floor_plan_id},
        dedupe_key=dedupe_key_for_task(TASK_PIPELINE_DETECT_ROOMS, floor_plan_id=floor_plan_id),
        resource_path=f"/floor-plans/{floor_plan_id}",
    )
    return background_task_read(task)


@router.post("/api/floor-plans/{floor_plan_id}/pipeline/rooms/commit", response_model=PipelineCommitResult)
def commit_rooms(
    floor_plan_id: int,
    payload: PipelineRoomsCommitRequest,
    service: PipelineUseCases = Depends(get_pipeline_use_cases),
) -> PipelineCommitResult:
    floor_plan, state = service.commit_rooms(floor_plan_id, payload)
    return PipelineCommitResult(
        message="Rooms validated and committed",
        floor_plan=floor_plan_read(floor_plan, include_elements=True),
        pipeline_state=state,
    )


@router.post(
    "/api/floor-plans/{floor_plan_id}/pipeline/zkspc/detect",
    response_model=BackgroundTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def detect_zkspc(
    floor_plan_id: int,
    current_user: AuthenticatedUser = Depends(require_floor_plan_access),
    db: Session = Depends(get_db),
) -> BackgroundTaskRead:
    task = BackgroundTaskService(db).enqueue(
        task_type=TASK_PIPELINE_DETECT_ZKSPC,
        requested_by_user_id=current_user.id,
        floor_plan_id=floor_plan_id,
        payload={"floor_plan_id": floor_plan_id},
        dedupe_key=dedupe_key_for_task(TASK_PIPELINE_DETECT_ZKSPC, floor_plan_id=floor_plan_id),
        resource_path=f"/floor-plans/{floor_plan_id}",
    )
    return background_task_read(task)


@router.post("/api/floor-plans/{floor_plan_id}/pipeline/zkspc/commit", response_model=PipelineCommitResult)
def commit_zkspc(
    floor_plan_id: int,
    payload: PipelineZkspcCommitRequest,
    service: PipelineUseCases = Depends(get_pipeline_use_cases),
) -> PipelineCommitResult:
    floor_plan, state = service.commit_zkspc(floor_plan_id, payload)
    return PipelineCommitResult(
        message="ZKSPC validated and committed",
        floor_plan=floor_plan_read(floor_plan, include_elements=True),
        pipeline_state=state,
    )
