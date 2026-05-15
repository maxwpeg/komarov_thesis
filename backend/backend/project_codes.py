"""Helpers for project numbering and code formatting."""

from __future__ import annotations


CYRILLIC_PROJECT_CODE_PREFIX = "РП-ЗК"
LATIN_PROJECT_CODE_PREFIX = "RP-ZK"


def build_project_code(number: int, year: int, project_type: str) -> str:
    """Build a project code in the canonical Cyrillic format."""
    return f"{CYRILLIC_PROJECT_CODE_PREFIX}-{number}/{year % 100:02d}-{project_type}"


def normalize_project_code(code: str | None) -> str | None:
    """Normalize legacy Latin-prefix project codes to the Cyrillic format."""
    if code is None:
        return None
    if code.startswith(f"{LATIN_PROJECT_CODE_PREFIX}-"):
        return code.replace(f"{LATIN_PROJECT_CODE_PREFIX}-", f"{CYRILLIC_PROJECT_CODE_PREFIX}-", 1)
    return code
