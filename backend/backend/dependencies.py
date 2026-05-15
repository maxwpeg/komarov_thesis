"""FastAPI dependency helpers."""

from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from backend.composition import (
    build_documents_use_cases,
    build_equipment_use_cases,
    build_elements_geometry_use_cases,
    build_floor_plan_use_cases,
    build_pipeline_use_cases,
    build_project_use_cases,
    build_recognition_use_cases,
    build_signal_design_use_cases,
)
from backend.database import get_db
from backend.modules.documents.application.use_cases import DocumentsUseCases
from backend.modules.equipment.application.use_cases import EquipmentUseCases
from backend.modules.elements_geometry.application.use_cases import ElementsGeometryUseCases
from backend.modules.floor_plans.application.use_cases import FloorPlanUseCases
from backend.modules.pipeline.application.use_cases import PipelineUseCases
from backend.modules.projects.application.use_cases import ProjectUseCases
from backend.modules.recognition.application.use_cases import RecognitionUseCases
from backend.modules.shared.infrastructure.storage import StorageService
from backend.modules.signal_design.application.use_cases import SignalDesignUseCases
from backend.services.recognition_training_management_service import RecognitionTrainingManagementService


def get_storage_service() -> StorageService:
    return StorageService()


def get_project_use_cases(
    db: Session = Depends(get_db),
) -> ProjectUseCases:
    return build_project_use_cases(db)


def get_equipment_use_cases(
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> EquipmentUseCases:
    return build_equipment_use_cases(db, storage)


def get_floor_plan_use_cases(
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> FloorPlanUseCases:
    return build_floor_plan_use_cases(db, storage)


def get_elements_geometry_use_cases(db: Session = Depends(get_db)) -> ElementsGeometryUseCases:
    return build_elements_geometry_use_cases(db)


def get_pipeline_use_cases(
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> PipelineUseCases:
    return build_pipeline_use_cases(db, storage)


def get_recognition_use_cases(
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> RecognitionUseCases:
    return build_recognition_use_cases(db, storage)


def get_recognition_training_management_service(
    db: Session = Depends(get_db),
    storage: StorageService = Depends(get_storage_service),
) -> RecognitionTrainingManagementService:
    return RecognitionTrainingManagementService(db, storage)


def get_signal_design_use_cases(db: Session = Depends(get_db)) -> SignalDesignUseCases:
    return build_signal_design_use_cases(db)


def get_documents_use_cases(db: Session = Depends(get_db)) -> DocumentsUseCases:
    return build_documents_use_cases(db)
