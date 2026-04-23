"""Run the backend background worker loop as a dedicated process."""

from backend.bootstrap import configure_logging, ensure_runtime_directories
from backend.database import init_db
from backend.services.background_worker import run_worker_forever


def main() -> None:
    configure_logging()
    ensure_runtime_directories()
    init_db()
    run_worker_forever()


if __name__ == "__main__":
    main()
