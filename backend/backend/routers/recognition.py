"""Recognition routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query, Request, status

from backend.background_jobs import TASK_RECOGNITION_PROCESS, dedupe_key_for_task
from backend.audit import record_audit_event
from backend.auth import AuthenticatedUser, require_current_user, require_developer, require_floor_plan_access
from backend.database import get_db
from backend.dependencies import get_pipeline_use_cases
from backend.dependencies import get_recognition_use_cases
from backend.mappers import background_task_read
from backend.modules.pipeline.application.use_cases import PipelineUseCases
from backend.modules.recognition.application.use_cases import RecognitionUseCases
from backend.schemas import BackgroundTaskRead, FeedbackCreate, MessageRead, RecognitionFeedbackRead, RecognitionFeedbackStatsRead, RecognitionRead
from backend.services.background_task_service import BackgroundTaskService
from sqlalchemy.orm import Session

from backend.config import settings
from backend.security import enforce_rate_limit


router = APIRouter(tags=["recognition"])


@router.post(
    "/api/floor-plans/{floor_plan_id}/process",
    response_model=BackgroundTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def process_floor_plan(
    floor_plan_id: int,
    request: Request,
    debug: bool = Query(False),
    current_user: AuthenticatedUser = Depends(require_floor_plan_access),
    db: Session = Depends(get_db),
) -> BackgroundTaskRead:
    enforce_rate_limit(
        request,
        "recognition_process",
        discriminator=str(current_user.id),
        limit=settings.heavy_task_rate_limit_count,
        window_seconds=settings.heavy_task_rate_limit_window_seconds,
    )
    task = BackgroundTaskService(db).enqueue(
        task_type=TASK_RECOGNITION_PROCESS,
        requested_by_user_id=current_user.id,
        floor_plan_id=floor_plan_id,
        payload={"floor_plan_id": floor_plan_id, "debug": bool(debug)},
        dedupe_key=dedupe_key_for_task(TASK_RECOGNITION_PROCESS, floor_plan_id=floor_plan_id),
        resource_path=f"/floor-plans/{floor_plan_id}",
    )
    record_audit_event(
        db,
        "recognition_process_requested",
        category="recognition",
        use_case="ProcessFloorPlan",
        user_id=current_user.id,
        floor_plan_id=floor_plan_id,
        payload={"debug": bool(debug), "background_task_id": task.id},
    )
    db.commit()
    return background_task_read(task)


@router.get("/api/floor-plans/{floor_plan_id}/recognition", response_model=RecognitionRead)
def get_floor_plan_recognition(
    floor_plan_id: int,
    debug: bool = Query(False),
    _: AuthenticatedUser = Depends(require_floor_plan_access),
    service: RecognitionUseCases = Depends(get_recognition_use_cases),
) -> RecognitionRead:
    return service.get_recognition(floor_plan_id, debug=debug)


@router.post("/api/floor-plans/{floor_plan_id}/recognition-feedback", response_model=RecognitionFeedbackRead)
def submit_floor_plan_recognition_feedback(
    floor_plan_id: int,
    _: AuthenticatedUser = Depends(require_floor_plan_access),
    service: RecognitionUseCases = Depends(get_recognition_use_cases),
) -> RecognitionFeedbackRead:
    return service.submit_feedback_sample(floor_plan_id)


@router.get("/api/recognition-feedback/stats", response_model=RecognitionFeedbackStatsRead)
def get_recognition_feedback_stats(
    _: AuthenticatedUser = Depends(require_developer),
    service: PipelineUseCases = Depends(get_pipeline_use_cases),
) -> RecognitionFeedbackStatsRead:
    return RecognitionFeedbackStatsRead.model_validate(service.get_feedback_stats())


@router.post("/feedback", response_model=MessageRead)
def save_feedback(
    payload: FeedbackCreate,
    _: AuthenticatedUser = Depends(require_current_user),
) -> MessageRead:
    with settings.feedback_file.open("w", encoding="utf-8") as file:
        json.dump(payload.model_dump(), file, ensure_ascii=False, indent=2)
    return MessageRead(message="saved")
