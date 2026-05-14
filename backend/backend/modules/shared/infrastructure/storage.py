"""Shared storage implementation used by backend modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import shutil
from typing import BinaryIO
from uuid import uuid4

from fastapi import UploadFile
from PIL import Image, UnidentifiedImageError

from backend.assets import build_asset_url, normalize_asset_path
from backend.bootstrap import ensure_runtime_directories, relative_to_root
from backend.config import settings
from backend.errors import AppError


Image.MAX_IMAGE_PIXELS = settings.max_image_pixels


@dataclass(frozen=True)
class SavedUpload:
    """Metadata about a persisted uploaded file."""

    relative_path: str
    width: int
    height: int
    size_bytes: int = 0
    sha256: str = ""
    content_type: str | None = None


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
        root, inner_path = self._root_for_asset_path(normalized)
        return self._resolve_inside(root, inner_path)

    def save_upload(self, upload: UploadFile, project_id: int, floor_number: int) -> SavedUpload:
        extension = self._validated_extension(upload.filename, settings.allowed_image_types, default=".png")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        relative_path = f"floor-plans/project_{project_id}/floor_{floor_number}_{timestamp}{extension}"
        target = self._object_target(relative_path)
        size_bytes, digest = self._write_upload_atomically(
            upload,
            target,
            max_bytes=settings.max_upload_bytes,
            validator=lambda path: self._validate_image_file(
                path,
                min_width=settings.min_floor_plan_image_size_px,
                min_height=settings.min_floor_plan_image_size_px,
            ),
        )
        width, height = self._image_size(target)
        return SavedUpload(
            relative_path=relative_path,
            width=width,
            height=height,
            size_bytes=size_bytes,
            sha256=digest,
            content_type=upload.content_type,
        )

    def save_equipment_upload(self, upload: UploadFile, equipment_id: int) -> SavedUpload:
        extension = self._validated_extension(upload.filename, settings.allowed_image_types, default=".png")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        relative_path = f"equipment/{equipment_id}/image_{timestamp}{extension}"
        target = self._object_target(relative_path)
        size_bytes, digest = self._write_upload_atomically(
            upload,
            target,
            max_bytes=settings.max_upload_bytes,
            validator=self._validate_image_file,
        )
        width, height = self._image_size(target)
        return SavedUpload(
            relative_path=relative_path,
            width=width,
            height=height,
            size_bytes=size_bytes,
            sha256=digest,
            content_type=upload.content_type,
        )

    def save_equipment_connection_diagram_upload(self, upload: UploadFile, equipment_id: int) -> SavedUpload:
        extension = self._validated_extension(upload.filename, settings.allowed_image_types, default=".png")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        relative_path = f"equipment/{equipment_id}/connection_diagram_{timestamp}{extension}"
        target = self._object_target(relative_path)
        size_bytes, digest = self._write_upload_atomically(
            upload,
            target,
            max_bytes=settings.max_upload_bytes,
            validator=self._validate_image_file,
        )
        width, height = self._image_size(target)
        return SavedUpload(
            relative_path=relative_path,
            width=width,
            height=height,
            size_bytes=size_bytes,
            sha256=digest,
            content_type=upload.content_type,
        )

    def save_equipment_document_upload(self, upload: UploadFile, equipment_id: int, document_kind: str) -> str:
        extension = self._validated_extension(upload.filename, settings.allowed_document_types, default=".pdf")
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        safe_kind = "".join(ch for ch in str(document_kind or "document") if ch.isalnum() or ch in {"_", "-"}) or "document"
        relative_path = f"equipment/{equipment_id}/{safe_kind}_{timestamp}{extension}"
        target = self._object_target(relative_path)
        self._write_upload_atomically(
            upload,
            target,
            max_bytes=settings.max_document_upload_bytes,
            validator=self._validate_pdf_file,
        )
        return relative_path

    def save_generated_file(self, source_path: str | Path, *, object_key: str) -> str:
        source = Path(source_path).resolve()
        if not source.exists():
            raise FileNotFoundError(source)
        relative_path = normalize_asset_path(object_key)
        if not relative_path:
            raise ValueError("object_key is required")
        target = self._object_target(relative_path)
        tmp_path = self._temporary_sibling(target)
        try:
            shutil.copy2(source, tmp_path)
            os.replace(tmp_path, target)
        finally:
            tmp_path.unlink(missing_ok=True)
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
        target = self._resolve_inside(settings.object_storage_dir, normalized)
        target.parent.mkdir(parents=True, exist_ok=True)
        return target

    @staticmethod
    def _delete_path(path: Path) -> None:
        roots = (
            settings.uploads_dir.resolve(),
            settings.outputs_dir.resolve(),
            settings.debug_output_dir.resolve(),
            settings.object_storage_dir.resolve(),
        )
        resolved = path.resolve()
        if not any(resolved == root or root in resolved.parents for root in roots):
            raise ValueError(f"Refusing to delete path outside managed storage: {resolved}")
        if resolved.is_dir():
            shutil.rmtree(resolved, ignore_errors=True)
        else:
            resolved.unlink(missing_ok=True)

    @staticmethod
    def _copy_stream(
        source: BinaryIO,
        destination: BinaryIO,
        *,
        max_bytes: int,
        chunk_size: int = 1024 * 1024,
    ) -> tuple[int, str]:
        total = 0
        digest = hashlib.sha256()
        while True:
            chunk = source.read(chunk_size)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("Uploaded file is too large")
            digest.update(chunk)
            destination.write(chunk)
        return total, digest.hexdigest()

    @staticmethod
    def _root_for_asset_path(normalized_path: str) -> tuple[Path, str]:
        root_map = {
            "uploads": settings.uploads_dir,
            "outputs": settings.outputs_dir,
            "debug_output": settings.debug_output_dir,
        }
        prefix, _, rest = normalized_path.partition("/")
        if prefix in root_map:
            if not rest:
                raise ValueError("Asset path must include a file path")
            return root_map[prefix], rest
        return settings.object_storage_dir, normalized_path

    @staticmethod
    def _resolve_inside(root: Path, relative_path: str) -> Path:
        normalized = normalize_asset_path(relative_path)
        if not normalized:
            raise ValueError("relative_path is required")
        resolved_root = root.resolve()
        target = (resolved_root / normalized).resolve()
        if target != resolved_root and resolved_root not in target.parents:
            raise ValueError(f"Refusing to resolve path outside managed storage: {target}")
        return target

    @staticmethod
    def _validated_extension(filename: str | None, allowed_types: tuple[str, ...], *, default: str) -> str:
        extension = Path(filename or default).suffix.lower() or default
        normalized_allowed = {f".{item.lower().lstrip('.')}" for item in allowed_types}
        if extension not in normalized_allowed:
            raise AppError(400, "unsupported_upload_extension", f"Unsupported file extension: {extension}")
        return extension

    @staticmethod
    def _temporary_sibling(target: Path) -> Path:
        return target.with_name(f".{target.name}.{uuid4().hex}.tmp")

    def _write_upload_atomically(
        self,
        upload: UploadFile,
        target: Path,
        *,
        max_bytes: int,
        validator,
    ) -> tuple[int, str]:
        tmp_path = self._temporary_sibling(target)
        try:
            with tmp_path.open("wb") as buffer:
                size_bytes, digest = self._copy_stream(upload.file, buffer, max_bytes=max_bytes)
                buffer.flush()
                os.fsync(buffer.fileno())
            validator(tmp_path)
            os.replace(tmp_path, target)
            return size_bytes, digest
        except ValueError as exc:
            raise AppError(400, "invalid_upload_file", str(exc)) from exc
        finally:
            tmp_path.unlink(missing_ok=True)

    @staticmethod
    def _validate_image_file(path: Path, *, min_width: int | None = None, min_height: int | None = None) -> None:
        try:
            with Image.open(path) as image:
                image.verify()
        except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
            raise ValueError("Uploaded file is not a valid image") from exc
        if min_width is not None or min_height is not None:
            with Image.open(path) as image:
                width = int(image.width)
                height = int(image.height)
            if min_width is not None and width < int(min_width):
                raise ValueError(f"Image width must be at least {int(min_width)} px")
            if min_height is not None and height < int(min_height):
                raise ValueError(f"Image height must be at least {int(min_height)} px")

    @staticmethod
    def _image_size(path: Path) -> tuple[int, int]:
        with Image.open(path) as image:
            return int(image.width), int(image.height)

    @staticmethod
    def _validate_pdf_file(path: Path) -> None:
        with path.open("rb") as file:
            header = file.read(5)
        if header != b"%PDF-":
            raise ValueError("Uploaded file is not a valid PDF document")
