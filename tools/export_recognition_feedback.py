"""Export approved recognition feedback samples into a training batch."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.bootstrap import ensure_runtime_directories
from backend.composition import build_recognition_use_cases
from backend.database import SessionLocal, init_db
from backend.modules.shared.infrastructure.storage import StorageService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export approved recognition feedback samples")
    parser.add_argument("--batch-id", dest="batch_id", default=None, help="Optional explicit batch id")
    parser.add_argument(
        "--output-root",
        dest="output_root",
        default=None,
        help="Optional output root. Defaults to outputs/recognition_feedback",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    ensure_runtime_directories()
    init_db()
    session = SessionLocal()
    try:
        use_cases = build_recognition_use_cases(session, StorageService())
        result = use_cases.export_feedback_samples(
            batch_id=args.batch_id,
            output_root=Path(args.output_root) if args.output_root else None,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
