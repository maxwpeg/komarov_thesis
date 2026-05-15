"""Additional info payload builder for editor and PDF generation."""

from __future__ import annotations

from typing import Any


ADDITIONAL_INFO_PAGE_TITLE = "Доп. сведения"
ADDITIONAL_INFO_HEADING = "ДОП. СВЕДЕНИЯ"


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _text_to_blocks(text: str) -> list[dict[str, str]]:
    normalized = _normalize_text(text).replace("\r\n", "\n").replace("\r", "\n")
    blocks: list[dict[str, str]] = []
    for raw_paragraph in normalized.split("\n\n"):
        collapsed = " ".join(line.strip() for line in raw_paragraph.splitlines() if line.strip())
        if collapsed:
            blocks.append({"kind": "paragraph", "text": collapsed})
    return blocks


def build_project_additional_info(project: Any) -> dict[str, Any]:
    text = _normalize_text(getattr(project, "additional_info_text", ""))
    blocks = _text_to_blocks(text)
    return {
        "project_id": int(getattr(project, "id", 0) or 0),
        "page_title": ADDITIONAL_INFO_PAGE_TITLE,
        "heading": ADDITIONAL_INFO_HEADING,
        "local_sheet_title": ADDITIONAL_INFO_PAGE_TITLE,
        "text": text,
        "is_empty": not bool(blocks),
        "blocks": blocks,
    }
