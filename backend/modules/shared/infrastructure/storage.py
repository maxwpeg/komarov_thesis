"""Shared storage implementation used by backend modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile
from PIL import Image

from backend.bootstrap import ensure_runtime_directories
from backend.config import settings


@dataclass(frozen=True)
class SavedUpload:
    """Metadata about a persisted uploaded file."""

    relative_path: str
    width: int
    height: int


class StorageService:
    """Persistent storage helper used by the modular monolith."""

    def __init__(self) -> None:
        ensure_runtime_directories()

    def absolute_path(self, relative_path: str | None) -> Path | None:
        if not relative_path:
            return None
        return (settings.project_root / relative_path).resolve()

    def save_upload(self, upload: UploadFile, project_id: int, floor_number: int) -> SavedUpload:
        extension = Path(upload.filename or "upload.bin").suffix or ".bin"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        filename = f"floor_plan_{project_id}_{floor_number}_{timestamp}{extension}"
        target = settings.uploads_dir / filename
        with target.open("wb") as buffer:
            self._copy_stream(upload.file, buffer)

        with Image.open(target) as image:
            width = image.width
            height = image.height

        return SavedUpload(relative_path=f"uploads/{filename}", width=width, height=height)

    def save_equipment_upload(self, upload: UploadFile, equipment_id: int) -> SavedUpload:
        extension = Path(upload.filename or "upload.bin").suffix or ".bin"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        filename = f"equipment_{equipment_id}_{timestamp}{extension}"
        target = settings.uploads_dir / filename
        with target.open("wb") as buffer:
            self._copy_stream(upload.file, buffer)

        with Image.open(target) as image:
            width = image.width
            height = image.height

        return SavedUpload(relative_path=f"uploads/{filename}", width=width, height=height)

    def save_equipment_document_upload(self, upload: UploadFile, equipment_id: int, document_kind: str) -> str:
        extension = Path(upload.filename or "document.pdf").suffix or ".pdf"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        safe_kind = "".join(ch for ch in str(document_kind or "document") if ch.isalnum() or ch in {"_", "-"}) or "document"
        filename = f"equipment_{equipment_id}_{safe_kind}_{timestamp}{extension}"
        target = settings.uploads_dir / filename
        with target.open("wb") as buffer:
            self._copy_stream(upload.file, buffer)
        return f"uploads/{filename}"

    def delete_relative_path(self, relative_path: str | None) -> None:
        path = self.absolute_path(relative_path)
        if path and path.exists():
            path.unlink()

    def debug_dir(self, floor_plan_id: int) -> Path:
        path = settings.debug_output_dir / f"floor_plan_{floor_plan_id}"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def list_debug_images(self, relative_dir: str | None) -> list[dict[str, str]]:
        if not relative_dir:
            return []
        base_path = self.absolute_path(relative_dir)
        if not base_path or not base_path.exists():
            return []

        images: list[dict[str, str]] = []
        for path in sorted(base_path.iterdir()):
            if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
                continue
            rel_path = path.resolve().relative_to(settings.project_root.resolve())
            images.append(
                {
                    "step": path.stem.replace("_", " "),
                    "path": str(rel_path).replace("\\", "/"),
                }
            )
        return images

    @staticmethod
    def _copy_stream(source: BinaryIO, destination: BinaryIO, chunk_size: int = 1024 * 1024) -> None:
        while True:
            chunk = source.read(chunk_size)
            if not chunk:
                break
            destination.write(chunk)
