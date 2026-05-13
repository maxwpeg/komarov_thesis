"""Helpers for backend-managed asset URLs."""

from __future__ import annotations

from pathlib import PurePosixPath
from urllib.parse import quote

from backend.config import settings


API_ASSET_PREFIX = "/api/assets/"


def normalize_asset_path(value: str | None) -> str | None:
    """Normalize persisted asset paths or object keys to a stable slash form."""
    if not value:
        return None
    raw = str(value).strip().replace("\\", "/")
    if raw.startswith(API_ASSET_PREFIX):
        raw = raw[len(API_ASSET_PREFIX):]
    if "://" in raw or raw.startswith("//"):
        raise ValueError("External asset URLs are not supported as storage paths")
    normalized = raw.lstrip("/")
    if not normalized:
        return None
    path = PurePosixPath(normalized)
    parts = path.parts
    if path.is_absolute() or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("Asset path must be relative and must not contain traversal segments")
    if any(":" in part for part in parts):
        raise ValueError("Asset path must not contain drive or scheme separators")
    return "/".join(parts)


def build_asset_url(value: str | None) -> str | None:
    """Build a frontend-safe URL for a persisted asset path."""
    normalized = normalize_asset_path(value)
    if not normalized:
        return None
    if normalized.startswith(("http://", "https://", "/api/assets/")):
        return normalized
    public_base = str(settings.asset_public_base_url or "").rstrip("/")
    quoted = quote(normalized, safe="/")
    if public_base:
        return f"{public_base}/api/assets/{quoted}"
    return f"/api/assets/{quoted}"
