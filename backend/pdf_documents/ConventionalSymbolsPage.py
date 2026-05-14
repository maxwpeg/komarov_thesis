from __future__ import annotations

from typing import Any

from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from .DrawingPage import (
    draw_fire_alarm_symbol,
    draw_signal_instrument_symbol,
    draw_soue_device_symbol,
)
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


class ConventionalSymbolsPage(Page):
    """A4 portrait page with the conventional symbols table."""

    INNER_FRAME_MARGIN = 5.0 * mm
    PAGE_TITLE_TOP_MARGIN = 6.0 * mm
    PAGE_TITLE_HEIGHT = 8.0 * mm
    PAGE_TITLE_GAP = 4.0 * mm
    TABLE_HEADER_HEIGHT = 16.0 * mm
    MIN_DATA_ROW_HEIGHT = 14.0 * mm
    CELL_PADDING_X = 1.2 * mm
    CELL_PADDING_Y = 1.0 * mm
    LINE_HEIGHT = DEFAULT_FONT_SIZE * 1.15
    TEXT_BASELINE_OFFSET = DEFAULT_FONT_SIZE * 0.35
    TABLE_TEXT_SHIFT_DOWN = 0.7 * mm
    TABLE_TO_DECODE_GAP = 4.0 * mm
    DECODE_ITEM_GAP = 1.2 * mm
    COLUMN_WIDTHS_MM = (56.0, 38.0, 86.0)

    def __init__(
        self,
        conventional_symbols: dict[str, Any] | None = None,
        *,
        page_rows: list[dict[str, Any]] | None = None,
        show_decode: bool = False,
        is_continuation: bool = False,
        page_format: tuple[float, float] = PAGESIZE_A4,
        main_title_box_type: str = "1",
        creds: dict[str, str] | None = None,
        page_number: int = 1,
    ):
        page_creds = dict(creds or {})
        page_creds["Title of the Drawing"] = str(
            (conventional_symbols or {}).get("page_title") or "Условные графические обозначения"
        )
        super().__init__(
            page_format=page_format,
            main_title_box_type=main_title_box_type,
            creds=page_creds,
            page_number=page_number,
        )
        self.conventional_symbols = conventional_symbols or {}
        self.page_rows = list(page_rows or [])
        self.show_decode = show_decode
        self.is_continuation = is_continuation
        raw_widths = [width * mm for width in self.COLUMN_WIDTHS_MM]
        content_left, content_right, _content_top, _content_bottom = self._content_bounds()
        usable_width = (content_right - content_left) - (self.INNER_FRAME_MARGIN * 2)
        scale = usable_width / sum(raw_widths)
        self._column_widths = [width * scale for width in raw_widths]

    @classmethod
    def paginate(
        cls,
        conventional_symbols: dict[str, Any] | None,
        *,
        page_format: tuple[float, float] = PAGESIZE_A4,
        creds: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        first_probe = cls(
            conventional_symbols=conventional_symbols,
            page_rows=[],
            show_decode=False,
            is_continuation=False,
            page_format=page_format,
            main_title_box_type="1",
            creds=creds,
            page_number=1,
        )
        continuation_probe = cls(
            conventional_symbols=conventional_symbols,
            page_rows=[],
            show_decode=False,
            is_continuation=True,
            page_format=page_format,
            main_title_box_type="2",
            creds=creds,
            page_number=1,
        )

        rows = list((conventional_symbols or {}).get("rows") or [])
        segments: list[dict[str, Any]] = []
        remaining_rows = list(rows)
        is_first_page = True

        while remaining_rows:
            probe = first_probe if is_first_page else continuation_probe
            available_height = probe._table_available_height()
            page_rows: list[dict[str, Any]] = []

            while remaining_rows:
                next_row = remaining_rows[0]
                row_height = probe._measure_row_height(next_row)
                if page_rows and row_height > available_height:
                    break
                if not page_rows and row_height > available_height:
                    page_rows.append(remaining_rows.pop(0))
                    available_height = 0.0
                    break
                page_rows.append(remaining_rows.pop(0))
                available_height -= row_height

            segments.append(
                {
                    "page_rows": page_rows,
                    "show_decode": False,
                    "is_continuation": not is_first_page,
                    "main_title_box_type": "1" if is_first_page else "2",
                }
            )
            is_first_page = False

        if not segments:
            segments.append(
                {
                    "page_rows": [],
                    "show_decode": False,
                    "is_continuation": False,
                    "main_title_box_type": "1",
                }
            )

        last_probe = first_probe if segments[-1]["main_title_box_type"] == "1" else continuation_probe
        remaining_height = last_probe._table_available_height()
        remaining_height -= sum(last_probe._measure_row_height(row) for row in segments[-1]["page_rows"])
        decode_height = last_probe._measure_decode_block_height()
        if decode_height <= remaining_height:
            segments[-1]["show_decode"] = True
        else:
            segments.append(
                {
                    "page_rows": [],
                    "show_decode": True,
                    "is_continuation": True,
                    "main_title_box_type": "2",
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
        total_height = len(lines) * self.LINE_HEIGHT
        cursor_y = (
            y
            + height
            - self.CELL_PADDING_Y
            - (height - total_height) / 2
            - self.TEXT_BASELINE_OFFSET
            - baseline_shift_down
        )
        c.setFont(font_name, DEFAULT_FONT_SIZE)
        for line in lines:
            if align == CENTER:
                c.drawCentredString(x + width / 2, cursor_y, line)
            else:
                c.drawString(x + self.CELL_PADDING_X, cursor_y, line)
            cursor_y -= self.LINE_HEIGHT

    def _measure_row_height(self, row: dict[str, Any]) -> float:
        designation_lines = self._wrap_text(
            str(row.get("designation", "")),
            self._column_widths[0] - self.CELL_PADDING_X * 2,
        )
        name_lines = self._wrap_text(
            str(row.get("name", "")),
            self._column_widths[2] - self.CELL_PADDING_X * 2,
        )
        text_height = max(len(designation_lines), len(name_lines)) * self.LINE_HEIGHT + self.CELL_PADDING_Y * 2
        return max(self.MIN_DATA_ROW_HEIGHT, text_height)

    def _measure_decode_block_height(self) -> float:
        decode_lines = list(self.conventional_symbols.get("decode_lines") or [])
        if not decode_lines:
            return 0.0
        content_left, content_right, _content_top, _content_bottom = self._content_bounds()
        width = (content_right - content_left) - (self.INNER_FRAME_MARGIN * 2)
        total_height = self.TABLE_TO_DECODE_GAP
        for index, line in enumerate(decode_lines):
            wrapped = self._wrap_text(line, width)
            total_height += len(wrapped) * self.LINE_HEIGHT
            if index < len(decode_lines) - 1:
                total_height += self.DECODE_ITEM_GAP
        return total_height

    def _table_available_height(self) -> float:
        content_left, content_right, content_top, content_bottom = self._content_bounds()
        available_height = content_top - content_bottom
        available_height -= self.PAGE_TITLE_TOP_MARGIN + self.PAGE_TITLE_HEIGHT + self.PAGE_TITLE_GAP
        available_height -= self.TABLE_HEADER_HEIGHT
        return available_height

    def _draw_page_title(self, c: canvas.Canvas, *, x: float, y_top: float, width: float) -> float:
        c.setFont(f"{DEFAULT_FONT_NAME} Bold", DEFAULT_FONT_SIZE)
        title_y_top = y_top - self.PAGE_TITLE_TOP_MARGIN
        c.drawCentredString(
            x + width / 2,
            title_y_top - self.PAGE_TITLE_HEIGHT + self.TEXT_BASELINE_OFFSET + 1.0 * mm,
            str(self.conventional_symbols.get("heading") or "УСЛОВНЫЕ ГРАФИЧЕСКИЕ ОБОЗНАЧЕНИЯ"),
        )
        return title_y_top - self.PAGE_TITLE_HEIGHT - self.PAGE_TITLE_GAP

    def _draw_table_header(self, c: canvas.Canvas, *, x: float, y_top: float) -> float:
        headers = (
            "Условное обозначение\n(цифро-буквенное)",
            "Графическое\nобозначение",
            "Наименование",
        )
        current_x = x
        current_y = y_top
        c.setStrokeColor(DEFAULT_BORDER_COLOR)
        c.setLineWidth(DEFAULT_INNER_BORDER_THICKNESS_MM)
        for index, header in enumerate(headers):
            width = self._column_widths[index]
            c.rect(current_x, current_y - self.TABLE_HEADER_HEIGHT, width, self.TABLE_HEADER_HEIGHT, stroke=1, fill=0)
            self._draw_lines_in_box(
                c,
                self._wrap_text(header, width - self.CELL_PADDING_X * 2, font_name=f"{DEFAULT_FONT_NAME} Bold"),
                x=current_x,
                y=current_y - self.TABLE_HEADER_HEIGHT,
                width=width,
                height=self.TABLE_HEADER_HEIGHT,
                font_name=f"{DEFAULT_FONT_NAME} Bold",
                align=CENTER,
                baseline_shift_down=self.TABLE_TEXT_SHIFT_DOWN,
            )
            current_x += width
        return current_y - self.TABLE_HEADER_HEIGHT

    def _draw_symbol(self, c: canvas.Canvas, row: dict[str, Any], *, center_x: float, center_y: float) -> None:
        symbol_kind = str(row.get("symbol_kind") or "")
        symbol_type = str(row.get("symbol_type") or "")
        if symbol_kind == "instrument":
            draw_signal_instrument_symbol(c, center_x, center_y, symbol_type)
            return
        if symbol_kind == "fire_alarm":
            draw_fire_alarm_symbol(c, center_x, center_y, symbol_type)
            return
        if symbol_kind == "soue_device":
            draw_soue_device_symbol(c, center_x, center_y, symbol_type)

    def _draw_row(self, c: canvas.Canvas, row: dict[str, Any], *, x: float, y_top: float) -> float:
        height = self._measure_row_height(row)
        current_x = x
        c.setStrokeColor(DEFAULT_BORDER_COLOR)
        c.setLineWidth(DEFAULT_INNER_BORDER_THICKNESS_MM)

        for width in self._column_widths:
            c.rect(current_x, y_top - height, width, height, stroke=1, fill=0)
            current_x += width

        self._draw_lines_in_box(
            c,
            self._wrap_text(str(row.get("designation", "")), self._column_widths[0] - self.CELL_PADDING_X * 2),
            x=x,
            y=y_top - height,
            width=self._column_widths[0],
            height=height,
            align=CENTER,
            baseline_shift_down=self.TABLE_TEXT_SHIFT_DOWN,
        )

        symbol_x = x + self._column_widths[0]
        symbol_center_x = symbol_x + self._column_widths[1] / 2
        symbol_center_y = y_top - height / 2 - 0.5 * mm
        self._draw_symbol(c, row, center_x=symbol_center_x, center_y=symbol_center_y)

        name_x = x + self._column_widths[0] + self._column_widths[1]
        self._draw_lines_in_box(
            c,
            self._wrap_text(str(row.get("name", "")), self._column_widths[2] - self.CELL_PADDING_X * 2),
            x=name_x,
            y=y_top - height,
            width=self._column_widths[2],
            height=height,
            align=LEFT,
            baseline_shift_down=self.TABLE_TEXT_SHIFT_DOWN,
        )
        return y_top - height

    def _draw_decode_block(self, c: canvas.Canvas, *, x: float, y_top: float, width: float) -> float:
        decode_lines = list(self.conventional_symbols.get("decode_lines") or [])
        if not decode_lines:
            return y_top
        current_y = y_top - self.TABLE_TO_DECODE_GAP
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        for index, line in enumerate(decode_lines):
            wrapped = self._wrap_text(line, width)
            for wrapped_line in wrapped:
                c.drawString(x, current_y - self.TEXT_BASELINE_OFFSET, wrapped_line)
                current_y -= self.LINE_HEIGHT
            if index < len(decode_lines) - 1:
                current_y -= self.DECODE_ITEM_GAP
        return current_y

    def draw(self, c: canvas.Canvas):
        c.setPageSize((self.page_width, self.page_height))
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        self.draw_outer_border(c)
        self.draw_main_title_box(c, self.main_title_box_type)
        self.fill_main_title_box(c, self.main_title_box_type)

        content_left, content_right, content_top, _content_bottom = self._content_bounds()
        inner_left = content_left + self.INNER_FRAME_MARGIN
        inner_width = (content_right - content_left) - (self.INNER_FRAME_MARGIN * 2)
        current_y = self._draw_page_title(c, x=inner_left, y_top=content_top, width=inner_width)
        current_y = self._draw_table_header(c, x=inner_left, y_top=current_y)

        for row in self.page_rows:
            current_y = self._draw_row(c, row, x=inner_left, y_top=current_y)

        if self.show_decode:
            self._draw_decode_block(c, x=inner_left, y_top=current_y, width=inner_width)

        c.showPage()
