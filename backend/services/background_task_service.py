"""Persistent background task queue helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import asc
from sqlalchemy.orm import Session, joinedload

from backend.errors import AppError
from backend.models import BackgroundTask


ACTIVE_BACKGROUND_TASK_STATUSES = ("queued", "running")
TERMINAL_BACKGROUND_TASK_STATUSES = ("succeeded", "failed", "canceled")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class BackgroundTaskService:
    db: Session

    def enqueue(
        self,
        *,
        task_type: str,
        requested_by_user_id: int | None = None,
        project_id: int | None = None,
        floor_plan_id: int | None = None,
        payload: dict[str, Any] | None = None,
        dedupe_key: str | None = None,
        resource_path: str | None = None,
    ) -> BackgroundTask:
        if dedupe_key:
            existing = (
                self.db.query(BackgroundTask)
                .options(joinedload(BackgroundTask.requested_by_user))
                .filter(
                    BackgroundTask.dedupe_key == dedupe_key,
                    BackgroundTask.status.in_(ACTIVE_BACKGROUND_TASK_STATUSES),
                )
                .order_by(BackgroundTask.created_at.desc(), BackgroundTask.id.desc())
                .first()
            )
            if existing is not None:
                return existing

        task = BackgroundTask(
            task_type=task_type,
            status="queued",
            requested_by_user_id=requested_by_user_id,
            project_id=project_id,
            floor_plan_id=floor_plan_id,
            payload=payload or {},
            result_payload={},
            attempts=0,
            dedupe_key=dedupe_key,
            resource_path=resource_path,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return self.get_task(task.id)

    def list_tasks(
        self,
        *,
        requested_by_user_id: int | None = None,
        project_id: int | None = None,
        floor_plan_id: int | None = None,
        status: str | None = None,
        task_type: str | None = None,
        limit: int = 200,
    ) -> list[BackgroundTask]:
        query = (
            self.db.query(BackgroundTask)
            .options(joinedload(BackgroundTask.requested_by_user))
            .order_by(BackgroundTask.created_at.desc(), BackgroundTask.id.desc())
        )
        if requested_by_user_id is not None:
            query = query.filter(BackgroundTask.requested_by_user_id == requested_by_user_id)
        if project_id is not None:
            query = query.filter(BackgroundTask.project_id == project_id)
        if floor_plan_id is not None:
            query = query.filter(BackgroundTask.floor_plan_id == floor_plan_id)
        if status:
            query = query.filter(BackgroundTask.status == status)
        if task_type:
            query = query.filter(BackgroundTask.task_type == task_type)
        return query.limit(max(int(limit), 1)).all()

    def get_task(self, task_id: int) -> BackgroundTask:
        task = (
            self.db.query(BackgroundTask)
            .options(joinedload(BackgroundTask.requested_by_user))
            .filter(BackgroundTask.id == task_id)
            .first()
        )
        if task is None:
            raise AppError(404, "background_task_not_found", "Background task not found")
        return task

    def claim_next(self) -> BackgroundTask | None:
        query = (
            self.db.query(BackgroundTask)
            .filter(BackgroundTask.status == "queued")
            .order_by(asc(BackgroundTask.created_at), asc(BackgroundTask.id))
        )
        task = query.first()
        if task is None:
            return None
        now = utcnow()
        task.status = "running"
        task.attempts = int(task.attempts or 0) + 1
        task.started_at = task.started_at or now
        task.heartbeat_at = now
        task.updated_at = now
        self.db.commit()
        return self.get_task(task.id)

    def heartbeat(self, task_id: int) -> BackgroundTask:
        task = self.get_task(task_id)
        task.heartbeat_at = utcnow()
        task.updated_at = utcnow()
        self.db.commit()
        return task

    def succeed(self, task_id: int, *, result_payload: dict[str, Any] | None = None) -> BackgroundTask:
        task = self.get_task(task_id)
        now = utcnow()
        task.status = "succeeded"
        task.result_payload = result_payload or {}
        task.error_message = None
        task.finished_at = now
        task.heartbeat_at = now
        task.updated_at = now
        self.db.commit()
        return task

    def fail(self, task_id: int, error: Exception | str) -> BackgroundTask:
        task = self.get_task(task_id)
        now = utcnow()
        task.status = "failed"
        task.error_message = str(error)
        task.finished_at = now
        task.heartbeat_at = now
        task.updated_at = now
        self.db.commit()
        return task

    def cancel(self, task_id: int, *, message: str | None = None) -> BackgroundTask:
        task = self.get_task(task_id)
        now = utcnow()
        task.status = "canceled"
        task.error_message = message
        task.finished_at = now
        task.updated_at = now
        self.db.commit()
        return task
