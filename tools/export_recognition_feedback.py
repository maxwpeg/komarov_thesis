"""Export recognition feedback into training-ready batches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.bootstrap import ensure_runtime_directories
from backend.composition import build_recognition_use_cases
from backend.database import SessionLocal, init_db
from backend.modules.shared.infrastructure.storage import StorageService
from backend.services.recognition_training_feedback_service import RecognitionTrainingFeedbackService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export recognition feedback")
    parser.add_argument("--batch-id", dest="batch_id", default=None, help="Optional explicit batch id prefix")
    parser.add_argument(
        "--output-root",
        dest="output_root",
        default=None,
        help="Optional output root. Defaults to outputs/recognition_feedback",
    )
    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Export legacy full-architecture samples collected by /recognition-feedback",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_runtime_directories()
    init_db()
    session = SessionLocal()
    try:
        storage = StorageService()
        if args.legacy:
            use_cases = build_recognition_use_cases(session, storage)
            result = use_cases.export_feedback_samples(
                batch_id=args.batch_id,
                output_root=Path(args.output_root) if args.output_root else None,
            )
        else:
            result = RecognitionTrainingFeedbackService(session, storage).export_feedback_batches(
                batch_id=args.batch_id,
                output_root=Path(args.output_root) if args.output_root else None,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
