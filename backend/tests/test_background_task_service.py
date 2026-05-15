from __future__ import annotations

import pytest

import backend.database as database
from backend.errors import AppError
from backend.services.background_task_service import BackgroundTaskService


def test_cancel_queued_background_task_prevents_claim(isolated_database):
    _ = isolated_database
    with database.SessionLocal() as db:
        service = BackgroundTaskService(db)
        task = service.enqueue(task_type="project_pdf_generate", payload={"project_id": 1})

        canceled = service.cancel(task.id, message="Canceled in test")

        assert canceled.status == "canceled"
        assert canceled.error_message == "Canceled in test"
        assert service.claim_next() is None


def test_cancel_running_background_task_is_rejected(isolated_database):
    _ = isolated_database
    with database.SessionLocal() as db:
        service = BackgroundTaskService(db)
        task = service.enqueue(task_type="project_pdf_generate", payload={"project_id": 1})
        claimed = service.claim_next()

        with pytest.raises(AppError) as exc:
            service.cancel(claimed.id)

        assert exc.value.status_code == 409
        assert exc.value.code == "background_task_not_cancelable"


def test_failed_background_task_can_be_retried_with_progress_reset(isolated_database):
    _ = isolated_database
    with database.SessionLocal() as db:
        service = BackgroundTaskService(db)
        task = service.enqueue(task_type="project_pdf_generate", payload={"project_id": 1})
        claimed = service.claim_next()

        failed = service.fail(claimed.id, "boom", retry=False)
        retried = service.retry(failed.id)

        assert retried.id == task.id
        assert retried.status == "queued"
        assert retried.error_message is None
        assert retried.attempts == 0
        assert retried.progress_percent == 0
        assert retried.progress_stage == "queued"
