"""Default in-process implementations of shared ports."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.modules.shared.application.ports import EventPublisherPort, FileStoragePort, TaskDispatcherPort
from backend.modules.shared.application.unit_of_work import UnitOfWork
from backend.modules.shared.infrastructure.persistence.models import AuditEvent
from backend.modules.shared.observability.context import get_request_id
from backend.modules.shared.infrastructure.storage import SavedUpload, StorageService


class SqlAlchemyUnitOfWork(UnitOfWork):
    """Thin transaction wrapper over a SQLAlchemy session."""

    def __init__(self, session: Session):
        self.session = session

    def flush(self) -> None:
        self.session.flush()

    def commit(self) -> None:
        self.session.commit()

    def rollback(self) -> None:
        self.session.rollback()


class StorageServiceAdapter(FileStoragePort):
    """Port adapter around the existing storage service."""

    def __init__(self, storage: StorageService):
        self._storage = storage

    def save_upload(self, upload: UploadFile, project_id: int, floor_number: int) -> SavedUpload:
        return self._storage.save_upload(upload, project_id, floor_number)

    def delete_relative_path(self, relative_path: str | None) -> None:
        self._storage.delete_relative_path(relative_path)

    def absolute_path(self, relative_path: str | None) -> Path | None:
        return self._storage.absolute_path(relative_path)

    def debug_dir(self, floor_plan_id: int) -> Path:
        return self._storage.debug_dir(floor_plan_id)

    def list_debug_images(self, relative_dir: str | None) -> list[dict[str, str]]:
        return self._storage.list_debug_images(relative_dir)


class NoOpEventPublisher(EventPublisherPort):
    """Default event publisher until an audit bus is introduced."""

    def publish(self, event_name: str, payload: dict[str, Any]) -> None:
        _ = (event_name, payload)


class SqlAlchemyEventPublisher(EventPublisherPort):
    """Persist audit events in the database and mirror them to structured logs."""

    def __init__(self, session: Session, logger: logging.Logger | None = None):
        self.session = session
        self.logger = logger or logging.getLogger("komarov_thesis")

    def publish(self, event_name: str, payload: dict[str, Any]) -> None:
        values = {
            "event_name": event_name,
            "category": str(payload.get("category", "application")),
            "use_case": str(payload.get("use_case", "unknown")),
            "request_id": str(payload.get("request_id") or get_request_id() or ""),
            "project_id": payload.get("project_id"),
            "floor_plan_id": payload.get("floor_plan_id"),
            "pipeline_step": payload.get("pipeline_step"),
            "system_type": payload.get("system_type"),
            "payload": payload.get("payload"),
        }
        with self.session.get_bind().begin() as connection:
            connection.execute(AuditEvent.__table__.insert().values(**values))
        self.logger.info(
            "audit_event event_name=%s category=%s use_case=%s request_id=%s project_id=%s floor_plan_id=%s pipeline_step=%s system_type=%s",
            event_name,
            values["category"],
            values["use_case"],
            values["request_id"],
            values["project_id"],
            values["floor_plan_id"],
            values["pipeline_step"],
            values["system_type"],
        )


class InProcessTaskDispatcher(TaskDispatcherPort):
    """Synchronous task dispatcher placeholder for future async extraction."""

    def dispatch(self, task_name: str, payload: dict[str, Any]) -> None:
        _ = (task_name, payload)
