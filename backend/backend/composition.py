"""Application composition root for the modular monolith."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.modules.documents.application.use_cases import DocumentsUseCases
from backend.modules.documents.infrastructure.pdf_adapter import PdfGeneratorAdapter
from backend.modules.documents.infrastructure.sqlalchemy_repository import SqlAlchemyDocumentReadRepository
from backend.modules.equipment.application.use_cases import EquipmentUseCases
from backend.modules.equipment.infrastructure.sqlalchemy_repository import SqlAlchemyEquipmentRepository
from backend.modules.elements_geometry.application.use_cases import ElementsGeometryUseCases
from backend.modules.elements_geometry.infrastructure.sqlalchemy_repository import SqlAlchemyElementsRepository
from backend.modules.floor_plans.application.use_cases import FloorPlanUseCases
from backend.modules.floor_plans.infrastructure.sqlalchemy_repository import SqlAlchemyFloorPlanRepository
from backend.modules.pipeline.infrastructure.legacy_orchestrator import LegacyPipelineOrchestrator
from backend.modules.pipeline.application.use_cases import PipelineUseCases
from backend.modules.projects.application.use_cases import ProjectUseCases
from backend.modules.projects.infrastructure.sqlalchemy_repository import SqlAlchemyProjectRepository
from backend.modules.recognition.application.use_cases import RecognitionUseCases
from backend.modules.recognition.infrastructure.sqlalchemy_repository import SqlAlchemyRecognitionRepository
from backend.modules.shared.infrastructure.runtime import (
    SqlAlchemyEventPublisher,
    SqlAlchemyUnitOfWork,
    StorageServiceAdapter,
)
from backend.modules.shared.infrastructure.storage import StorageService
from backend.modules.signal_design.application.use_cases import SignalDesignUseCases
from backend.modules.signal_design.infrastructure.sqlalchemy_repository import SqlAlchemySignalDesignRepository
from backend.services.pipeline_service import PipelineService


def build_project_use_cases(session: Session) -> ProjectUseCases:
    """Build project use cases with explicit repository and transaction wiring."""
    return ProjectUseCases(SqlAlchemyProjectRepository(session), SqlAlchemyUnitOfWork(session))


def build_equipment_use_cases(session: Session, storage: StorageService) -> EquipmentUseCases:
    """Build equipment catalog use cases."""
    return EquipmentUseCases(SqlAlchemyEquipmentRepository(session, storage), SqlAlchemyUnitOfWork(session))


def build_floor_plan_use_cases(session: Session, storage: StorageService) -> FloorPlanUseCases:
    """Build floor-plan use cases with storage and SQL adapters."""
    repository = SqlAlchemyFloorPlanRepository(session, StorageServiceAdapter(storage))
    return FloorPlanUseCases(repository, SqlAlchemyUnitOfWork(session))


def build_elements_geometry_use_cases(session: Session) -> ElementsGeometryUseCases:
    """Build element geometry use cases."""
    return ElementsGeometryUseCases(
        SqlAlchemyElementsRepository(session),
        SqlAlchemyUnitOfWork(session),
        SqlAlchemyEventPublisher(session),
    )


def build_pipeline_use_cases(session: Session, storage: StorageService) -> PipelineUseCases:
    """Build pipeline use cases with the legacy orchestration service behind explicit handlers."""
    return PipelineUseCases(
        LegacyPipelineOrchestrator(PipelineService(session, storage)),
        SqlAlchemyEventPublisher(session),
    )


def build_recognition_use_cases(session: Session, storage: StorageService) -> RecognitionUseCases:
    """Build recognition use cases with explicit repository wiring."""
    return RecognitionUseCases(
        SqlAlchemyRecognitionRepository(session),
        StorageServiceAdapter(storage),
        SqlAlchemyUnitOfWork(session),
        SqlAlchemyEventPublisher(session),
    )


def build_signal_design_use_cases(session: Session) -> SignalDesignUseCases:
    """Build signal-design use cases."""
    return SignalDesignUseCases(
        SqlAlchemySignalDesignRepository(session),
        SqlAlchemyUnitOfWork(session),
        SqlAlchemyEventPublisher(session),
    )


def build_documents_use_cases(session: Session) -> DocumentsUseCases:
    """Build document-generation use cases."""
    return DocumentsUseCases(
        SqlAlchemyDocumentReadRepository(session),
        SqlAlchemyUnitOfWork(session),
        PdfGeneratorAdapter(),
        SqlAlchemyEventPublisher(session),
    )
