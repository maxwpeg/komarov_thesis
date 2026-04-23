"""Shared storage implementation used by backend modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import BinaryIO

from fastapi import UploadFile
from PIL import Image

from backend.assets import build_asset_url, normalize_asset_path
from backend.bootstrap import ensure_runtime_directories, relative_to_root
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

    def public_url(self, relative_path: str | None) -> str | None:
        return build_asset_url(relative_path)

    def absolute_path(self, relative_path: str | None) -> Path | None:
        normalized = normalize_asset_path(relative_path)
        if not normalized:
            return None
        if normalized.startswith(("uploads/", "outputs/", "debug_output/")):
            return (settings.project_root / normalized).resolve()
        return (settings.object_storage_dir / normalized).resolve()

    def save_upload(self, upload: UploadFile, project_id: int, floor_number: int) -> SavedUpload:
        extension = Path(upload.filename or "upload.bin").suffix or ".bin"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        relative_path = f"floor-plans/project_{project_id}/floor_{floor_number}_{timestamp}{extension}"
        target = self._object_target(relative_path)
        with target.open("wb") as buffer:
            self._copy_stream(upload.file, buffer)

        with Image.open(target) as image:
            width = image.width
            height = image.height

        return SavedUpload(relative_path=relative_path, width=width, height=height)

    def save_equipment_upload(self, upload: UploadFile, equipment_id: int) -> SavedUpload:
        extension = Path(upload.filename or "upload.bin").suffix or ".bin"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        relative_path = f"equipment/{equipment_id}/image_{timestamp}{extension}"
        target = self._object_target(relative_path)
        with target.open("wb") as buffer:
            self._copy_stream(upload.file, buffer)

        with Image.open(target) as image:
            width = image.width
            height = image.height

        return SavedUpload(relative_path=relative_path, width=width, height=height)

    def save_equipment_document_upload(self, upload: UploadFile, equipment_id: int, document_kind: str) -> str:
        extension = Path(upload.filename or "document.pdf").suffix or ".pdf"
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        safe_kind = "".join(ch for ch in str(document_kind or "document") if ch.isalnum() or ch in {"_", "-"}) or "document"
        relative_path = f"equipment/{equipment_id}/{safe_kind}_{timestamp}{extension}"
        target = self._object_target(relative_path)
        with target.open("wb") as buffer:
            self._copy_stream(upload.file, buffer)
        return relative_path

    def save_generated_file(self, source_path: str | Path, *, object_key: str) -> str:
        source = Path(source_path).resolve()
        if not source.exists():
            raise FileNotFoundError(source)
        relative_path = normalize_asset_path(object_key)
        if not relative_path:
            raise ValueError("object_key is required")
        target = self._object_target(relative_path)
        shutil.copy2(source, target)
        return relative_path

    def delete_relative_path(self, relative_path: str | None) -> None:
        path = self.absolute_path(relative_path)
        if not path or not path.exists():
            return
        self._delete_path(path)

    def delete_absolute_path(self, path: str | Path | None) -> None:
        if not path:
            return
        resolved = Path(path).resolve()
        if not resolved.exists():
            return
        self._delete_path(resolved)

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
            rel_path = relative_to_root(path)
            images.append(
                {
                    "step": path.stem.replace("_", " "),
                    "path": rel_path,
                    "asset_url": self.public_url(rel_path),
                }
            )
        return images

    def _object_target(self, relative_path: str) -> Path:
        normalized = normalize_asset_path(relative_path)
        if not normalized:
            raise ValueError("relative_path is required")
        target = (settings.object_storage_dir / normalized).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    @staticmethod
    def _delete_path(path: Path) -> None:
        root = settings.project_root.resolve()
        object_root = settings.object_storage_dir.resolve()
        resolved = path.resolve()
        if root not in resolved.parents and resolved != root and object_root not in resolved.parents and resolved != object_root:
            raise ValueError(f"Refusing to delete path outside the workspace: {resolved}")
        if resolved.is_dir():
            shutil.rmtree(resolved, ignore_errors=True)
        else:
            resolved.unlink(missing_ok=True)

    @staticmethod
    def _copy_stream(source: BinaryIO, destination: BinaryIO, chunk_size: int = 1024 * 1024) -> None:
        while True:
            chunk = source.read(chunk_size)
            if not chunk:
                break
            destination.write(chunk)
