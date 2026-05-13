"""Helpers for maintaining the managed-file metadata registry."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import mimetypes
from pathlib import Path

from sqlalchemy.orm import Session

from backend.assets import normalize_asset_path
from backend.modules.shared.infrastructure.persistence.models import ManagedFile
from backend.modules.shared.infrastructure.storage import SavedUpload, StorageService


def record_managed_file(
    session: Session,
    file_ref: SavedUpload | str | None,
    *,
    storage: StorageService | None = None,
    project_id: int | None = None,
    floor_plan_id: int | None = None,
    equipment_id: int | None = None,
    created_by_user_id: int | None = None,
    content_type: str | None = None,
) -> ManagedFile | None:
    """Upsert metadata for a backend-managed file path."""

    if file_ref is None:
        return None
    now = datetime.now(timezone.utc)
    if isinstance(file_ref, SavedUpload):
        path = file_ref.relative_path
        size_bytes = file_ref.size_bytes or None
        sha256 = file_ref.sha256 or None
        detected_content_type = file_ref.content_type or content_type
    else:
        path = file_ref
        size_bytes = None
        sha256 = None
        detected_content_type = content_type

    try:
        normalized_path = normalize_asset_path(path)
    except ValueError:
        return None
    if not normalized_path:
        return None

    if storage is not None and (size_bytes is None or sha256 is None or detected_content_type is None):
        metadata = _inspect_storage_path(storage, normalized_path)
        size_bytes = size_bytes if size_bytes is not None else metadata.get("size_bytes")
        sha256 = sha256 or metadata.get("sha256")
        detected_content_type = detected_content_type or metadata.get("content_type")

    storage_root = normalized_path.split("/", 1)[0] if "/" in normalized_path else "storage_objects"
    row = session.query(ManagedFile).filter(ManagedFile.path == normalized_path).first()
    if row is None:
        row = ManagedFile(path=normalized_path, created_at=now)
        session.add(row)

    row.storage_root = storage_root
    row.content_type = detected_content_type
    row.size_bytes = size_bytes
    row.sha256 = sha256
    row.project_id = project_id
    row.floor_plan_id = floor_plan_id
    row.equipment_id = equipment_id
    row.created_by_user_id = created_by_user_id
    row.last_seen_at = now
    row.updated_at = now
    session.flush()
    return row


def remove_managed_file(session: Session, path: str | None) -> None:
    """Remove metadata for a file that has been deleted from managed storage."""

    try:
        normalized_path = normalize_asset_path(path)
    except ValueError:
        return
    if not normalized_path:
        return
    (
        session.query(ManagedFile)
        .filter(ManagedFile.path == normalized_path)
        .delete(synchronize_session=False)
    )


def _inspect_storage_path(storage: StorageService, relative_path: str) -> dict[str, int | str | None]:
    path = storage.absolute_path(relative_path)
    if path is None or not path.exists() or not path.is_file():
        return {}
    return {
        "size_bytes": path.stat().st_size,
        "sha256": _file_sha256(path),
        "content_type": mimetypes.guess_type(path.name)[0],
    }


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
