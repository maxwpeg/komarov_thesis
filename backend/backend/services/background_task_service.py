"""Persistent background task queue helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import asc, update
from sqlalchemy.orm import Session, joinedload, selectinload

from backend.config import settings
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
            progress_percent=0,
            progress_stage="queued",
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
            .options(joinedload(BackgroundTask.requested_by_user), selectinload(BackgroundTask.training_runs))
            .filter(BackgroundTask.id == task_id)
            .first()
        )
        if task is None:
            raise AppError(404, "background_task_not_found", "Background task not found")
        return task

    def claim_next(self) -> BackgroundTask | None:
        self.reconcile_stale_running_tasks()
        now = utcnow()
        while True:
            task_id = (
                self.db.query(BackgroundTask.id)
                .filter(BackgroundTask.status == "queued")
                .order_by(asc(BackgroundTask.created_at), asc(BackgroundTask.id))
                .limit(1)
                .scalar()
            )
            if task_id is None:
                return None
            result = self.db.execute(
                update(BackgroundTask)
                .where(BackgroundTask.id == task_id, BackgroundTask.status == "queued")
                .values(
                    status="running",
                    attempts=BackgroundTask.attempts + 1,
                    progress_percent=5,
                    progress_stage="started",
                    started_at=now,
                    heartbeat_at=now,
                    updated_at=now,
                )
            )
            if result.rowcount == 1:
                self.db.commit()
                return self.get_task(int(task_id))
            self.db.rollback()

    def heartbeat(self, task_id: int) -> BackgroundTask:
        task = self.get_task(task_id)
        task.heartbeat_at = utcnow()
        task.updated_at = utcnow()
        self.db.commit()
        return task

    def update_progress(
        self,
        task_id: int,
        *,
        percent: int | None = None,
        stage: str | None = None,
    ) -> BackgroundTask:
        task = self.get_task(task_id)
        if percent is not None:
            task.progress_percent = min(max(int(percent), 0), 100)
        if stage is not None:
            task.progress_stage = str(stage)[:120]
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
        task.progress_percent = 100
        task.progress_stage = "succeeded"
        task.finished_at = now
        task.heartbeat_at = now
        task.updated_at = now
        self.db.commit()
        return task

    def fail(self, task_id: int, error: Exception | str, *, retry: bool = True) -> BackgroundTask:
        task = self.get_task(task_id)
        now = utcnow()
        task.error_message = str(error)
        task.heartbeat_at = now
        task.updated_at = now
        if retry and int(task.attempts or 0) < settings.worker_max_attempts:
            task.status = "queued"
            task.started_at = None
            task.finished_at = None
            task.progress_percent = 0
            task.progress_stage = "retrying"
        else:
            task.status = "failed"
            task.progress_stage = "failed"
            task.finished_at = now
        self.db.commit()
        return task

    def cancel(self, task_id: int, *, message: str | None = None) -> BackgroundTask:
        task = self.get_task(task_id)
        if task.status != "queued":
            raise AppError(409, "background_task_not_cancelable", "Only queued tasks can be canceled")
        now = utcnow()
        task.status = "canceled"
        task.error_message = message or "Task canceled by administrator"
        task.progress_stage = "canceled"
        task.finished_at = now
        task.heartbeat_at = now
        task.updated_at = now
        for run in task.training_runs:
            if run.status == "queued":
                run.status = "canceled"
                run.error_message = task.error_message
                run.finished_at = now
                if run.training_batch is not None:
                    run.training_batch.status = "canceled"
        self.db.commit()
        return self.get_task(task_id)

    def retry(self, task_id: int) -> BackgroundTask:
        task = self.get_task(task_id)
        if task.status != "failed":
            raise AppError(409, "background_task_not_retryable", "Only failed tasks can be retried")
        now = utcnow()
        task.status = "queued"
        task.error_message = None
        task.started_at = None
        task.finished_at = None
        task.heartbeat_at = None
        task.attempts = 0
        task.progress_percent = 0
        task.progress_stage = "queued"
        task.updated_at = now
        for run in task.training_runs:
            if run.status == "failed":
                run.status = "queued"
                run.error_message = None
                run.started_at = None
                run.finished_at = None
                if run.training_batch is not None and run.training_batch.status == "failed":
                    run.training_batch.status = "queued"
        self.db.commit()
        return self.get_task(task_id)

    def reconcile_stale_running_tasks(self) -> int:
        cutoff = utcnow() - timedelta(seconds=max(int(settings.worker_stale_after_seconds), 1))
        stale_tasks = (
            self.db.query(BackgroundTask)
            .filter(
                BackgroundTask.status == "running",
                BackgroundTask.heartbeat_at.is_not(None),
                BackgroundTask.heartbeat_at < cutoff,
            )
            .all()
        )
        changed = 0
        now = utcnow()
        for task in stale_tasks:
            changed += 1
            task.error_message = "Task heartbeat expired"
            task.updated_at = now
            if int(task.attempts or 0) < settings.worker_max_attempts:
                task.status = "queued"
                task.started_at = None
                task.finished_at = None
                task.progress_percent = 0
                task.progress_stage = "retrying"
            else:
                task.status = "failed"
                task.progress_stage = "failed"
                task.finished_at = now
        if changed:
            self.db.commit()
        return changed
