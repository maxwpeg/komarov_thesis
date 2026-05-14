from __future__ import annotations

from typing import Any

from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from Page import Page
from consts import (
    CENTER,
    DEFAULT_BORDER_COLOR,
    DEFAULT_FONT_NAME,
    DEFAULT_FONT_SIZE,
    DEFAULT_INNER_BORDER_THICKNESS_MM,
    LEFT,
    MAIN_TITLE_BOX_DICT,
    PAGESIZE_A3_LANDSCAPE,
)


DEFAULT_GENERAL_DATA_REFERENCE_DOCUMENTS: tuple[dict[str, str], ...] = (
    {
        "designation": "СП 76.13330.2016",
        "name": "Свод правил. Электротехнические устройства",
        "note": "",
    },
    {
        "designation": "СП 1.13130.2020",
        "name": "Свод правил. Системы противопожарной защиты. Эвакуационные пути и выходы.",
        "note": "",
    },
    {
        "designation": "СП 3.13130.2009",
        "name": "Свод правил. Системы противопожарной защиты. Система оповещения и управления эвакуацией людей при пожаре.",
        "note": "",
    },
    {
        "designation": "СП 486.1311500.2020",
        "name": (
            "Свод правил. Системы противопожарной защиты. Перечень зданий, сооружений, помещений и оборудования, "
            "подлежащих защите автоматическими установками пожаротушения и системами пожарной сигнализации. "
            "Требования пожарной безопасности. Свод правил. Системы противопожарной защиты."
        ),
        "note": "",
    },
    {
        "designation": "СП 6.13130.2021",
        "name": "Системы противопожарной защиты. Электрооборудование. Требования пожарной безопасности.",
        "note": "",
    },
    {
        "designation": "СП 484.1311500.2020",
        "name": "Системы пожарной сигнализации и автоматизации систем противопожарной защиты. Нормы и правила проектирования",
        "note": "",
    },
    {
        "designation": "СП 51.13330.2011",
        "name": "Свод правил. Защита от шума",
        "note": "",
    },
    {
        "designation": "ГОСТ 53325-2012",
        "name": "Техника пожарная. Технические средства пожарной автоматики. Общие технические требования и методы испытаний.",
        "note": "",
    },
    {
        "designation": "ГОСТ 31565-2012",
        "name": "Кабельные изделия. Требования пожарной безопасности.",
        "note": "",
    },
    {
        "designation": "РД 78.145-93",
        "name": (
            "Руководящий документ. Системы и комплексы охранной, пожарной, и охранно-пожарной сигнализации. "
            "Правила производства и приемки работ."
        ),
        "note": "",
    },
    {
        "designation": "ПУЭ, издание 7",
        "name": "Правила устройства электроустановок.",
        "note": "",
    },
    {
        "designation": "Постановление Правительства\nРФ от 6.09.2020 № 1479",
        "name": "Об утверждении Правил противопожарного режима в Российской Федерации».",
        "note": "",
    },
)

DEFAULT_GENERAL_DATA_STATEMENT = (
    "Технические решения, принятые в рабочих чертежах основного комплекта марки АТМ.АГСВ, соответствуют "
    "требованием экологических, санитарно-гигиенических, противопожарных и других норм, действующих на территории "
    "Российской Федерации, и обеспечивают безопасную для жизни и здоровья людей эксплуатацию объекта при соблюдении "
    "предусмотренных рабочими чертежами мероприятий"
)


