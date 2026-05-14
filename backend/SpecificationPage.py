from __future__ import annotations

from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from Page import Page
from backend.modules.documents.specification import (
    DEFAULT_EQUIPMENT_SPECIFICATION_COLUMN_HEADERS,
    DEFAULT_EQUIPMENT_SPECIFICATION_PAGE_TITLE,
)
from consts import (
    CENTER,
    DEFAULT_BORDER_COLOR,
    DEFAULT_FONT_NAME,
    DEFAULT_FONT_SIZE,
    DEFAULT_INNER_BORDER_THICKNESS_MM,
    DEFAULT_OUTER_BORDER_THICKNESS_MM,
    LEFT,
    MAIN_TITLE_BOX_DICT,
    PAGESIZE_A3_LANDSCAPE,
)


_ROW_FIELDS = (
    "position",
    "technical_name",
    "type_mark",
    "code",
    "manufacturer",
    "unit",
    "quantity",
    "unit_mass_kg",
    "note",
)


class SpecificationPage(Page):
    """A3 landscape equipment specification page."""

    def __init__(
        self,
        specification: dict | None = None,
        page_format: tuple[float, float] = PAGESIZE_A3_LANDSCAPE,
        main_title_box_type: str = "1",
        creds: dict[str, str] | None = None,
        page_number: int = 1,
    ):
        resolved_specification = specification or {}
        page_creds = dict(creds or {})
        page_creds["Title of the Drawing"] = str(
            resolved_specification.get("page_title") or DEFAULT_EQUIPMENT_SPECIFICATION_PAGE_TITLE
        )
        super().__init__(
            page_format=page_format,
            main_title_box_type=main_title_box_type,
            creds=page_creds,
            page_number=page_number,
        )
        self.specification = resolved_specification
        self._cell_padding_x = 1.6 * mm
        self._cell_padding_y = 1.2 * mm
        self._line_height = DEFAULT_FONT_SIZE * 1.15
        self._text_baseline_offset = DEFAULT_FONT_SIZE * 0.35
        self._min_column_widths = [
            18 * mm,
            70 * mm,
            66 * mm,
            32 * mm,
            30 * mm,
            18 * mm,
            18 * mm,
            18 * mm,
            34 * mm,
        ]

    def _split_lines(self, text: str) -> list[str]:
        normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
        return normalized.split("\n") or [""]

    def _wrap_text(self, text: str, width: float, *, font_name: str) -> list[str]:
        width = max(1.0, float(width))
        wrapped: list[str] = []
        for raw_line in self._split_lines(text):
            line = raw_line.strip()
            if not line:
                wrapped.append("")
                continue
            words = line.split()
            current = ""
            for word in words:
                candidate = f"{current} {word}".strip()
                if not current or pdfmetrics.stringWidth(candidate, font_name, DEFAULT_FONT_SIZE) <= width:
                    current = candidate
                    continue
                wrapped.append(current)
                current = word
            wrapped.append(current or "")
        return wrapped or [""]

    def _measure_natural_width(self, text: str, *, font_name: str) -> float:
        lines = self._split_lines(text)
        longest = max((pdfmetrics.stringWidth(line or " ", font_name, DEFAULT_FONT_SIZE) for line in lines), default=0.0)
        return longest + self._cell_padding_x * 2

    def _build_rows(self) -> list[dict]:
        headers = list(self.specification.get("column_headers") or DEFAULT_EQUIPMENT_SPECIFICATION_COLUMN_HEADERS)
        if len(headers) < len(_ROW_FIELDS):
            headers.extend([""] * (len(_ROW_FIELDS) - len(headers)))
        rows: list[dict] = [
            {
                "kind": "header",
                "values": headers[: len(_ROW_FIELDS)],
            }
        ]
        for section in self.specification.get("sections") or []:
            rows.append({"kind": "section", "title": str(section.get("title") or "")})
            for row in section.get("rows") or []:
                rows.append(
                    {
                        "kind": "data",
                        "source_key": row.get("source_key"),
                        "values": [str(row.get(field, "") or "") for field in _ROW_FIELDS],
                    }
                )
        return rows

    def _compute_column_widths(self, rows: list[dict], total_width: float) -> list[float]:
        headers = list(self.specification.get("column_headers") or DEFAULT_EQUIPMENT_SPECIFICATION_COLUMN_HEADERS)
        natural_widths = [
            max(self._min_column_widths[index], self._measure_natural_width(headers[index] if index < len(headers) else "", font_name=DEFAULT_FONT_NAME))
            for index in range(len(_ROW_FIELDS))
        ]
        for row in rows:
            if row.get("kind") != "data":
                continue
            values = row.get("values") or []
            for index, value in enumerate(values[: len(_ROW_FIELDS)]):
                natural_widths[index] = max(
                    natural_widths[index],
                    self._measure_natural_width(value, font_name=DEFAULT_FONT_NAME),
                )

        natural_total = sum(natural_widths)
        if natural_total < total_width:
            extra = total_width - natural_total
            flex_total = sum(natural_widths) or 1.0
            widths = [
                width + extra * (width / flex_total)
                for width in natural_widths
            ]
        else:
            shrinkable = [max(0.0, natural - minimum) for natural, minimum in zip(natural_widths, self._min_column_widths)]
            shrinkable_total = sum(shrinkable)
            if shrinkable_total > 0:
                overflow = natural_total - total_width
                widths = [
                    max(
                        minimum,
                        natural - overflow * (shrink / shrinkable_total),
                    )
                    for natural, minimum, shrink in zip(natural_widths, self._min_column_widths, shrinkable)
                ]
            else:
                scale = total_width / natural_total if natural_total else 1.0
                widths = [max(minimum, natural * scale) for natural, minimum in zip(natural_widths, self._min_column_widths)]
        correction = total_width - sum(widths)
        widths[-1] += correction
        return widths

    def _measure_row_height(self, row: dict, widths: list[float], total_width: float) -> tuple[float, dict]:
        if row["kind"] == "section":
            font_name = f"{DEFAULT_FONT_NAME} Bold"
            lines = self._wrap_text(row.get("title", ""), total_width - self._cell_padding_x * 2, font_name=font_name)
            content_height = len(lines) * self._line_height
            return content_height + self._cell_padding_y * 2, {"lines": lines}

        if row["kind"] == "header":
            wrapped_cells: list[list[str]] = []
            max_lines = 1
            for index, value in enumerate(row.get("values") or []):
                lines = self._wrap_text(value, widths[index] - self._cell_padding_x * 2, font_name=f"{DEFAULT_FONT_NAME} Bold")
                wrapped_cells.append(lines)
                max_lines = max(max_lines, len(lines))
            content_height = max_lines * self._line_height
            return content_height + self._cell_padding_y * 2, {"cells": wrapped_cells}

        wrapped_cells: list[list[str]] = []
        max_lines = 1
        for index, value in enumerate(row.get("values") or []):
            lines = self._wrap_text(value, widths[index] - self._cell_padding_x * 2, font_name=DEFAULT_FONT_NAME)
            wrapped_cells.append(lines)
            max_lines = max(max_lines, len(lines))
        content_height = max_lines * self._line_height
        return content_height + self._cell_padding_y * 2, {"cells": wrapped_cells}

    def _draw_multiline_text(
        self,
        c: canvas.Canvas,
        lines: list[str],
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        font_name: str = DEFAULT_FONT_NAME,
        align: str = LEFT,
    ) -> list[float]:
        total_text_height = len(lines) * self._line_height
        cursor_y = y + height - self._cell_padding_y - (height - total_text_height) / 2 - self._text_baseline_offset
        c.setFont(font_name, DEFAULT_FONT_SIZE)
        baselines: list[float] = []
        for line in lines:
            if align == CENTER:
                c.drawCentredString(x + width / 2, cursor_y, line)
            else:
                c.drawString(x + self._cell_padding_x, cursor_y, line)
            baselines.append(cursor_y)
            cursor_y -= self._line_height
        return baselines

    def _draw_section_row(
        self,
        c: canvas.Canvas,
        title: str,
        lines: list[str],
        *,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        c.rect(x, y, width, height, stroke=1, fill=0)
        baselines = self._draw_multiline_text(
            c,
            lines,
            x=x,
            y=y,
            width=width,
            height=height,
            font_name=f"{DEFAULT_FONT_NAME} Bold",
            align=CENTER,
        )
        c.setLineWidth(DEFAULT_INNER_BORDER_THICKNESS_MM)
        for line, baseline in zip(lines, baselines):
            text_width = pdfmetrics.stringWidth(line or " ", f"{DEFAULT_FONT_NAME} Bold", DEFAULT_FONT_SIZE)
            underline_width = min(text_width + 2.5 * mm, width - self._cell_padding_x * 2)
            underline_y = baseline - 1.0 * mm
            c.line(
                x + (width - underline_width) / 2,
                underline_y,
                x + (width + underline_width) / 2,
                underline_y,
            )

    def draw(self, c: canvas.Canvas):
        c.setPageSize((self.page_width, self.page_height))
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        self.draw_outer_border(c)
        self.draw_main_title_box(c, self.main_title_box_type)
        self.fill_main_title_box(c, self.main_title_box_type)

        title_box_height = MAIN_TITLE_BOX_DICT.get(self.main_title_box_type, MAIN_TITLE_BOX_DICT["1"])[1]
        content_left = self.borders_mm["left"]
        content_right = self.page_width - self.borders_mm["right"]
        content_top = self.page_height - self.borders_mm["top"]
        content_bottom = self.borders_mm["bottom"] + title_box_height
        content_width = content_right - content_left

        rows = self._build_rows()
        table_top = content_top
        widths = self._compute_column_widths(rows, content_width)

        current_y = table_top
        c.setStrokeColor(DEFAULT_BORDER_COLOR)
        c.setLineWidth(DEFAULT_INNER_BORDER_THICKNESS_MM)

        for row in rows:
            row_height, prepared = self._measure_row_height(row, widths, content_width)
            if current_y - row_height < content_bottom:
                break
            current_y -= row_height
            if row["kind"] == "section":
                self._draw_section_row(
                    c,
                    row.get("title", ""),
                    prepared["lines"],
                    x=content_left,
                    y=current_y,
                    width=content_width,
                    height=row_height,
                )
                continue

            cursor_x = content_left
            if row["kind"] == "header":
                alignments = [CENTER] * len(widths)
                font_name = f"{DEFAULT_FONT_NAME} Bold"
            else:
                alignments = [CENTER, LEFT, LEFT, LEFT, LEFT, CENTER, CENTER, CENTER, LEFT]
                font_name = DEFAULT_FONT_NAME
            for index, width in enumerate(widths):
                c.rect(cursor_x, current_y, width, row_height, stroke=1, fill=0)
                self._draw_multiline_text(
                    c,
                    prepared["cells"][index],
                    x=cursor_x,
                    y=current_y,
                    width=width,
                    height=row_height,
                    font_name=font_name,
                    align=alignments[index],
                )
                cursor_x += width

        c.showPage()
