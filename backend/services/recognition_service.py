"""Compatibility shim for recognition workflows."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.modules.recognition.application.use_cases import RecognitionUseCases
from backend.modules.recognition.infrastructure.sqlalchemy_repository import SqlAlchemyRecognitionRepository
from backend.modules.shared.infrastructure.runtime import SqlAlchemyUnitOfWork, StorageServiceAdapter
from backend.services.storage_service import StorageService


class RecognitionService:
    """Backward-compatible wrapper over modular recognition use cases."""

    def __init__(self, db: Session, storage: StorageService):
        self._use_cases = RecognitionUseCases(
            repository=SqlAlchemyRecognitionRepository(db),
            storage=StorageServiceAdapter(storage),
            uow=SqlAlchemyUnitOfWork(db),
        )

    def process_floor_plan(self, floor_plan_id: int, debug: bool = False) -> tuple[int, int, int, int, int, int]:
        return self._use_cases.process_floor_plan(floor_plan_id, debug=debug)

    def get_recognition(self, floor_plan_id: int, debug: bool = False):
        return self._use_cases.get_recognition(floor_plan_id, debug=debug)
