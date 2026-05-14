from __future__ import annotations

import io
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from Page import Page
from backend.assets import normalize_asset_path
from backend.config import settings
from consts import (
    DEFAULT_BORDER_COLOR,
    DEFAULT_FONT_NAME,
    DEFAULT_FONT_SIZE,
    DEFAULT_INNER_BORDER_THICKNESS_MM,
    DEFAULT_OUTER_BORDER_THICKNESS_MM,
    MAIN_TITLE_BOX_DICT,
    PAGESIZE_A3_LANDSCAPE,
)


class ConnectionDiagramPage(Page):
    """A3 sheet for a cleaned equipment connection diagram."""

    HEADING_FONT_SIZE = 16
    META_FONT_SIZE = 10
    MIN_PREPARED_IMAGE_SIDE_PX = 2200

    def __init__(
        self,
        diagram: dict | None = None,
        page_format: tuple[float, float] = PAGESIZE_A3_LANDSCAPE,
        main_title_box_type: str = "1",
        creds: dict[str, str] | None = None,
        page_number: int = 1,
    ):
        self.diagram = diagram or {}
        page_creds = dict(creds or {})
        page_creds["Title of the Drawing"] = self._title_box_text()
        super().__init__(
            page_format=page_format,
            main_title_box_type=main_title_box_type,
            creds=page_creds,
            page_number=page_number,
        )

    def _title_box_text(self) -> str:
        name = str(self.diagram.get("name") or "").strip()
        return f"Схема подключения {name}" if name else "Схема подключения оборудования"

    def _content_bounds(self) -> tuple[float, float, float, float]:
        title_box_height = MAIN_TITLE_BOX_DICT.get(self.main_title_box_type, MAIN_TITLE_BOX_DICT["1"])[1]
        content_left = self.borders_mm["left"]
        content_right = self.page_width - self.borders_mm["right"]
        content_top = self.page_height - self.borders_mm["top"]
        content_bottom = self.borders_mm["bottom"] + title_box_height
        return content_left, content_right, content_top, content_bottom

    def _resolve_image_path(self) -> Path | None:
        normalized = normalize_asset_path(self.diagram.get("connection_diagram_path"))
        if not normalized or normalized.startswith(("http://", "https://")):
            return None

        candidates = [
            settings.object_storage_dir / normalized,
            settings.project_root / normalized,
        ]
        if normalized.startswith(("uploads/", "outputs/", "debug_output/")):
            candidates.insert(0, settings.project_root / normalized)

        for candidate in candidates:
            resolved = candidate.resolve()
            if resolved.exists() and resolved.is_file():
                return resolved
        return None

    def _prepare_image(self, image_path: Path) -> io.BytesIO:
        with Image.open(image_path) as source:
            image = source.convert("L")
            image = ImageOps.autocontrast(image, cutoff=1)
            image = image.filter(ImageFilter.SHARPEN)
            max_side = max(image.size)
            if max_side < self.MIN_PREPARED_IMAGE_SIDE_PX:
                scale = min(
                    4,
                    max(2, int(self.MIN_PREPARED_IMAGE_SIDE_PX / max(max_side, 1)) + 1),
                )
                image = image.resize((image.width * scale, image.height * scale), Image.Resampling.LANCZOS)
            image = ImageOps.autocontrast(image, cutoff=1).convert("RGB")

            buffer = io.BytesIO()
            image.save(buffer, format="PNG", optimize=True)
            buffer.seek(0)
            return buffer

    def _draw_heading(self, c: canvas.Canvas, *, x: float, y: float, width: float) -> float:
        equipment_name = str(self.diagram.get("name") or "").strip()
        technical_name = str(self.diagram.get("technical_name") or "").strip()
        manufacturer = str(self.diagram.get("manufacturer") or "").strip()

        c.setFillColor(colors.black)
        c.setFont(f"{DEFAULT_FONT_NAME} Bold", self.HEADING_FONT_SIZE)
        c.drawCentredString(x + width / 2, y, "СХЕМА ПОДКЛЮЧЕНИЯ")

        subheading_parts = [part for part in (technical_name, equipment_name) if part]
        subheading = " - ".join(subheading_parts) or "Оборудование"
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        c.drawCentredString(x + width / 2, y - 8 * mm, subheading)

        if manufacturer:
            c.setFont(DEFAULT_FONT_NAME, self.META_FONT_SIZE)
            c.drawCentredString(x + width / 2, y - 14 * mm, f"Производитель: {manufacturer}")
            return y - 20 * mm
        return y - 16 * mm

    def _draw_image_frame(self, c: canvas.Canvas, *, x: float, y: float, width: float, height: float) -> None:
        c.setStrokeColor(DEFAULT_BORDER_COLOR)
        c.setLineWidth(DEFAULT_INNER_BORDER_THICKNESS_MM)
        c.rect(x, y, width, height, stroke=1, fill=0)

    def _draw_missing_image(
        self,
        c: canvas.Canvas,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        message: str,
    ) -> None:
        self._draw_image_frame(c, x=x, y=y, width=width, height=height)
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        c.setFillColor(colors.black)
        c.drawCentredString(x + width / 2, y + height / 2, message)

    def _draw_diagram_image(
        self,
        c: canvas.Canvas,
        *,
        image_buffer: io.BytesIO,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        with Image.open(image_buffer) as image:
            image_width, image_height = image.size
        image_buffer.seek(0)

        padding = 4 * mm
        available_width = max(1, width - padding * 2)
        available_height = max(1, height - padding * 2)
        scale = min(available_width / image_width, available_height / image_height)
        draw_width = image_width * scale
        draw_height = image_height * scale
        draw_x = x + (width - draw_width) / 2
        draw_y = y + (height - draw_height) / 2

        self._draw_image_frame(c, x=x, y=y, width=width, height=height)
        c.drawImage(
            ImageReader(image_buffer),
            draw_x,
            draw_y,
            width=draw_width,
            height=draw_height,
            preserveAspectRatio=True,
            mask="auto",
        )

    def draw(self, c: canvas.Canvas):
        c.setPageSize((self.page_width, self.page_height))
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        self.draw_outer_border(c)
        self.draw_main_title_box(c, self.main_title_box_type)
        self.fill_main_title_box(c, self.main_title_box_type)

        content_left, content_right, content_top, content_bottom = self._content_bounds()
        content_x = content_left + 8 * mm
        content_width = content_right - content_left - 16 * mm
        cursor_y = self._draw_heading(c, x=content_x, y=content_top - 10 * mm, width=content_width)

        frame_x = content_x
        frame_top = cursor_y - 2 * mm
        frame_bottom = content_bottom + 8 * mm
        frame_height = max(1, frame_top - frame_bottom)

        image_path = self._resolve_image_path()
        if image_path is None:
            self._draw_missing_image(
                c,
                x=frame_x,
                y=frame_bottom,
                width=content_width,
                height=frame_height,
                message="Изображение схемы подключения не найдено",
            )
        else:
            try:
                image_buffer = self._prepare_image(image_path)
            except (OSError, UnidentifiedImageError, ValueError):
                self._draw_missing_image(
                    c,
                    x=frame_x,
                    y=frame_bottom,
                    width=content_width,
                    height=frame_height,
                    message="Не удалось подготовить изображение схемы подключения",
                )
            else:
                self._draw_diagram_image(
                    c,
                    image_buffer=image_buffer,
                    x=frame_x,
                    y=frame_bottom,
                    width=content_width,
                    height=frame_height,
                )

        c.setLineWidth(DEFAULT_OUTER_BORDER_THICKNESS_MM)
        c.showPage()
