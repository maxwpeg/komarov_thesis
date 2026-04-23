"""Helpers for backend-managed asset URLs."""

from __future__ import annotations

from urllib.parse import quote

from backend.config import settings


def normalize_asset_path(value: str | None) -> str | None:
    """Normalize persisted asset paths or object keys to a stable slash form."""
    if not value:
        return None
    normalized = str(value).strip().replace("\\", "/").lstrip("/")
    return normalized or None


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
