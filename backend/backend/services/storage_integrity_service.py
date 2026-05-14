"""Storage integrity reporting for managed backend files."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from backend.config import settings
from backend.modules.shared.infrastructure.persistence.models import ManagedFile
from backend.modules.shared.infrastructure.storage import StorageService


class StorageIntegrityService:
    """Compare managed-file metadata against files present on disk."""

    def __init__(self, db: Session, storage: StorageService | None = None) -> None:
        self.db = db
        self.storage = storage or StorageService()

    def build_report(self, *, sample_limit: int = 200) -> dict[str, object]:
        rows = self.db.query(ManagedFile).order_by(ManagedFile.id.asc()).all()
        referenced_paths = {row.path for row in rows}
        missing = []
        for row in rows:
            try:
                path = self.storage.absolute_path(row.path)
            except ValueError:
                item = row.to_dict()
                item["error"] = "invalid_path"
                missing.append(item)
                continue
            if path is None or not path.exists():
                missing.append(row.to_dict())

        disk_paths = self._list_disk_files()
        orphan_paths = sorted(path for path in disk_paths if path not in referenced_paths)
        return {
            "registered_count": len(rows),
            "disk_file_count": len(disk_paths),
            "missing_count": len(missing),
            "orphan_count": len(orphan_paths),
            "missing": missing[:sample_limit],
            "orphans": orphan_paths[:sample_limit],
            "sample_limit": sample_limit,
        }

    def _list_disk_files(self) -> set[str]:
        roots: tuple[tuple[Path, str], ...] = (
            (settings.object_storage_dir, ""),
            (settings.uploads_dir, "uploads"),
            (settings.outputs_dir, "outputs"),
            (settings.debug_output_dir, "debug_output"),
        )
        result: set[str] = set()
        for root, prefix in roots:
            if not root.exists():
                continue
            resolved_root = root.resolve()
            for path in resolved_root.rglob("*"):
                if not path.is_file():
                    continue
                inner = path.resolve().relative_to(resolved_root).as_posix()
                result.add(f"{prefix}/{inner}" if prefix else inner)
        return result
