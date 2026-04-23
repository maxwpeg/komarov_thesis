"""Background worker loop and task execution."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.background_jobs import (
    TASK_FIRE_ALARM_AUTO_LAYOUT,
    TASK_PIPELINE_DETECT_OPENINGS,
    TASK_PIPELINE_DETECT_ROOMS,
    TASK_PIPELINE_DETECT_WALLS,
    TASK_PIPELINE_DETECT_ZKSPC,
    TASK_PROJECT_PDF_GENERATE,
    TASK_RECOGNITION_PROCESS,
    TASK_RECOGNITION_TRAINING_RUN,
    TASK_SOUE_AUTO_LAYOUT,
)
from backend.composition import (
    build_documents_use_cases,
    build_pipeline_use_cases,
    build_recognition_use_cases,
    build_signal_design_use_cases,
)
from backend.config import settings
from backend.database import SessionLocal
from backend.errors import AppError
from backend.models import FloorPlan, Project
from backend.modules.shared.infrastructure.storage import StorageService
from backend.services.background_task_service import BackgroundTaskService
from backend.services.recognition_training_management_service import RecognitionTrainingManagementService


logger = logging.getLogger(__name__)


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


@dataclass(slots=True)
class BackgroundTaskExecutor:
    db: Session
    storage: StorageService = field(default_factory=StorageService)

    def execute(self, task_id: int) -> dict:
        task_service = BackgroundTaskService(self.db)
        task = task_service.get_task(task_id)
        payload = task.payload or {}
        result = self._execute_task(task.task_type, payload, task_id=task.id)
        task_service.succeed(task.id, result_payload=result)
        return result

    def _execute_task(self, task_type: str, payload: dict, *, task_id: int) -> dict:
        if task_type == TASK_RECOGNITION_PROCESS:
            return self._execute_recognition_process(payload)
        if task_type == TASK_PIPELINE_DETECT_WALLS:
            return self._execute_pipeline_detect(payload, "walls")
        if task_type == TASK_PIPELINE_DETECT_OPENINGS:
            return self._execute_pipeline_detect(payload, "openings")
        if task_type == TASK_PIPELINE_DETECT_ROOMS:
            return self._execute_pipeline_detect(payload, "rooms")
        if task_type == TASK_PIPELINE_DETECT_ZKSPC:
            return self._execute_pipeline_detect(payload, "zkspc")
        if task_type == TASK_FIRE_ALARM_AUTO_LAYOUT:
            return self._execute_fire_alarm_auto_layout(payload)
        if task_type == TASK_SOUE_AUTO_LAYOUT:
            return self._execute_soue_auto_layout(payload)
        if task_type == TASK_PROJECT_PDF_GENERATE:
            return self._execute_project_pdf_generate(payload)
        if task_type == TASK_RECOGNITION_TRAINING_RUN:
            return self._execute_recognition_training_run(payload, task_id=task_id)
        raise AppError(400, "background_task_unsupported", f"Unsupported task type: {task_type}")

    def _execute_recognition_process(self, payload: dict) -> dict:
        floor_plan_id = int(payload["floor_plan_id"])
        debug = bool(payload.get("debug"))
        service = build_recognition_use_cases(self.db, self.storage)
        recognition_id, walls, doors, windows, rooms, dimensions = service.process_floor_plan(floor_plan_id, debug=debug)
        floor_plan = self.db.query(FloorPlan).filter(FloorPlan.id == floor_plan_id).first()
        return {
            "floor_plan_id": floor_plan_id,
            "project_id": int(floor_plan.project_id) if floor_plan is not None else None,
            "debug": debug,
            "recognition_id": recognition_id,
            "walls_detected": walls,
            "doors_detected": doors,
            "windows_detected": windows,
            "rooms_detected": rooms,
            "dimensions_detected": dimensions,
        }

    def _execute_pipeline_detect(self, payload: dict, step: str) -> dict:
        floor_plan_id = int(payload["floor_plan_id"])
        service = build_pipeline_use_cases(self.db, self.storage)
        if step == "walls":
            floor_plan, state = service.detect_walls(floor_plan_id)
        elif step == "openings":
            floor_plan, state = service.detect_openings(floor_plan_id)
        elif step == "rooms":
            floor_plan, state = service.detect_rooms(floor_plan_id)
        else:
            floor_plan, state = service.detect_zkspc(floor_plan_id)
        return {
            "floor_plan_id": floor_plan_id,
            "project_id": int(floor_plan.project_id),
            "step": step,
            "pipeline_state": state.model_dump(mode="json") if hasattr(state, "model_dump") else state,
        }

    def _execute_fire_alarm_auto_layout(self, payload: dict) -> dict:
        floor_plan_id = int(payload["floor_plan_id"])
        system_type = str(payload.get("system_type") or "non_addressable")
        service = build_signal_design_use_cases(self.db)
        layout = service.auto_layout_fire_alarms(floor_plan_id, system_type)
        floor_plan = self.db.query(FloorPlan).filter(FloorPlan.id == floor_plan_id).first()
        return {
            "floor_plan_id": floor_plan_id,
            "project_id": int(floor_plan.project_id) if floor_plan is not None else None,
            "system_type": system_type,
            "devices": layout.get("all_devices", layout.get("devices", [])),
            "summary": layout.get("summary", {}),
            "warnings": layout.get("warnings", []),
        }

    def _execute_soue_auto_layout(self, payload: dict) -> dict:
        floor_plan_id = int(payload["floor_plan_id"])
        system_type = str(payload.get("system_type") or "non_addressable")
        service = build_signal_design_use_cases(self.db)
        layout = service.auto_layout_soue_devices(floor_plan_id, system_type)
        floor_plan = self.db.query(FloorPlan).filter(FloorPlan.id == floor_plan_id).first()
        return {
            "floor_plan_id": floor_plan_id,
            "project_id": int(floor_plan.project_id) if floor_plan is not None else None,
            "system_type": system_type,
            "devices": layout.get("devices", []),
            "summary": layout.get("summary", {}),
            "warnings": layout.get("warnings", []),
        }

    def _execute_project_pdf_generate(self, payload: dict) -> dict:
        project_id = int(payload["project_id"])
        service = build_documents_use_cases(self.db)
        generated_pdf_path = service.generate_project_pdf(project_id)
        object_key = f"projects/{project_id}/pdf/project_{project_id}_{_utc_timestamp()}.pdf"
        stored_pdf_path = self.storage.save_generated_file(generated_pdf_path, object_key=object_key)
        project = self.db.query(Project).filter(Project.id == project_id).first()
        generated_at = datetime.now(timezone.utc)
        if project is not None:
            project.latest_pdf_path = stored_pdf_path
            project.latest_pdf_generated_at = generated_at
            self.db.commit()
        self.storage.delete_absolute_path(generated_pdf_path)
        return {
            "project_id": project_id,
            "pdf_path": stored_pdf_path,
            "generated_at": generated_at.isoformat(),
        }

    def _execute_recognition_training_run(self, payload: dict, *, task_id: int) -> dict:
        run_id = str(payload["run_id"])
        service = RecognitionTrainingManagementService(self.db, self.storage)
        run = service.get_run(run_id)
        if run.get("background_task_id") != task_id:
            model = service._get_run_model(run_id)  # pylint: disable=protected-access
            model.background_task_id = task_id
            self.db.commit()
        result = service.run_training_job(run_id)
        return {
            "run_id": run_id,
            "step": result.get("step"),
            "status": result.get("status"),
            "background_task_id": task_id,
        }


class BackgroundWorkerController:
    """Simple worker loop that can run inline or from a dedicated process."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="background-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._thread = None

    def _run_loop(self) -> None:
        logger.info("Background worker loop started")
        while not self._stop_event.is_set():
            claimed_task_id = None
            session = SessionLocal()
            try:
                task_service = BackgroundTaskService(session)
                claimed = task_service.claim_next()
                claimed_task_id = claimed.id if claimed is not None else None
            except Exception:  # pragma: no cover - defensive logging
                logger.exception("Failed to claim background task")
            finally:
                session.close()

            if claimed_task_id is None:
                self._stop_event.wait(settings.worker_poll_interval_seconds)
                continue

            execution_session = SessionLocal()
            try:
                BackgroundTaskExecutor(execution_session).execute(claimed_task_id)
            except Exception as exc:  # pragma: no cover - exercised via integration
                logger.exception("Background task %s failed", claimed_task_id)
                try:
                    BackgroundTaskService(execution_session).fail(claimed_task_id, exc)
                except Exception:
                    logger.exception("Failed to update background task %s status", claimed_task_id)
            finally:
                execution_session.close()
        logger.info("Background worker loop stopped")


worker_controller = BackgroundWorkerController()


def run_worker_forever() -> None:
    """Run the worker loop in the current process until interrupted."""
    logger.info("Starting dedicated worker process")
    try:
        while True:
            session = SessionLocal()
            try:
                task = BackgroundTaskService(session).claim_next()
                task_id = task.id if task is not None else None
            finally:
                session.close()
            if task_id is None:
                time.sleep(settings.worker_poll_interval_seconds)
                continue
            session = SessionLocal()
            try:
                BackgroundTaskExecutor(session).execute(task_id)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Worker task %s failed", task_id)
                try:
                    BackgroundTaskService(session).fail(task_id, exc)
                except Exception:
                    logger.exception("Unable to mark task %s as failed", task_id)
            finally:
                session.close()
    except KeyboardInterrupt:  # pragma: no cover - manual stop
        logger.info("Worker interrupted by keyboard")
