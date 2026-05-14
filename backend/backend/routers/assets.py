"""Authenticated asset proxy endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.auth import AuthenticatedUser, ensure_project_access, require_current_user, require_developer
from backend.database import get_db
from backend.errors import AppError
from backend.assets import normalize_asset_path
from backend.models import EquipmentItem, FloorPlan, FloorplanRecognition, Project, ProjectPdfVersion, RecognitionTrainingRun
from backend.modules.shared.infrastructure.storage import StorageService
from backend.services.storage_integrity_service import StorageIntegrityService


router = APIRouter(tags=["system"], dependencies=[Depends(require_current_user)])


def _same_asset_path(left: str | None, right: str) -> bool:
    try:
        return normalize_asset_path(left) == right
    except ValueError:
        return False


def _authorize_asset_access(db: Session, current_user: AuthenticatedUser, asset_path: str) -> None:
    if current_user.is_developer:
        return

    equipment = (
        db.query(EquipmentItem.id)
        .filter(
            or_(
                EquipmentItem.image_path == asset_path,
                EquipmentItem.connection_diagram_path == asset_path,
                EquipmentItem.label_pdf_path == asset_path,
                EquipmentItem.manual_pdf_path == asset_path,
            )
        )
        .first()
    )
    if equipment is not None:
        return

    project = db.query(Project).filter(Project.latest_pdf_path == asset_path).first()
    if project is not None:
        ensure_project_access(db, current_user, int(project.id))
        return

    pdf_version = db.query(ProjectPdfVersion).filter(ProjectPdfVersion.path == asset_path).first()
    if pdf_version is not None:
        ensure_project_access(db, current_user, int(pdf_version.project_id))
        return

    floor_plan = (
        db.query(FloorPlan)
        .filter(
            or_(
                FloorPlan.original_image_path == asset_path,
                FloorPlan.processed_image_path == asset_path,
            )
        )
        .first()
    )
    if floor_plan is not None:
        ensure_project_access(db, current_user, int(floor_plan.project_id))
        return

    recognition = db.query(FloorplanRecognition).filter(FloorplanRecognition.debug_artifacts_dir.is_not(None)).all()
    for item in recognition:
        try:
            debug_dir = normalize_asset_path(item.debug_artifacts_dir)
        except ValueError:
            continue
        if debug_dir and (_same_asset_path(debug_dir, asset_path) or asset_path.startswith(f"{debug_dir}/")):
            if item.floor_plan is None:
                raise AppError(404, "asset_not_found", "Asset not found")
            ensure_project_access(db, current_user, int(item.floor_plan.project_id))
            return

    training_run = (
        db.query(RecognitionTrainingRun.id)
        .filter(
            or_(
                RecognitionTrainingRun.artifact_dir == asset_path,
                RecognitionTrainingRun.log_path == asset_path,
            )
        )
        .first()
    )
    if training_run is not None or asset_path.startswith("recognition_training/"):
        raise AppError(403, "asset_access_denied", "Only administrators can access recognition training artifacts")

    raise AppError(404, "asset_not_found", "Asset not found")


@router.get("/api/storage/integrity")
def get_storage_integrity_report(
    _: AuthenticatedUser = Depends(require_developer),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    return StorageIntegrityService(db).build_report()


@router.get("/api/assets/{asset_path:path}")
def get_asset(
    asset_path: str,
    current_user: AuthenticatedUser = Depends(require_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    storage = StorageService()
    try:
        normalized = normalize_asset_path(asset_path)
        resolved = storage.absolute_path(normalized)
    except ValueError as exc:
        raise AppError(404, "asset_not_found", "Asset not found") from exc
    if resolved is None or not resolved.exists() or not resolved.is_file():
        raise AppError(404, "asset_not_found", "Asset not found")
    _authorize_asset_access(db, current_user, normalized)
    return FileResponse(resolved)