class GeneralDataPage(Page):
    """A3 landscape page with general project data tables."""

    LEFT_TABLE_TITLE = "ВЕДОМОСТЬ ССЫЛОЧНЫХ И ПРИЛАГАЕМЫХ ДОКУМЕНТОВ"
    RIGHT_TABLE_TITLE = "ВЕДОМОСТЬ РАБОЧИХ ЧЕРТЕЖЕЙ ОСНОВНОГО КОМПЛЕКТА"
    LEFT_HEADERS = ("Обозначение", "Наименование", "Примечание")
    RIGHT_HEADERS = ("Лист", "Наименование", "Примечание")

    TABLE_SIDE_MARGIN = 5.0 * mm
    TABLE_GAP = 6.0 * mm
    TABLE_TITLE_HEIGHT = 10.0 * mm
    TABLE_TITLE_GAP = 2.0 * mm
    BASE_ROW_HEIGHT = 7.0 * mm
    HEADER_ROW_HEIGHT = 14.0 * mm
    CELL_PADDING_X = 1.1 * mm
    CELL_PADDING_Y = 0.8 * mm
    LINE_HEIGHT = DEFAULT_FONT_SIZE * 1.1
    TEXT_BASELINE_OFFSET = DEFAULT_FONT_SIZE * 0.35
    TABLE_TEXT_SHIFT_DOWN = 0.8 * mm
    PARAGRAPH_GAP = 20.0 * mm
    PARAGRAPH_FIRST_LINE_INDENT = 10.0 * mm
    SIGNATURE_TOP_GAP = 20.0 * mm
    SIGNATURE_LINE_HEIGHT = 9.0 * mm
    SIGNATURE_LABEL_FONT_SIZE = 8.0
    SIGNATURE_LABEL_GAP = 1.8 * mm

    def __init__(
        self,
        general_data: dict[str, Any] | None = None,
        *,
        page_format: tuple[float, float] = PAGESIZE_A3_LANDSCAPE,
        main_title_box_type: str = "1",
        creds: dict[str, str] | None = None,
        page_number: int = 1,
    ):
        page_creds = dict(creds or {})
        page_creds["Title of the Drawing"] = str((general_data or {}).get("page_title") or "Общие данные")
        super().__init__(
            page_format=page_format,
            main_title_box_type=main_title_box_type,
            creds=page_creds,
            page_number=page_number,
        )
        self.general_data = general_data or {}

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

    def _wrap_text(self, text: str, width: float, *, font_name: str = DEFAULT_FONT_NAME, font_size: float = DEFAULT_FONT_SIZE) -> list[str]:
        width = max(1.0, float(width))
        wrapped: list[str] = []
        for raw_line in self._split_lines(text):
            words = raw_line.split()
            if not words:
                wrapped.append("")
                continue
            current = ""
            for word in words:
                candidate = f"{current} {word}".strip()
                if not current or pdfmetrics.stringWidth(candidate, font_name, font_size) <= width:
                    current = candidate
                    continue
                wrapped.append(current)
                current = word
            wrapped.append(current or "")
        return wrapped or [""]

    def _wrap_paragraph(self, text: str, width: float, *, first_line_indent: float = 0.0) -> list[str]:
        width = max(1.0, float(width))
        words = str(text or "").split()
        if not words:
            return [""]

        lines: list[str] = []
        current = ""
        current_width = max(1.0, width - first_line_indent)
        is_first_line = True

        for word in words:
            candidate = f"{current} {word}".strip()
            if not current or pdfmetrics.stringWidth(candidate, DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE) <= current_width:
                current = candidate
                continue
            lines.append(current)
            current = word
            if is_first_line:
                current_width = width
                is_first_line = False
        lines.append(current or "")
        return lines

    def _measure_text_width(self, text: str, *, font_name: str = DEFAULT_FONT_NAME, font_size: float = DEFAULT_FONT_SIZE) -> float:
        return max(
            (pdfmetrics.stringWidth(line or " ", font_name, font_size) for line in self._split_lines(text)),
            default=0.0,
        )

    def _compute_column_widths(
        self,
        rows: list[dict[str, Any]],
        headers: tuple[str, ...],
        total_width: float,
        *,
        min_widths: tuple[float, ...],
        primary_flex_index: int,
    ) -> list[float]:
        natural_widths = list(min_widths)
        for index, header in enumerate(headers):
            natural_widths[index] = max(
                natural_widths[index],
                self._measure_text_width(header, font_name=f"{DEFAULT_FONT_NAME} Bold") + self.CELL_PADDING_X * 2,
            )

        for row in rows:
            for index, cell in enumerate(row.get("cells") or []):
                natural_widths[index] = max(
                    natural_widths[index],
                    self._measure_text_width(cell) + self.CELL_PADDING_X * 2,
                )

        natural_total = sum(natural_widths)
        widths = list(natural_widths)
        if natural_total <= total_width:
            widths[primary_flex_index] += total_width - natural_total
            return widths

        overflow = natural_total - total_width
        primary_reducible = max(0.0, widths[primary_flex_index] - min_widths[primary_flex_index])
        primary_take = min(primary_reducible, overflow)
        widths[primary_flex_index] -= primary_take
        overflow -= primary_take

        if overflow > 0:
            shrinkable = [max(0.0, width - minimum) for width, minimum in zip(widths, min_widths)]
            shrinkable_total = sum(shrinkable)
            if shrinkable_total > 0:
                widths = [
                    max(minimum, width - overflow * (reducible / shrinkable_total))
                    for width, minimum, reducible in zip(widths, min_widths, shrinkable)
                ]

        correction = total_width - sum(widths)
        widths[-1] += correction
        return widths

    def _explode_row(self, row: dict[str, Any], widths: list[float]) -> list[dict[str, Any]]:
        kind = row.get("kind", "data")
        if kind == "category":
            return [
                {
                    "kind": "category",
                    "cells": list(row.get("cells") or []),
                    "underline_columns": set(row.get("underline_columns") or []),
                }
            ]

        lines_per_row = 2 if kind == "header" else 1
        wrapped_cells: list[list[str]] = []
        max_lines = 1
        font_name = f"{DEFAULT_FONT_NAME} Bold" if kind == "header" else DEFAULT_FONT_NAME
        for index, cell in enumerate(row.get("cells") or []):
            lines = self._wrap_text(
                str(cell or ""),
                widths[index] - self.CELL_PADDING_X * 2,
                font_name=font_name,
            )
            wrapped_cells.append(lines)
            max_lines = max(max_lines, len(lines))

        exploded_rows: list[dict[str, Any]] = []
        for start in range(0, max_lines, lines_per_row):
            exploded_rows.append(
                {
                    "kind": kind,
                    "cells": ["\n".join(lines[start : start + lines_per_row]) for lines in wrapped_cells],
                    "underline_columns": set(row.get("underline_columns") or []),
                    "is_continuation": start > 0,
                }
            )
        return exploded_rows

    def _build_left_table_logical_rows(self) -> list[dict[str, Any]]:
        reference_category_title = str(self.general_data.get("reference_category_title") or "Ссылочные документы")
        attached_category_title = str(self.general_data.get("attached_category_title") or "Прилагаемые документы")
        rows: list[dict[str, Any]] = [
            {
                "kind": "header",
                "cells": list(self.LEFT_HEADERS),
            },
            {
                "kind": "category",
                "cells": ["", reference_category_title, ""],
                "underline_columns": {1},
            },
        ]
        for document in self.general_data.get("reference_documents") or []:
            rows.append(
                {
                    "kind": "data",
                    "cells": [
                        str(document.get("designation") or ""),
                        str(document.get("name") or ""),
                        str(document.get("note") or ""),
                    ],
                }
            )
        rows.append(
            {
                "kind": "category",
                "cells": ["", attached_category_title, ""],
                "underline_columns": {1},
            }
        )
        for document in self.general_data.get("attached_documents") or []:
            rows.append(
                {
                    "kind": "data",
                    "cells": [
                        str(document.get("designation") or ""),
                        str(document.get("name") or ""),
                        str(document.get("note") or ""),
                    ],
                }
            )
        return rows

    def _build_right_table_logical_rows(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = [
            {
                "kind": "header",
                "cells": list(self.RIGHT_HEADERS),
            }
        ]
        for index, row in enumerate(self.general_data.get("drawing_manifest_rows") or [], start=1):
            rows.append(
                {
                    "kind": "data",
                    "cells": [
                        str(index),
                        str(row.get("name") or ""),
                        str(row.get("note") or ""),
                    ],
                }
            )
        return rows

    def _prepare_left_table(self, block_width: float) -> dict[str, Any]:
        logical_rows = self._build_left_table_logical_rows()
        widths = self._compute_column_widths(
            logical_rows,
            self.LEFT_HEADERS,
            block_width,
            min_widths=(24.0 * mm, 96.0 * mm, 14.0 * mm),
            primary_flex_index=1,
        )
        designation_cap = 46.0 * mm
        if widths[0] > designation_cap:
            widths[1] += widths[0] - designation_cap
            widths[0] = designation_cap
        rows: list[dict[str, Any]] = []
        for row in logical_rows:
            rows.extend(self._explode_row(row, widths))
        return {
            "table_key": "left",
            "title": str(self.general_data.get("left_table_title") or self.LEFT_TABLE_TITLE),
            "widths": widths,
            "rows": rows,
        }

    def _prepare_right_table(self, block_width: float) -> dict[str, Any]:
        logical_rows = self._build_right_table_logical_rows()
        widths = self._compute_column_widths(
            logical_rows,
            self.RIGHT_HEADERS,
            block_width,
            min_widths=(14.0 * mm, 95.0 * mm, 26.0 * mm),
            primary_flex_index=1,
        )
        rows: list[dict[str, Any]] = []
        for row in logical_rows:
            rows.extend(self._explode_row(row, widths))
        return {
            "table_key": "right",
            "title": str(self.general_data.get("right_table_title") or self.RIGHT_TABLE_TITLE),
            "widths": widths,
            "rows": rows,
        }

    def _row_height(self, row: dict[str, Any]) -> float:
        return self.HEADER_ROW_HEIGHT if row.get("kind") == "header" else self.BASE_ROW_HEIGHT

    def _table_height(self, rows: list[dict[str, Any]]) -> float:
        return sum(self._row_height(row) for row in rows)

    def _draw_cell_text(
        self,
        c: canvas.Canvas,
        text: str,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        align: str = LEFT,
        font_name: str = DEFAULT_FONT_NAME,
        font_size: float = DEFAULT_FONT_SIZE,
        underline: bool = False,
    ) -> None:
        lines = self._split_lines(text)
        total_text_height = len(lines) * self.LINE_HEIGHT
        cursor_y = (
            y
            + height
            - self.CELL_PADDING_Y
            - (height - total_text_height) / 2
            - self.TEXT_BASELINE_OFFSET
            - self.TABLE_TEXT_SHIFT_DOWN
        )
        c.setFont(font_name, font_size)
        for line in lines:
            text_width = pdfmetrics.stringWidth(line or " ", font_name, font_size)
            if align == CENTER:
                text_x = x + width / 2
                c.drawCentredString(text_x, cursor_y, line)
                line_start = text_x - text_width / 2
                line_end = text_x + text_width / 2
            else:
                text_x = x + self.CELL_PADDING_X
                c.drawString(text_x, cursor_y, line)
                line_start = text_x
                line_end = text_x + text_width

            if underline and line.strip():
                underline_end = min(x + width - self.CELL_PADDING_X, line_end)
                c.line(line_start, cursor_y - 0.9 * mm, underline_end, cursor_y - 0.9 * mm)
            cursor_y -= self.LINE_HEIGHT

    def _resolve_cell_alignment(self, table_key: str, row: dict[str, Any], column_index: int) -> str:
        row_kind = row.get("kind")
        if row_kind == "header":
            return CENTER
        if row_kind == "category":
            return CENTER
        if table_key == "right" and column_index == 0:
            return CENTER
        return LEFT

    def _draw_table(self, c: canvas.Canvas, table: dict[str, Any], *, x: float, top_y: float, width: float) -> float:
        self.fit_text_in_box(
            c,
            table["title"],
            x,
            top_y - self.TABLE_TITLE_HEIGHT,
            width,
            self.TABLE_TITLE_HEIGHT,
            CENTER,
            font_size=DEFAULT_FONT_SIZE,
            bold=True,
        )
        current_y = top_y - self.TABLE_TITLE_HEIGHT - self.TABLE_TITLE_GAP
        c.setStrokeColor(DEFAULT_BORDER_COLOR)
        c.setLineWidth(DEFAULT_INNER_BORDER_THICKNESS_MM)

        for row in table["rows"]:
            row_height = self._row_height(row)
            current_y -= row_height
            cursor_x = x
            for index, column_width in enumerate(table["widths"]):
                c.rect(cursor_x, current_y, column_width, row_height, stroke=1, fill=0)
                cell_text = row["cells"][index] if index < len(row["cells"]) else ""
                if row.get("kind") == "header":
                    font_name = f"{DEFAULT_FONT_NAME} Bold"
                else:
                    font_name = DEFAULT_FONT_NAME
                self._draw_cell_text(
                    c,
                    cell_text,
                    x=cursor_x,
                    y=current_y,
                    width=column_width,
                    height=row_height,
                    align=self._resolve_cell_alignment(str(table.get("table_key") or ""), row, index),
                    font_name=font_name,
                    underline=index in set(row.get("underline_columns") or []),
                )
                cursor_x += column_width
        return current_y

    def _measure_statement_height(self, width: float) -> float:
        lines = self._wrap_paragraph(
            str(self.general_data.get("statement_text") or ""),
            width,
            first_line_indent=self.PARAGRAPH_FIRST_LINE_INDENT,
        )
        return len(lines) * self.LINE_HEIGHT

    def _draw_statement(self, c: canvas.Canvas, *, x: float, top_y: float, width: float) -> float:
        lines = self._wrap_paragraph(
            str(self.general_data.get("statement_text") or ""),
            width,
            first_line_indent=self.PARAGRAPH_FIRST_LINE_INDENT,
        )
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        cursor_y = top_y - self.TEXT_BASELINE_OFFSET
        for index, line in enumerate(lines):
            indent = self.PARAGRAPH_FIRST_LINE_INDENT if index == 0 else 0.0
            c.drawString(x + indent, cursor_y, line)
            cursor_y -= self.LINE_HEIGHT
        return cursor_y

    def _draw_signature_block(self, c: canvas.Canvas, *, x: float, top_y: float, width: float) -> None:
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        label = "ГИП проекта"
        label_width = pdfmetrics.stringWidth(label, DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        cursor_x = x
        baseline_y = top_y - self.TEXT_BASELINE_OFFSET

        c.drawString(cursor_x, baseline_y, label)
        cursor_x += label_width + 4.0 * mm

        signature_width = min(42.0 * mm, max(30.0 * mm, width * 0.23))
        date_width = min(24.0 * mm, max(18.0 * mm, width * 0.13))
        name_width = max(50.0 * mm, width - (cursor_x - x) - signature_width - date_width - 10.0 * mm)
        if cursor_x + signature_width + date_width + name_width > x + width:
            name_width = max(42.0 * mm, x + width - cursor_x - signature_width - date_width - 6.0 * mm)

        signature_x = cursor_x
        date_x = signature_x + signature_width + 4.0 * mm
        name_x = date_x + date_width + 4.0 * mm

        c.line(signature_x, top_y, signature_x + signature_width, top_y)
        c.line(date_x, top_y, date_x + date_width, top_y)
        name_end_x = min(x + width, name_x + name_width)
        c.line(name_x, top_y, name_end_x, top_y)

        gip_name = str(self.general_data.get("gip_name") or "")
        if gip_name:
            self.fit_text_in_box(
                c,
                gip_name,
                name_x,
                top_y + 1.0 * mm,
                name_end_x - name_x,
                self.SIGNATURE_LINE_HEIGHT - 1.0 * mm,
                CENTER,
                font_size=DEFAULT_FONT_SIZE,
            )

        labels_y = top_y - self.SIGNATURE_LABEL_GAP - self.SIGNATURE_LABEL_FONT_SIZE
        c.setFont(DEFAULT_FONT_NAME, self.SIGNATURE_LABEL_FONT_SIZE)
        c.drawCentredString(signature_x + signature_width / 2, labels_y, "Подпись")
        c.drawCentredString(date_x + date_width / 2, labels_y, "Дата")
        c.drawCentredString(name_x + (name_end_x - name_x) / 2, labels_y, "Фамилия И.О.")

    def draw(self, c: canvas.Canvas):
        c.setPageSize((self.page_width, self.page_height))
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        self.draw_outer_border(c)
        self.draw_main_title_box(c, self.main_title_box_type)
        self.fill_main_title_box(c, self.main_title_box_type)

        content_left, content_right, content_top, _content_bottom = self._content_bounds()
        usable_width = content_right - content_left - self.TABLE_SIDE_MARGIN * 2 - self.TABLE_GAP
        block_width = usable_width / 2
        left_x = content_left + self.TABLE_SIDE_MARGIN
        right_x = left_x + block_width + self.TABLE_GAP

        left_table = self._prepare_left_table(block_width)
        right_table = self._prepare_right_table(block_width)

        self._draw_table(c, left_table, x=left_x, top_y=content_top, width=block_width)
        right_table_bottom = self._draw_table(c, right_table, x=right_x, top_y=content_top, width=block_width)

        statement_top = right_table_bottom - self.PARAGRAPH_GAP
        statement_bottom = self._draw_statement(c, x=right_x, top_y=statement_top, width=block_width)

        signature_top = statement_bottom - self.SIGNATURE_TOP_GAP
        self._draw_signature_block(c, x=right_x, top_y=signature_top, width=block_width)

        c.showPage()
