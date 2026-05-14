"""Application bootstrap helpers."""

from __future__ import annotations

import logging
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from backend.config import settings


LOGGER_NAME = "komarov_thesis"


def configure_logging() -> logging.Logger:
    """Configure application logging once and return the root app logger."""
    logger = logging.getLogger(LOGGER_NAME)
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=getattr(logging, settings.log_level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s %(message)s",
        )
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    return logger


def ensure_runtime_directories() -> None:
    """Ensure local runtime directories exist."""
    for path in (
        settings.uploads_dir,
        settings.outputs_dir,
        settings.debug_output_dir,
        settings.object_storage_dir,
    ):
        path.mkdir(parents=True, exist_ok=True)


def register_pdf_fonts() -> None:
    """Register required PDF fonts if available."""
    registered = set(pdfmetrics.getRegisteredFontNames())
    font_specs = (
        ("GOST Type A", settings.regular_font_path),
        ("GOST Type A Bold", settings.bold_font_path),
    )
    for font_name, font_path in font_specs:
        if font_name in registered:
            continue
        if not font_path.exists():
            raise FileNotFoundError(f"Required font file is missing: {font_path}")
        pdfmetrics.registerFont(TTFont(font_name, str(font_path)))


def relative_to_root(path: Path | str) -> str:
    """Return a stable relative path for persisted project or runtime files."""
    value = Path(path)
    resolved = value.resolve()
    for root in (settings.project_root.resolve(), settings.data_dir.resolve()):
        try:
            return str(resolved.relative_to(root)).replace("\\", "/")
        except ValueError:
            continue
    return str(resolved.relative_to(settings.project_root.resolve())).replace("\\", "/")
