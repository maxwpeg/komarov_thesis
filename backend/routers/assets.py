"""Authenticated asset proxy endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from backend.auth import AuthenticatedUser, require_current_user
from backend.errors import AppError
from backend.modules.shared.infrastructure.storage import StorageService


router = APIRouter(tags=["system"], dependencies=[Depends(require_current_user)])


@router.get("/api/assets/{asset_path:path}")
def get_asset(
    asset_path: str,
    _: AuthenticatedUser = Depends(require_current_user),
) -> FileResponse:
    storage = StorageService()
    resolved = storage.absolute_path(asset_path)
    if resolved is None or not resolved.exists() or not resolved.is_file():
        raise AppError(404, "asset_not_found", "Asset not found")
    return FileResponse(resolved)
