from __future__ import annotations

from typing import Any

from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from .Page import Page
from .consts import (
    CENTER,
    DEFAULT_BORDER_COLOR,
    DEFAULT_FONT_NAME,
    DEFAULT_FONT_SIZE,
    DEFAULT_INNER_BORDER_THICKNESS_MM,
    LEFT,
    MAIN_TITLE_BOX_DICT,
    PAGESIZE_A4,
)


class PowerConsumptionCalculationPage(Page):
    """A4 portrait page for the power consumption calculation."""

    COLUMN_WIDTHS_MM = (10.0, 56.0, 16.0, 16.0, 22.5, 22.5, 21.0, 21.0)
    INNER_FRAME_MARGIN = 5.0 * mm

    def __init__(
        self,
        calculation: dict[str, Any] | None = None,
        *,
        page_rows: list[dict[str, Any]] | None = None,
        show_intro: bool = True,
        show_summary: bool = False,
        is_continuation: bool = False,
        page_format: tuple[float, float] = PAGESIZE_A4,
        main_title_box_type: str = "1",
        creds: dict[str, str] | None = None,
        page_number: int = 1,
    ):
        page_creds = dict(creds or {})
        page_creds["Title of the Drawing"] = "Расчет токопотребления системы"
        super().__init__(
            page_format=page_format,
            main_title_box_type=main_title_box_type,
            creds=page_creds,
            page_number=page_number,
        )
        self.calculation = calculation or {}
        self.page_rows = list(page_rows or [])
        self.show_intro = show_intro
        self.show_summary = show_summary
        self.is_continuation = is_continuation
        self._line_height = DEFAULT_FONT_SIZE * 1.15
        self._cell_padding_x = 1.2 * mm
        self._cell_padding_y = 1.0 * mm
        self._text_baseline_offset = DEFAULT_FONT_SIZE * 0.35
        self._table_text_shift_down = 0.7 * mm
        self._page_title_height = 8.0 * mm
        self._page_title_top_margin = 6.0 * mm
        self._page_title_gap = 4.0 * mm
        self._paragraph_gap = 2.0 * mm
        self._section_gap = 3.0 * mm
        self._caption_gap = 2.0 * mm
        self._table_title_row_height = 8.0 * mm
        self._table_header_row_height = 14.0 * mm
        self._table_subheader_row_height = 10.5 * mm
        self._category_row_height = 8.0 * mm
        self._summary_to_text_gap = 4.0 * mm
        self._paragraph_first_line_indent = 15.0 * mm
        raw_column_widths = [width * mm for width in self.COLUMN_WIDTHS_MM]
        content_left, content_right, _content_top, _content_bottom = self._content_bounds()
        usable_table_width = (content_right - content_left) - (self.INNER_FRAME_MARGIN * 2)
        scale = usable_table_width / sum(raw_column_widths)
        self._column_widths = [width * scale for width in raw_column_widths]

    @classmethod
    def paginate(
        cls,
        calculation: dict[str, Any] | None,
        *,
        page_format: tuple[float, float] = PAGESIZE_A4,
        main_title_box_type: str = "1",
        creds: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        probe = cls(
            calculation=calculation,
            page_rows=[],
            show_intro=True,
            show_summary=False,
            is_continuation=False,
            page_format=page_format,
            main_title_box_type=main_title_box_type,
            creds=creds,
            page_number=1,
        )
        flat_rows = probe._flatten_body_rows()
        if not flat_rows:
            flat_rows = []

        segments: list[dict[str, Any]] = []
        remaining_rows = list(flat_rows)
        show_intro = True

        while remaining_rows:
            available_height = probe._table_available_height(show_intro=show_intro)
            page_rows: list[dict[str, Any]] = []

            while remaining_rows:
                next_row = remaining_rows[0]
                row_height = probe._measure_table_row_height(next_row)
                if next_row.get("kind") == "category" and len(remaining_rows) > 1 and remaining_rows[1].get("kind") == "data":
                    required_height = row_height + probe._measure_table_row_height(remaining_rows[1])
                else:
                    required_height = row_height

                if page_rows and available_height < required_height:
                    break
                if not page_rows and available_height < row_height:
                    page_rows.append(remaining_rows.pop(0))
                    available_height -= row_height
                    continue
                if available_height < required_height:
                    break

                page_rows.append(remaining_rows.pop(0))
                available_height -= row_height

            segments.append(
                {
                    "page_rows": page_rows,
                    "show_intro": show_intro,
                    "show_summary": False,
                    "is_continuation": not show_intro,
                }
            )
            show_intro = False

        if not segments:
            segments.append(
                {
                    "page_rows": [],
                    "show_intro": True,
                    "show_summary": False,
                    "is_continuation": False,
                }
            )

        summary_height = probe._measure_summary_block_height()
        last_segment = segments[-1]
        remaining_on_last_page = probe._table_available_height(show_intro=bool(last_segment["show_intro"]))
        remaining_on_last_page -= sum(probe._measure_table_row_height(row) for row in last_segment["page_rows"])

        if remaining_on_last_page >= summary_height:
            last_segment["show_summary"] = True
        else:
            segments.append(
                {
                    "page_rows": [],
                    "show_intro": False,
                    "show_summary": True,
                    "is_continuation": True,
                }
            )
        return segments

    def _content_bounds(self) -> tuple[float, float, float, float]:
        title_box_height = MAIN_TITLE_BOX_DICT.get(self.main_title_box_type, MAIN_TITLE_BOX_DICT["1"])[1]
        content_left = self.borders_mm["left"]
        content_right = self.page_width - self.borders_mm["right"]
        content_top = self.page_height - self.borders_mm["top"]
        content_bottom = self.borders_mm["bottom"] + title_box_height
        return content_left, content_right, content_top, content_bottom

    def _split_lines(self, text: str) -> list[str]:
        normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
        return normalized.split("\n") or [""]

    def _wrap_text(self, text: str, width: float, *, font_name: str = DEFAULT_FONT_NAME) -> list[str]:
        width = max(1.0, float(width))
        lines: list[str] = []
        for raw_line in self._split_lines(text):
            words = raw_line.split()
            if not words:
                lines.append("")
                continue
            current = ""
            for word in words:
                candidate = f"{current} {word}".strip()
                if not current or pdfmetrics.stringWidth(candidate, font_name, DEFAULT_FONT_SIZE) <= width:
                    current = candidate
                    continue
                lines.append(current)
                current = word
            lines.append(current or "")
        return lines or [""]

    def _wrap_paragraph(self, text: str, width: float, *, first_line_indent: float = 0.0) -> list[str]:
        lines: list[str] = []
        words = str(text or "").split()
        if not words:
            return [""]

        current = ""
        current_width = max(1.0, width - first_line_indent)
        use_indent = True
        for word in words:
            candidate = f"{current} {word}".strip()
            if not current or pdfmetrics.stringWidth(candidate, DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE) <= current_width:
                current = candidate
                continue
            lines.append(current)
            current = word
            if use_indent:
                current_width = width
                use_indent = False
        lines.append(current or "")
        return lines

    def _draw_lines_in_box(
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
        baseline_shift_down: float = 0.0,
    ) -> None:
        total_text_height = len(lines) * self._line_height
        cursor_y = y + height - self._cell_padding_y - (height - total_text_height) / 2 - self._text_baseline_offset - baseline_shift_down
        c.setFont(font_name, DEFAULT_FONT_SIZE)
        for line in lines:
            if align == CENTER:
                c.drawCentredString(x + width / 2, cursor_y, line)
            elif align == "right":
                c.drawRightString(x + width - self._cell_padding_x, cursor_y, line)
            else:
                c.drawString(x + self._cell_padding_x, cursor_y, line)
            cursor_y -= self._line_height

    def _measure_data_row_height(self, row: dict[str, Any]) -> float:
        values = [
            row.get("number", ""),
            row.get("equipment_name", ""),
            row.get("unit", ""),
            row.get("quantity", ""),
            row.get("standby_current", ""),
            row.get("alarm_current", ""),
            row.get("standby_total", ""),
            row.get("alarm_total", ""),
        ]
        max_lines = 1
        for index, value in enumerate(values):
            lines = self._wrap_text(str(value), self._column_widths[index] - self._cell_padding_x * 2)
            max_lines = max(max_lines, len(lines))
        return max_lines * self._line_height + self._cell_padding_y * 2

    def _measure_summary_row_height(self, row: dict[str, Any]) -> float:
        label_width = sum(self._column_widths[:6]) - self._cell_padding_x * 2
        label_lines = self._wrap_text(row.get("label", ""), label_width)
        max_lines = len(label_lines)
        if row.get("kind") == "summary":
            for value in (row.get("standby", ""), row.get("alarm", "")):
                max_lines = max(max_lines, len(self._wrap_text(str(value), self._column_widths[6] - self._cell_padding_x * 2)))
                max_lines = max(max_lines, len(self._wrap_text(str(value), self._column_widths[7] - self._cell_padding_x * 2)))
        else:
            max_lines = max(
                max_lines,
                len(self._wrap_text(str(row.get("value", "")), sum(self._column_widths[6:]) - self._cell_padding_x * 2)),
            )
        return max_lines * self._line_height + self._cell_padding_y * 2

    def _measure_table_row_height(self, row: dict[str, Any]) -> float:
        kind = row.get("kind")
        if kind == "category":
            return self._category_row_height
        if kind == "summary" or kind == "summary_merged":
            return self._measure_summary_row_height(row)
        return self._measure_data_row_height(row)

    def _measure_paragraph_height(self, text: str, width: float, *, first_line_indent: float = 0.0) -> float:
        lines = self._wrap_paragraph(text, width, first_line_indent=first_line_indent)
        return len(lines) * self._line_height

    def _measure_summary_block_height(self) -> float:
        summary_rows = self.calculation.get("summary_rows") or []
        summary_height = sum(self._measure_summary_row_height(row) for row in summary_rows)
        if not summary_rows:
            return 0.0
        content_left, content_right, _content_top, _content_bottom = self._content_bounds()
        final_text = str(self.calculation.get("final_text", "") or "")
        final_text_height = self._measure_paragraph_height(
            final_text,
            (content_right - content_left) - (self.INNER_FRAME_MARGIN * 2),
            first_line_indent=self._paragraph_first_line_indent,
        )
        return summary_height + self._summary_to_text_gap + final_text_height

    def _table_available_height(self, *, show_intro: bool) -> float:
        content_left, content_right, content_top, content_bottom = self._content_bounds()
        available_height = content_top - content_bottom
        available_height -= self._page_title_top_margin + self._page_title_height + self._page_title_gap
        if show_intro:
            intro_texts = list(self.calculation.get("introductory_texts") or [])
            content_width = (content_right - content_left) - (self.INNER_FRAME_MARGIN * 2)
            for index, paragraph in enumerate(intro_texts):
                available_height -= self._measure_paragraph_height(
                    paragraph,
                    content_width,
                    first_line_indent=self._paragraph_first_line_indent,
                )
                if index < len(intro_texts) - 1:
                    available_height -= self._paragraph_gap
            available_height -= self._section_gap
        available_height -= self._line_height + self._caption_gap
        available_height -= self._table_title_row_height + self._table_header_row_height + self._table_subheader_row_height
        return available_height

    def _flatten_body_rows(self) -> list[dict[str, Any]]:
        flat_rows: list[dict[str, Any]] = []
        for category in self.calculation.get("categories") or []:
            flat_rows.append({"kind": "category", "title": category.get("title", "")})
            for row in category.get("rows") or []:
                flat_rows.append({"kind": "data", **row})
        return flat_rows

    def _draw_page_title(self, c: canvas.Canvas, *, x: float, y_top: float, width: float) -> float:
        c.setFont(f"{DEFAULT_FONT_NAME} Bold", DEFAULT_FONT_SIZE)
        title_y_top = y_top - self._page_title_top_margin
        c.drawCentredString(
            x + width / 2,
            title_y_top - self._page_title_height + self._text_baseline_offset + 1.0 * mm,
            self.calculation.get("page_title", ""),
        )
        return title_y_top - self._page_title_height - self._page_title_gap

    def _draw_paragraph(self, c: canvas.Canvas, text: str, *, x: float, y_top: float, width: float, first_line_indent: float = 0.0) -> float:
        lines = self._wrap_paragraph(text, width, first_line_indent=first_line_indent)
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        cursor_y = y_top - self._text_baseline_offset
        for index, line in enumerate(lines):
            line_x = x + (first_line_indent if index == 0 else 0.0)
            c.drawString(line_x, cursor_y, line)
            cursor_y -= self._line_height
        return cursor_y

    def _draw_caption(self, c: canvas.Canvas, *, x: float, y_top: float) -> float:
        caption = str(self.calculation.get("table_caption", "") or "")
        if self.is_continuation:
            caption = f"{caption} (продолжение)"
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        c.drawString(x, y_top - self._text_baseline_offset, caption)
        return y_top - self._line_height - self._caption_gap

    def _draw_table_header(self, c: canvas.Canvas, *, x: float, y_top: float) -> float:
        total_width = sum(self._column_widths)
        current_y = y_top

        c.rect(x, current_y - self._table_title_row_height, total_width, self._table_title_row_height, stroke=1, fill=0)
        self._draw_lines_in_box(
            c,
            [str(self.calculation.get("table_title", "") or "")],
            x=x,
            y=current_y - self._table_title_row_height,
            width=total_width,
            height=self._table_title_row_height,
            font_name=f"{DEFAULT_FONT_NAME} Bold",
            align=CENTER,
            baseline_shift_down=self._table_text_shift_down,
        )
        current_y -= self._table_title_row_height

        row_span_height = self._table_header_row_height + self._table_subheader_row_height
        cursor_x = x
        rowspan_headers = (
            "№",
            "Наименование оборудования",
            "Ед. изм",
            "Кол-во",
        )
        for index, header in enumerate(rowspan_headers):
            width = self._column_widths[index]
            c.rect(cursor_x, current_y - row_span_height, width, row_span_height, stroke=1, fill=0)
            self._draw_lines_in_box(
                c,
                self._wrap_text(header, width - self._cell_padding_x * 2, font_name=f"{DEFAULT_FONT_NAME} Bold"),
                x=cursor_x,
                y=current_y - row_span_height,
                width=width,
                height=row_span_height,
                font_name=f"{DEFAULT_FONT_NAME} Bold",
                align=CENTER,
                baseline_shift_down=self._table_text_shift_down,
            )
            cursor_x += width

        grouped_headers = (
            ("Токопотребление, А", self._column_widths[4] + self._column_widths[5]),
            ("Токопотребление общее, А", self._column_widths[6] + self._column_widths[7]),
        )
        for header, width in grouped_headers:
            c.rect(cursor_x, current_y - self._table_header_row_height, width, self._table_header_row_height, stroke=1, fill=0)
            self._draw_lines_in_box(
                c,
                self._wrap_text(header, width - self._cell_padding_x * 2, font_name=f"{DEFAULT_FONT_NAME} Bold"),
                x=cursor_x,
                y=current_y - self._table_header_row_height,
                width=width,
                height=self._table_header_row_height,
                font_name=f"{DEFAULT_FONT_NAME} Bold",
                align=CENTER,
                baseline_shift_down=self._table_text_shift_down,
            )
            cursor_x += width

        current_y -= self._table_header_row_height
        subheaders = ('Дежурный\nрежим', 'Режим\n"Пожар"', 'Дежурный\nрежим', 'Режим\n"Пожар"')
        cursor_x = x + sum(self._column_widths[:4])
        for index, header in enumerate(subheaders, start=4):
            width = self._column_widths[index]
            c.rect(cursor_x, current_y - self._table_subheader_row_height, width, self._table_subheader_row_height, stroke=1, fill=0)
            self._draw_lines_in_box(
                c,
                self._wrap_text(header, width - self._cell_padding_x * 2, font_name=f"{DEFAULT_FONT_NAME} Bold"),
                x=cursor_x,
                y=current_y - self._table_subheader_row_height,
                width=width,
                height=self._table_subheader_row_height,
                font_name=f"{DEFAULT_FONT_NAME} Bold",
                align=CENTER,
                baseline_shift_down=self._table_text_shift_down,
            )
            cursor_x += width

        return current_y - self._table_subheader_row_height

    def _draw_category_row(self, c: canvas.Canvas, row: dict[str, Any], *, x: float, y_top: float) -> float:
        height = self._category_row_height
        total_width = sum(self._column_widths)
        c.rect(x, y_top - height, total_width, height, stroke=1, fill=0)
        self._draw_lines_in_box(
            c,
            self._wrap_text(str(row.get("title", "") or ""), total_width - self._cell_padding_x * 2, font_name=f"{DEFAULT_FONT_NAME} Bold"),
            x=x,
            y=y_top - height,
            width=total_width,
            height=height,
            font_name=f"{DEFAULT_FONT_NAME} Bold",
            align=CENTER,
            baseline_shift_down=self._table_text_shift_down,
        )
        return y_top - height

    def _draw_data_row(self, c: canvas.Canvas, row: dict[str, Any], *, x: float, y_top: float) -> float:
        height = self._measure_data_row_height(row)
        values = [
            row.get("number", ""),
            row.get("equipment_name", ""),
            row.get("unit", ""),
            row.get("quantity", ""),
            row.get("standby_current", ""),
            row.get("alarm_current", ""),
            row.get("standby_total", ""),
            row.get("alarm_total", ""),
        ]
        alignments = ("right", LEFT, CENTER, CENTER, "right", "right", "right", "right")

        cursor_x = x
        for index, value in enumerate(values):
            width = self._column_widths[index]
            c.rect(cursor_x, y_top - height, width, height, stroke=1, fill=0)
            self._draw_lines_in_box(
                c,
                self._wrap_text(str(value), width - self._cell_padding_x * 2),
                x=cursor_x,
                y=y_top - height,
                width=width,
                height=height,
                align=alignments[index],
                baseline_shift_down=self._table_text_shift_down,
            )
            cursor_x += width
        return y_top - height

    def _draw_summary_row(self, c: canvas.Canvas, row: dict[str, Any], *, x: float, y_top: float) -> float:
        height = self._measure_summary_row_height(row)
        label_width = sum(self._column_widths[:6])
        label_lines = self._wrap_text(str(row.get("label", "") or ""), label_width - self._cell_padding_x * 2)

        c.rect(x, y_top - height, label_width, height, stroke=1, fill=0)
        self._draw_lines_in_box(
            c,
            label_lines,
            x=x,
            y=y_top - height,
            width=label_width,
            height=height,
            align="right",
            baseline_shift_down=self._table_text_shift_down,
        )

        if row.get("kind") == "summary_merged":
            merged_width = sum(self._column_widths[6:])
            c.rect(x + label_width, y_top - height, merged_width, height, stroke=1, fill=0)
            self._draw_lines_in_box(
                c,
                self._wrap_text(str(row.get("value", "") or ""), merged_width - self._cell_padding_x * 2),
                x=x + label_width,
                y=y_top - height,
                width=merged_width,
                height=height,
                align="right",
                baseline_shift_down=self._table_text_shift_down,
            )
            return y_top - height

        cursor_x = x + label_width
        for width, key in ((self._column_widths[6], "standby"), (self._column_widths[7], "alarm")):
            c.rect(cursor_x, y_top - height, width, height, stroke=1, fill=0)
            self._draw_lines_in_box(
                c,
                self._wrap_text(str(row.get(key, "") or ""), width - self._cell_padding_x * 2),
                x=cursor_x,
                y=y_top - height,
                width=width,
                height=height,
                align="right",
                baseline_shift_down=self._table_text_shift_down,
            )
            cursor_x += width
        return y_top - height

    def _draw_final_text(self, c: canvas.Canvas, *, x: float, y_top: float, width: float) -> float:
        text = str(self.calculation.get("final_text", "") or "")
        lines = self._wrap_paragraph(text, width, first_line_indent=self._paragraph_first_line_indent)
        cursor_y = y_top - self._text_baseline_offset
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        for index, line in enumerate(lines):
            line_x = x + (self._paragraph_first_line_indent if index == 0 else 0.0)
            c.drawString(line_x, cursor_y, line)
            cursor_y -= self._line_height
        return cursor_y

    def draw(self, c: canvas.Canvas):
        c.setPageSize((self.page_width, self.page_height))
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        c.setStrokeColor(DEFAULT_BORDER_COLOR)
        c.setLineWidth(DEFAULT_INNER_BORDER_THICKNESS_MM)

        self.draw_outer_border(c)
        self.draw_main_title_box(c, self.main_title_box_type)
        self.fill_main_title_box(c, self.main_title_box_type)

        content_left, content_right, content_top, _content_bottom = self._content_bounds()
        inner_left = content_left + self.INNER_FRAME_MARGIN
        inner_right = content_right - self.INNER_FRAME_MARGIN
        current_y = self._draw_page_title(c, x=content_left, y_top=content_top, width=content_right - content_left)

        if self.show_intro:
            for index, paragraph in enumerate(self.calculation.get("introductory_texts") or []):
                current_y = self._draw_paragraph(
                    c,
                    str(paragraph),
                    x=inner_left,
                    y_top=current_y,
                    width=inner_right - inner_left,
                    first_line_indent=self._paragraph_first_line_indent,
                )
                if index < len(self.calculation.get("introductory_texts") or []) - 1:
                    current_y -= self._paragraph_gap
            current_y -= self._section_gap

        current_y = self._draw_caption(c, x=inner_left, y_top=current_y)
        current_y = self._draw_table_header(c, x=inner_left, y_top=current_y)

        for row in self.page_rows:
            kind = row.get("kind")
            if kind == "category":
                current_y = self._draw_category_row(c, row, x=inner_left, y_top=current_y)
            else:
                current_y = self._draw_data_row(c, row, x=inner_left, y_top=current_y)

        if self.show_summary:
            for row in self.calculation.get("summary_rows") or []:
                current_y = self._draw_summary_row(c, row, x=inner_left, y_top=current_y)
            current_y -= self._summary_to_text_gap
            self._draw_final_text(c, x=inner_left, y_top=current_y, width=inner_right - inner_left)

        c.showPage()
