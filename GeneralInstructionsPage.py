from __future__ import annotations

from typing import Any

from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from Page import Page
from consts import (
    CENTER,
    DEFAULT_FONT_NAME,
    DEFAULT_FONT_SIZE,
    LEFT,
    MAIN_TITLE_BOX_DICT,
    PAGESIZE_A4,
)


class GeneralInstructionsPage(Page):
    """A4 portrait page renderer for the general instructions section."""

    INNER_MARGIN = 5.0 * mm
    HEADING_HEIGHT = 8.0 * mm
    HEADING_TOP_MARGIN = 4.0 * mm
    HEADING_GAP = 4.0 * mm
    LINE_HEIGHT = DEFAULT_FONT_SIZE * 1.18
    TEXT_BASELINE_OFFSET = DEFAULT_FONT_SIZE * 0.32
    PARAGRAPH_FIRST_LINE_INDENT = 10.0 * mm
    SECTION_SPACING = 4.0 * mm
    PARAGRAPH_SPACING = 2.0 * mm
    BULLET_ITEM_SPACING = 1.0 * mm
    BULLET_PREFIX = "- "
    BULLET_BASE_INDENT = 2.0 * mm

    def __init__(
        self,
        instructions: dict[str, Any] | None = None,
        *,
        page_lines: list[dict[str, Any]] | None = None,
        show_heading: bool = True,
        is_continuation: bool = False,
        local_sheet_number: int | None = None,
        local_total_sheets: int | None = None,
        page_format: tuple[float, float] = PAGESIZE_A4,
        main_title_box_type: str = "1",
        creds: dict[str, str] | None = None,
        page_number: int = 1,
    ):
        page_creds = dict(creds or {})
        local_title = str((instructions or {}).get("local_sheet_title") or "Общие указания")
        page_creds["Title of the Drawing"] = local_title
        if local_sheet_number is not None:
            page_creds["Sheet Number"] = str(local_sheet_number)
        if local_total_sheets is not None:
            page_creds["Total Sheets"] = str(local_total_sheets)
        super().__init__(
            page_format=page_format,
            main_title_box_type=main_title_box_type,
            creds=page_creds,
            page_number=page_number,
        )
        self.instructions = instructions or {}
        self.page_lines = list(page_lines or [])
        self.show_heading = show_heading
        self.is_continuation = is_continuation
        self._content_width = self._content_bounds()[1] - self._content_bounds()[0]
        self._bullet_prefix_width = pdfmetrics.stringWidth(self.BULLET_PREFIX, DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)

    @classmethod
    def paginate(
        cls,
        instructions: dict[str, Any] | None,
        *,
        page_format: tuple[float, float] = PAGESIZE_A4,
        creds: dict[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        first_probe = cls(
            instructions=instructions,
            page_lines=[],
            show_heading=True,
            is_continuation=False,
            page_format=page_format,
            main_title_box_type="1",
            creds=creds,
            page_number=1,
        )
        continuation_probe = cls(
            instructions=instructions,
            page_lines=[],
            show_heading=False,
            is_continuation=True,
            page_format=page_format,
            main_title_box_type="2",
            creds=creds,
            page_number=1,
        )
        flow_lines = first_probe._flatten_blocks()
        if not flow_lines:
            return [{"page_lines": [], "show_heading": True, "is_continuation": False, "main_title_box_type": "1"}]

        segments: list[dict[str, Any]] = []
        remaining = list(flow_lines)
        show_heading = True

        while remaining:
            probe = first_probe if show_heading else continuation_probe
            available_height = probe._available_height(show_heading=show_heading)
            page_lines: list[dict[str, Any]] = []

            while remaining:
                next_line = remaining[0]
                spacing_before = float(next_line.get("spacing_before", 0.0) or 0.0) if page_lines else 0.0
                required_height = spacing_before + probe.LINE_HEIGHT
                if page_lines and required_height > available_height:
                    break
                if not page_lines and probe.LINE_HEIGHT > available_height:
                    page_lines.append(remaining.pop(0))
                    available_height = 0.0
                    break
                page_lines.append(remaining.pop(0))
                available_height -= required_height

            segments.append(
                {
                    "page_lines": page_lines,
                    "show_heading": show_heading,
                    "is_continuation": not show_heading,
                    "main_title_box_type": "1" if show_heading else "2",
                }
            )
            show_heading = False

        return segments

    def _content_bounds(self) -> tuple[float, float, float, float]:
        title_box_height = MAIN_TITLE_BOX_DICT.get(self.main_title_box_type, MAIN_TITLE_BOX_DICT["1"])[1]
        content_left = self.borders_mm["left"] + self.INNER_MARGIN
        content_right = self.page_width - self.borders_mm["right"] - self.INNER_MARGIN
        content_top = self.page_height - self.borders_mm["top"] - self.INNER_MARGIN
        content_bottom = self.borders_mm["bottom"] + title_box_height + self.INNER_MARGIN
        return content_left, content_right, content_top, content_bottom

    def _available_height(self, *, show_heading: bool) -> float:
        _left, _right, content_top, content_bottom = self._content_bounds()
        available = content_top - content_bottom
        if show_heading:
            available -= self.HEADING_TOP_MARGIN + self.HEADING_HEIGHT + self.HEADING_GAP
        return max(0.0, available)

    def _wrap_text(self, text: str, width: float, *, bold: bool = False) -> list[str]:
        font_name = f"{DEFAULT_FONT_NAME} Bold" if bold else DEFAULT_FONT_NAME
        normalized_lines = str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        wrapped: list[str] = []
        for raw_line in normalized_lines:
            words = raw_line.split()
            if not words:
                wrapped.append("")
                continue
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

    def _wrap_paragraph(self, text: str) -> list[dict[str, Any]]:
        content_width = self._content_bounds()[1] - self._content_bounds()[0]
        words = str(text or "").split()
        if not words:
            return []

        lines: list[str] = []
        current = ""
        line_width = max(1.0, content_width - self.PARAGRAPH_FIRST_LINE_INDENT)
        first_line = True
        for word in words:
            candidate = f"{current} {word}".strip()
            if not current or pdfmetrics.stringWidth(candidate, DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE) <= line_width:
                current = candidate
                continue
            lines.append(current)
            current = word
            if first_line:
                line_width = content_width
                first_line = False
        lines.append(current or "")

        flattened: list[dict[str, Any]] = []
        for index, line in enumerate(lines):
            flattened.append(
                {
                    "text": line,
                    "align": LEFT,
                    "bold": False,
                    "text_indent": self.PARAGRAPH_FIRST_LINE_INDENT if index == 0 else 0.0,
                    "prefix": "",
                    "prefix_indent": 0.0,
                    "spacing_before": self.PARAGRAPH_SPACING if index == 0 else 0.0,
                }
            )
        return flattened

    def _wrap_bullet_item(self, text: str) -> list[dict[str, Any]]:
        content_width = self._content_bounds()[1] - self._content_bounds()[0]
        text_indent = self.BULLET_BASE_INDENT + self._bullet_prefix_width
        available_width = max(1.0, content_width - text_indent)
        wrapped_lines = self._wrap_text(text, available_width)
        flattened: list[dict[str, Any]] = []
        for index, line in enumerate(wrapped_lines):
            flattened.append(
                {
                    "text": line,
                    "align": LEFT,
                    "bold": False,
                    "text_indent": text_indent,
                    "prefix": self.BULLET_PREFIX if index == 0 else "",
                    "prefix_indent": self.BULLET_BASE_INDENT,
                    "spacing_before": self.BULLET_ITEM_SPACING if index == 0 else 0.0,
                }
            )
        return flattened

    def _flatten_blocks(self) -> list[dict[str, Any]]:
        flow_lines: list[dict[str, Any]] = []
        content_width = self._content_bounds()[1] - self._content_bounds()[0]
        for block in self.instructions.get("blocks") or []:
            kind = str(block.get("kind") or "")
            if kind == "section_heading":
                for index, line in enumerate(self._wrap_text(str(block.get("text") or ""), content_width, bold=True)):
                    flow_lines.append(
                        {
                            "text": line,
                            "align": LEFT,
                            "bold": True,
                            "text_indent": 0.0,
                            "prefix": "",
                            "prefix_indent": 0.0,
                            "spacing_before": self.SECTION_SPACING if index == 0 else 0.0,
                        }
                    )
            elif kind == "paragraph":
                flow_lines.extend(self._wrap_paragraph(str(block.get("text") or "")))
            elif kind == "bullet_list":
                for item in block.get("items") or []:
                    flow_lines.extend(self._wrap_bullet_item(str(item or "")))
        while flow_lines and float(flow_lines[0].get("spacing_before", 0.0) or 0.0) > 0:
            flow_lines[0]["spacing_before"] = 0.0
        return flow_lines

    def _draw_heading(self, c: canvas.Canvas, *, content_left: float, content_right: float, cursor_y: float) -> float:
        heading = str(self.instructions.get("heading") or "ОБЩИЕ УКАЗАНИЯ.")
        c.setFont(f"{DEFAULT_FONT_NAME} Bold", DEFAULT_FONT_SIZE)
        c.drawCentredString(
            content_left + (content_right - content_left) / 2,
            cursor_y - self.TEXT_BASELINE_OFFSET,
            heading,
        )
        return cursor_y - self.HEADING_HEIGHT - self.HEADING_GAP

    def _draw_line(self, c: canvas.Canvas, line: dict[str, Any], *, content_left: float, cursor_y: float) -> None:
        font_name = f"{DEFAULT_FONT_NAME} Bold" if bool(line.get("bold")) else DEFAULT_FONT_NAME
        c.setFont(font_name, DEFAULT_FONT_SIZE)
        baseline_y = cursor_y - self.TEXT_BASELINE_OFFSET
        if line.get("align") == CENTER:
            c.drawCentredString(content_left + self._content_width / 2, baseline_y, str(line.get("text") or ""))
            return
        prefix = str(line.get("prefix") or "")
        prefix_indent = float(line.get("prefix_indent", 0.0) or 0.0)
        text_indent = float(line.get("text_indent", 0.0) or 0.0)
        if prefix:
            c.drawString(content_left + prefix_indent, baseline_y, prefix)
        c.drawString(content_left + text_indent, baseline_y, str(line.get("text") or ""))

    def draw(self, c: canvas.Canvas):
        c.setPageSize((self.page_width, self.page_height))
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        self.draw_outer_border(c)
        self.draw_main_title_box(c, self.main_title_box_type)
        self.fill_main_title_box(c, self.main_title_box_type)

        content_left, content_right, content_top, _content_bottom = self._content_bounds()
        cursor_y = content_top
        if self.show_heading:
            cursor_y -= self.HEADING_TOP_MARGIN
            cursor_y = self._draw_heading(c, content_left=content_left, content_right=content_right, cursor_y=cursor_y)

        for index, line in enumerate(self.page_lines):
            if index > 0 and float(line.get("spacing_before", 0.0) or 0.0) > 0:
                cursor_y -= float(line.get("spacing_before", 0.0) or 0.0)
            self._draw_line(c, line, content_left=content_left, cursor_y=cursor_y)
            cursor_y -= self.LINE_HEIGHT

        c.showPage()
