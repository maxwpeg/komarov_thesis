"""Recognition training management routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from backend.auth import require_developer
from backend.dependencies import get_recognition_training_management_service
from backend.schemas import (
    RecognitionActiveModelRead,
    RecognitionTrainingBulkCurateRead,
    RecognitionTrainingBulkCurateRequest,
    RecognitionTrainingExampleDetailRead,
    RecognitionTrainingExampleSummaryRead,
    RecognitionTrainingExampleUpdate,
    RecognitionTrainingOverviewRead,
    RecognitionTrainingRunCreateRequest,
    RecognitionTrainingRunLogRead,
    RecognitionTrainingRunRead,
)
router = APIRouter(tags=["recognition-training"], dependencies=[Depends(require_developer)])


@router.get("/api/recognition-training/overview", response_model=RecognitionTrainingOverviewRead)
def get_recognition_training_overview(
    service: Any = Depends(get_recognition_training_management_service),
) -> RecognitionTrainingOverviewRead:
    return RecognitionTrainingOverviewRead.model_validate(service.get_overview())


@router.get("/api/recognition-training/examples", response_model=list[RecognitionTrainingExampleSummaryRead])
def list_recognition_training_examples(
    step: str | None = Query(None),
    curation_status: str | None = Query(None),
    project_id: int | None = Query(None),
    floor_plan_id: int | None = Query(None),
    changed_only: bool = Query(False),
    search: str | None = Query(None),
    sort_by: str = Query("submitted_at"),
    sort_dir: str = Query("desc"),
    service: Any = Depends(get_recognition_training_management_service),
) -> list[RecognitionTrainingExampleSummaryRead]:
    return [
        RecognitionTrainingExampleSummaryRead.model_validate(item)
        for item in service.list_examples(
            step=step,
            curation_status=curation_status,
            project_id=project_id,
            floor_plan_id=floor_plan_id,
            changed_only=changed_only,
            search=search,
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
    ]


@router.post("/api/recognition-training/examples/bulk-curate", response_model=RecognitionTrainingBulkCurateRead)
def bulk_curate_recognition_training_examples(
    payload: RecognitionTrainingBulkCurateRequest,
    service: Any = Depends(get_recognition_training_management_service),
) -> RecognitionTrainingBulkCurateRead:
    return RecognitionTrainingBulkCurateRead.model_validate(
        service.bulk_curate(
            payload.example_ids,
            curation_status=payload.curation_status,
        )
    )


@router.get("/api/recognition-training/examples/{example_id}", response_model=RecognitionTrainingExampleDetailRead)
def get_recognition_training_example(
    example_id: int,
    service: Any = Depends(get_recognition_training_management_service),
) -> RecognitionTrainingExampleDetailRead:
    return RecognitionTrainingExampleDetailRead.model_validate(service.get_example_detail(example_id))


@router.patch("/api/recognition-training/examples/{example_id}", response_model=RecognitionTrainingExampleDetailRead)
def update_recognition_training_example(
    example_id: int,
    payload: RecognitionTrainingExampleUpdate,
    service: Any = Depends(get_recognition_training_management_service),
) -> RecognitionTrainingExampleDetailRead:
    return RecognitionTrainingExampleDetailRead.model_validate(
        service.update_example(
            example_id,
            curation_status=payload.curation_status,
            issue_tags=payload.issue_tags,
            notes=payload.notes,
        )
    )


@router.get("/api/recognition-training/runs", response_model=list[RecognitionTrainingRunRead])
def list_recognition_training_runs(
    service: Any = Depends(get_recognition_training_management_service),
) -> list[RecognitionTrainingRunRead]:
    return [RecognitionTrainingRunRead.model_validate(item) for item in service.list_runs()]


@router.get("/api/recognition-training/runs/{run_id}", response_model=RecognitionTrainingRunRead)
def get_recognition_training_run(
    run_id: str,
    service: Any = Depends(get_recognition_training_management_service),
) -> RecognitionTrainingRunRead:
    return RecognitionTrainingRunRead.model_validate(service.get_run(run_id))


@router.get("/api/recognition-training/active-models", response_model=list[RecognitionActiveModelRead])
def list_recognition_training_active_models(
    service: Any = Depends(get_recognition_training_management_service),
) -> list[RecognitionActiveModelRead]:
    return [RecognitionActiveModelRead.model_validate(item) for item in service.list_active_models()]


@router.get("/api/recognition-training/runs/{run_id}/log", response_model=RecognitionTrainingRunLogRead)
def get_recognition_training_run_log(
    run_id: str,
    tail: int = Query(200, ge=1, le=5000),
    service: Any = Depends(get_recognition_training_management_service),
) -> RecognitionTrainingRunLogRead:
    return RecognitionTrainingRunLogRead.model_validate(service.get_run_log(run_id, tail=tail))


@router.post("/api/recognition-training/runs", response_model=RecognitionTrainingRunRead)
def create_recognition_training_run(
    payload: RecognitionTrainingRunCreateRequest,
    service: Any = Depends(get_recognition_training_management_service),
) -> RecognitionTrainingRunRead:
    return RecognitionTrainingRunRead.model_validate(
        service.create_run(
            step=payload.step,
            epochs=payload.epochs,
            imgsz=payload.imgsz,
            batch=payload.batch,
            patience=payload.patience,
            force=payload.force,
        )
    )


@router.post("/api/recognition-training/runs/{run_id}/activate", response_model=RecognitionActiveModelRead)
def activate_recognition_training_run(
    run_id: str,
    service: Any = Depends(get_recognition_training_management_service),
) -> RecognitionActiveModelRead:
    return RecognitionActiveModelRead.model_validate(service.activate_run(run_id))
