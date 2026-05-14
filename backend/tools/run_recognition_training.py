"""Run one recognition training job in a standalone subprocess."""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


def _ensure_project_root_on_path() -> Path:
    project_root = Path(__file__).resolve().parents[1]
    project_root_str = str(project_root)
    normalized_sys_path = {str(Path(item).resolve()) for item in sys.path if item}
    if project_root_str not in normalized_sys_path:
        sys.path.insert(0, project_root_str)
    return project_root


def _mark_run_failed_on_startup(run_id: str, error_message: str) -> None:
    try:
        _ensure_project_root_on_path()
        from backend.database import SessionLocal
        from backend.models import RecognitionTrainingRun

        session = SessionLocal()
        try:
            run = session.query(RecognitionTrainingRun).filter(RecognitionTrainingRun.run_id == run_id).first()
            if run is None:
                return
            run.status = "failed"
            run.error_message = error_message
            run.finished_at = datetime.now(timezone.utc)
            if run.training_batch is not None:
                run.training_batch.status = "failed"
            session.commit()
        finally:
            session.close()
    except Exception:
        traceback.print_exc()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one recognition training job")
    parser.add_argument("--run-id", dest="run_id", required=True, help="Recognition training run id")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        _ensure_project_root_on_path()
        from backend.services.recognition_training_management_service import run_training_job_main

        return run_training_job_main(args.run_id)
    except Exception as exc:
        traceback.print_exc()
        _mark_run_failed_on_startup(args.run_id, f"Training runner startup failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
