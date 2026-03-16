"""Step-by-step pipeline routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.dependencies import get_pipeline_use_cases
from backend.mappers import floor_plan_read
from backend.modules.pipeline.application.errors import WallValidationError
from backend.modules.pipeline.application.use_cases import PipelineUseCases
from backend.schemas import (
    PipelineCommitResult,
    PipelineDetectResult,
    PipelineOpeningsCommitRequest,
    PipelineRoomsCommitRequest,
    PipelineStateRead,
    PipelineWallsCommitRequest,
    PipelineZkspcCommitRequest,
)


router = APIRouter(tags=["pipeline"])


@router.get("/api/floor-plans/{floor_plan_id}/pipeline-state", response_model=PipelineStateRead)
def get_pipeline_state(
    floor_plan_id: int,
    service: PipelineUseCases = Depends(get_pipeline_use_cases),
) -> PipelineStateRead:
    return service.get_pipeline_state(floor_plan_id)


@router.post("/api/floor-plans/{floor_plan_id}/pipeline/walls/detect", response_model=PipelineDetectResult)
def detect_walls(
    floor_plan_id: int,
    service: PipelineUseCases = Depends(get_pipeline_use_cases),
) -> PipelineDetectResult:
    floor_plan, state = service.detect_walls(floor_plan_id)
    return PipelineDetectResult(
        message="Walls detected successfully",
        floor_plan=floor_plan_read(floor_plan, include_elements=True),
        pipeline_state=state,
    )


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


@router.post("/api/floor-plans/{floor_plan_id}/pipeline/openings/detect", response_model=PipelineDetectResult)
def detect_openings(
    floor_plan_id: int,
    service: PipelineUseCases = Depends(get_pipeline_use_cases),
) -> PipelineDetectResult:
    floor_plan, state = service.detect_openings(floor_plan_id)
    return PipelineDetectResult(
        message="Openings detected successfully",
        floor_plan=floor_plan_read(floor_plan, include_elements=True),
        pipeline_state=state,
    )


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


@router.post("/api/floor-plans/{floor_plan_id}/pipeline/rooms/detect", response_model=PipelineDetectResult)
def detect_rooms(
    floor_plan_id: int,
    service: PipelineUseCases = Depends(get_pipeline_use_cases),
) -> PipelineDetectResult:
    floor_plan, state = service.detect_rooms(floor_plan_id)
    return PipelineDetectResult(
        message="Rooms detected successfully",
        floor_plan=floor_plan_read(floor_plan, include_elements=True),
        pipeline_state=state,
    )


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


@router.post("/api/floor-plans/{floor_plan_id}/pipeline/zkspc/detect", response_model=PipelineDetectResult)
def detect_zkspc(
    floor_plan_id: int,
    service: PipelineUseCases = Depends(get_pipeline_use_cases),
) -> PipelineDetectResult:
    floor_plan, state = service.detect_zkspc(floor_plan_id)
    return PipelineDetectResult(
        message="ZKSPC detected successfully",
        floor_plan=floor_plan_read(floor_plan, include_elements=True),
        pipeline_state=state,
    )


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
