"""Recognition routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Query

from backend.auth import AuthenticatedUser, require_current_user, require_developer, require_floor_plan_access
from backend.dependencies import get_pipeline_use_cases
from backend.config import settings
from backend.dependencies import get_recognition_use_cases
from backend.modules.pipeline.application.use_cases import PipelineUseCases
from backend.modules.recognition.application.use_cases import RecognitionUseCases
from backend.schemas import FeedbackCreate, MessageRead, RecognitionFeedbackRead, RecognitionFeedbackStatsRead, RecognitionProcessRead, RecognitionRead


router = APIRouter(tags=["recognition"])


@router.post("/api/floor-plans/{floor_plan_id}/process", response_model=RecognitionProcessRead)
def process_floor_plan(
    floor_plan_id: int,
    debug: bool = Query(False),
    _: AuthenticatedUser = Depends(require_floor_plan_access),
    service: RecognitionUseCases = Depends(get_recognition_use_cases),
) -> RecognitionProcessRead:
    recognition_id, walls, doors, windows, rooms, dimensions = service.process_floor_plan(
        floor_plan_id,
        debug=debug,
    )
    return RecognitionProcessRead(
        message="Floor plan recognized successfully",
        walls_detected=walls,
        doors_detected=doors,
        windows_detected=windows,
        rooms_detected=rooms,
        dimensions_detected=dimensions,
        recognition_id=recognition_id,
    )


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
