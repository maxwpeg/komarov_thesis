from __future__ import annotations

import math
from typing import Any

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfgen import canvas

from .DrawingPage import draw_fire_alarm_symbol, draw_signal_instrument_symbol, draw_soue_device_symbol
from .Page import Page
from .consts import (
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


SPS_COLOR = colors.red
SOUE_COLOR = colors.blue
NETWORK_COLOR = colors.green
LIGHT_GRAY = colors.Color(0.94, 0.94, 0.94)


class StructuralSchemePage(Page):
    """A3 sheet with the project-level SPS and SOUE structural scheme."""

    HEADING_FONT_SIZE = 15
    SECTION_FONT_SIZE = 10
    BODY_FONT_SIZE = 8
    SMALL_FONT_SIZE = 6.5
    CARD_HEADER_HEIGHT = 8.0 * mm
    CARD_PADDING = 2.0 * mm

    def __init__(
        self,
        structural_scheme: dict[str, Any] | None = None,
        page_format: tuple[float, float] = PAGESIZE_A3_LANDSCAPE,
        main_title_box_type: str = "1",
        creds: dict[str, str] | None = None,
        page_number: int = 1,
    ):
        self.structural_scheme = structural_scheme or {}
        page_creds = dict(creds or {})
        page_creds["Title of the Drawing"] = str(
            self.structural_scheme.get("page_title") or "Структурная схема СПС и СОУЭ"
        )
        super().__init__(
            page_format=page_format,
            main_title_box_type=main_title_box_type,
            creds=page_creds,
            page_number=page_number,
        )

    def _content_bounds(self) -> tuple[float, float, float, float]:
        title_box_height = MAIN_TITLE_BOX_DICT.get(self.main_title_box_type, MAIN_TITLE_BOX_DICT["1"])[1]
        content_left = self.borders_mm["left"]
        content_right = self.page_width - self.borders_mm["right"]
        content_top = self.page_height - self.borders_mm["top"]
        content_bottom = self.borders_mm["bottom"] + title_box_height
        return content_left, content_right, content_top, content_bottom

    def _string(self, value: Any, default: str = "") -> str:
        text = str(value or "").strip()
        return text or default

    def _wrap_text(self, text: Any, width: float, font_size: float, *, font_name: str = DEFAULT_FONT_NAME) -> list[str]:
        normalized = self._string(text)
        if not normalized:
            return [""]
        words = normalized.replace("\r\n", "\n").replace("\r", "\n").split()
        if not words:
            return [""]
        lines: list[str] = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if not current or pdfmetrics.stringWidth(candidate, font_name, font_size) <= width:
                current = candidate
                continue
            if current:
                lines.append(current)
            current = word
        if current:
            lines.append(current)
        return lines or [normalized]

    def _draw_wrapped_text(
        self,
        c: canvas.Canvas,
        text: Any,
        *,
        x: float,
        y: float,
        width: float,
        font_size: float,
        max_lines: int = 2,
        color: colors.Color = colors.black,
        font_name: str = DEFAULT_FONT_NAME,
    ) -> float:
        lines = self._wrap_text(text, width, font_size, font_name=font_name)
        if max_lines > 0 and len(lines) > max_lines:
            lines = lines[:max_lines]
            lines[-1] = f"{lines[-1].rstrip()}..."
        c.setFont(font_name, font_size)
        c.setFillColor(color)
        line_height = font_size * 1.15
        cursor_y = y
        for line in lines:
            c.drawString(x, cursor_y, line)
            cursor_y -= line_height
        return cursor_y

    def _draw_heading(self, c: canvas.Canvas, *, x: float, y: float, width: float) -> float:
        page_title = self._string(self.structural_scheme.get("page_title"), "Структурная схема СПС и СОУЭ")
        facility = self._string(self.structural_scheme.get("facility"))
        subtitle = facility

        c.setFillColor(colors.black)
        c.setFont(f"{DEFAULT_FONT_NAME} Bold", self.HEADING_FONT_SIZE)
        c.drawCentredString(x + width / 2, y, page_title.upper())
        if subtitle:
            c.setFont(DEFAULT_FONT_NAME, self.SECTION_FONT_SIZE)
            c.drawCentredString(x + width / 2, y - 7 * mm, subtitle)
            return y - 14 * mm
        return y - 9 * mm

    def _draw_header_box(
        self,
        c: canvas.Canvas,
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        text: str,
    ) -> None:
        c.setStrokeColor(DEFAULT_BORDER_COLOR)
        c.setFillColor(colors.white)
        c.setLineWidth(DEFAULT_INNER_BORDER_THICKNESS_MM)
        c.rect(x, y, width, height, stroke=1, fill=1)
        c.setFillColor(colors.black)
        c.setFont(f"{DEFAULT_FONT_NAME} Bold", self.SECTION_FONT_SIZE)
        self.fit_text_in_box(c, text, x, y, width, height, CENTER, font_size=self.SECTION_FONT_SIZE)

    def _draw_device_line(
        self,
        c: canvas.Canvas,
        *,
        x: float,
        y: float,
        width: float,
        item: dict[str, Any],
        subsystem: str,
        index: int,
        font_size: float,
    ) -> None:
        device_type = str(item.get("device_type") or item.get("category") or "").strip()
        symbol_x = x + 3.0 * mm
        symbol_y = y + 1.0 * mm
        if subsystem == "soue":
            draw_soue_device_symbol(c, symbol_x, symbol_y, device_type if device_type in {"siren", "exit_sign"} else "exit_sign", size=4.0 * mm)
            color = SOUE_COLOR
        else:
            symbol_type = "manual_call_point" if device_type in {"manual", "manual_call_point"} else "smoke_detector"
            draw_fire_alarm_symbol(c, symbol_x, symbol_y, symbol_type, size=4.0 * mm)
            color = SPS_COLOR

        quantity = int(item.get("quantity") or 0)
        label = self._string(item.get("label") or item.get("technical_name") or item.get("name"), "Оборудование")
        text = f"{label} - {quantity} шт."
        text_x = x + 7.0 * mm
        c.setFillColor(color)
        c.setFont(DEFAULT_FONT_NAME, font_size)
        self._draw_wrapped_text(c, text, x=text_x, y=y - 1.0 * mm, width=width - 8.0 * mm, font_size=font_size, max_lines=1, color=color)
        if index > 0:
            c.setStrokeColor(color)
            c.setLineWidth(0.6)
            c.line(x + 2.0 * mm, y + 3.0 * mm, x + width - 2.0 * mm, y + 3.0 * mm)

    def _device_quantity(self, item: dict[str, Any]) -> int:
        try:
            return max(0, int(item.get("quantity") or 0))
        except (TypeError, ValueError):
            return 0

    def _device_label(self, item: dict[str, Any]) -> str:
        return self._string(item.get("label") or item.get("technical_name") or item.get("name"), "Equipment")

    def _group_item_pairs(self, group: dict[str, Any]) -> list[tuple[dict[str, Any], str]]:
        pairs = [(item, "sps") for item in (group.get("sps_items") or [])]
        pairs.extend((item, "soue") for item in (group.get("soue_items") or []))
        return pairs

    def _expand_group_devices(self, group: dict[str, Any]) -> list[dict[str, Any]]:
        devices: list[dict[str, Any]] = []
        for item, subsystem in self._group_item_pairs(group):
            quantity = self._device_quantity(item)
            device_ids = list(item.get("device_ids") or [])
            for index in range(quantity):
                device_id = None
                if index < len(device_ids):
                    try:
                        device_id = int(device_ids[index])
                    except (TypeError, ValueError):
                        device_id = None
                devices.append(
                    {
                        "item": item,
                        "subsystem": subsystem,
                        "device_id": device_id,
                        "index": index + 1,
                        "quantity": quantity,
                    }
                )
        return devices

    def _draw_group_device_symbol(
        self,
        c: canvas.Canvas,
        *,
        x: float,
        y: float,
        device: dict[str, Any],
        size: float,
    ) -> tuple[colors.Color, float, float]:
        item = device["item"]
        subsystem = device["subsystem"]
        device_type = str(item.get("device_type") or item.get("category") or "").strip()
        if subsystem == "soue":
            symbol_type = "siren" if device_type == "siren" else "exit_sign"
            half_width, half_height = draw_soue_device_symbol(c, x, y, symbol_type, size=size)
            return SOUE_COLOR, half_width, half_height

        symbol_type = "manual_call_point" if device_type in {"manual", "manual_call_point"} else "smoke_detector"
        draw_fire_alarm_symbol(c, x, y, symbol_type, size=size)
        return SPS_COLOR, size / 2.0, size / 2.0

    def _draw_group_devices(
        self,
        c: canvas.Canvas,
        group: dict[str, Any],
        *,
        x: float,
        y: float,
        width: float,
        height: float,
        cursor_y: float,
    ) -> dict[str, Any]:
        connectors: dict[str, Any] = {"sps": [], "soue": [], "all": [], "by_id": {}, "route_ports": {}}
        item_pairs = self._group_item_pairs(group)
        summary_parts = [
            f"{self._device_label(item)} - {self._device_quantity(item)} \u0448\u0442."
            for item, _subsystem in item_pairs
            if self._device_quantity(item) > 0
        ]
        if summary_parts:
            summary = "; ".join(summary_parts[:3])
            if len(summary_parts) > 3:
                summary = f"{summary}; +{len(summary_parts) - 3}"
            cursor_y = self._draw_wrapped_text(
                c,
                summary,
                x=x + self.CARD_PADDING,
                y=cursor_y,
                width=width - 2 * self.CARD_PADDING,
                font_size=self.SMALL_FONT_SIZE,
                max_lines=2,
            )
            cursor_y -= 1.0 * mm

        devices = self._expand_group_devices(group)
        if not devices:
            c.setFillColor(colors.black)
            c.setFont(DEFAULT_FONT_NAME, self.SMALL_FONT_SIZE)
            c.drawCentredString(x + width / 2, y + height / 2 - 2.0 * mm, "РѕР±РѕСЂСѓРґРѕРІР°РЅРёРµ РЅРµ СЂР°Р·РјРµС‰РµРЅРѕ")
            fallback = (x + width, y + height / 2)
            connectors["all"].append(fallback)
            return connectors

        symbol_left = x + self.CARD_PADDING
        symbol_bottom = y + 5.0 * mm
        symbol_top = cursor_y - 1.0 * mm
        usable_w = max(6.0 * mm, width - 2 * self.CARD_PADDING)
        usable_h = max(5.0 * mm, symbol_top - symbol_bottom)
        max_cols = max(1, min(10, int(usable_w // (6.0 * mm)) or 1))
        max_rows = max(1, int(usable_h // (7.0 * mm)) or 1)
        capacity = max(1, max_cols * max_rows)
        visible_count = len(devices) if len(devices) <= capacity else min(len(devices), max(2, capacity))
        aspect = usable_w / max(usable_h, 1.0)
        cols = min(max_cols, visible_count, max(1, int(math.ceil(math.sqrt(visible_count * aspect)))))
        rows = max(1, int(math.ceil(visible_count / max(1, cols))))
        cell_w = usable_w / max(1, cols)
        cell_h = usable_h / max(1, rows)
        symbol_size = max(1.2 * mm, min(3.8 * mm, cell_w * 0.34, cell_h * 0.34))

        placements: list[dict[str, Any]] = []
        for index, device in enumerate(devices[:visible_count]):
            row = index // cols
            col = index % cols
            symbol_x = symbol_left + cell_w * (col + 0.5)
            symbol_y = symbol_bottom + usable_h - cell_h * (row + 0.5)
            placements.append({"device": device, "x": symbol_x, "y": symbol_y, "size": symbol_size, "row": row, "col": col})

        for placement in placements:
            device = placement["device"]
            color, half_width, half_height = self._draw_group_device_symbol(
                c,
                x=placement["x"],
                y=placement["y"],
                device=device,
                size=placement["size"],
            )
            placement["color"] = color
            placement["half_width"] = half_width
            placement["half_height"] = half_height
            endpoint = (placement["x"] + half_width + 0.6 * mm, placement["y"])
            connectors[device["subsystem"]].append(endpoint)
            connectors["all"].append(endpoint)
            device_id = device.get("device_id")
            if device_id:
                connectors["by_id"][int(device_id)] = endpoint
            c.setStrokeColor(color)

        for subsystem in ("sps", "soue"):
            subsystem_placements = [placement for placement in placements if placement["device"]["subsystem"] == subsystem]
            if not subsystem_placements:
                continue
            subsystem_placements = sorted(
                subsystem_placements,
                key=lambda placement: (
                    int(placement["row"]),
                    int(placement["col"]) if int(placement["row"]) % 2 == 0 else -int(placement["col"]),
                ),
            )
            color = SOUE_COLOR if subsystem == "soue" else SPS_COLOR
            bus_x = x + width - self.CARD_PADDING * 0.75
            c.setStrokeColor(color)
            c.setLineWidth(0.45)
            previous: dict[str, Any] | None = None
            for placement in subsystem_placements:
                if previous is not None:
                    previous_right = previous["x"] + previous["half_width"] + 0.7 * mm
                    current_left = placement["x"] - placement["half_width"] - 0.7 * mm
                    if abs(previous["y"] - placement["y"]) < 0.3 * mm and previous_right < current_left:
                        c.line(previous_right, previous["y"], current_left, placement["y"])
                    else:
                        previous_exit = previous["x"] + previous["half_width"] + 0.7 * mm
                        current_entry = placement["x"] - placement["half_width"] - 0.7 * mm
                        row_bus_x = min(bus_x, max(previous_exit + 0.7 * mm, current_entry + 0.7 * mm))
                        c.line(previous_exit, previous["y"], row_bus_x, previous["y"])
                        c.line(row_bus_x, previous["y"], row_bus_x, placement["y"])
                        c.line(row_bus_x, placement["y"], current_entry, placement["y"])
                previous = placement
            last = subsystem_placements[-1]
            last_exit = last["x"] + last["half_width"] + 0.7 * mm
            port = (x + width + 0.6 * mm, last["y"])
            if last_exit < bus_x:
                c.line(last_exit, last["y"], bus_x, last["y"])
                c.line(bus_x, last["y"], port[0], port[1])
            else:
                c.line(last_exit, last["y"], port[0], port[1])
            connectors["route_ports"][subsystem] = port

        hidden_count = len(devices) - visible_count
        if hidden_count > 0:
            c.setFillColor(colors.black)
            c.setFont(DEFAULT_FONT_NAME, self.SMALL_FONT_SIZE)
            c.drawRightString(x + width - self.CARD_PADDING, y + 2.2 * mm, f"+{hidden_count} \u0448\u0442.")
        return connectors

    def _draw_group_card(
        self,
        c: canvas.Canvas,
        group: dict[str, Any],
        *,
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> dict[str, Any]:
        c.setStrokeColor(DEFAULT_BORDER_COLOR)
        c.setFillColor(colors.white)
        c.setLineWidth(DEFAULT_INNER_BORDER_THICKNESS_MM)
        c.rect(x, y, width, height, stroke=1, fill=1)
        c.line(x, y + height - self.CARD_HEADER_HEIGHT, x + width, y + height - self.CARD_HEADER_HEIGHT)

        title = self._string(group.get("title"), "ЗКСПС")
        c.setFillColor(colors.black)
        c.setFont(f"{DEFAULT_FONT_NAME} Bold", self.SECTION_FONT_SIZE)
        self.fit_text_in_box(
            c,
            title,
            x + 1.0 * mm,
            y + height - self.CARD_HEADER_HEIGHT,
            width - 2.0 * mm,
            self.CARD_HEADER_HEIGHT,
            CENTER,
            font_size=self.SECTION_FONT_SIZE,
        )

        meta_parts = []
        if group.get("area_sqm") not in (None, ""):
            try:
                meta_parts.append(f"S={float(group.get('area_sqm') or 0):.1f} м2")
            except (TypeError, ValueError):
                meta_parts.append(f"S={group.get('area_sqm')} м2")
        if group.get("room_count"):
            meta_parts.append(f"пом.: {group.get('room_count')}")
        cursor_y = y + height - self.CARD_HEADER_HEIGHT - 4.0 * mm
        if meta_parts:
            cursor_y = self._draw_wrapped_text(
                c,
                ", ".join(meta_parts),
                x=x + self.CARD_PADDING,
                y=cursor_y,
                width=width - 2 * self.CARD_PADDING,
                font_size=self.SMALL_FONT_SIZE,
                max_lines=1,
            )
            cursor_y -= 0.8 * mm

        connectors = self._draw_group_devices(c, group, x=x, y=y, width=width, height=height, cursor_y=cursor_y)
        connectors["rect"] = {"x": x, "y": y, "width": width, "height": height}
        return connectors

        all_items = [(item, "sps") for item in (group.get("sps_items") or [])]
        all_items.extend((item, "soue") for item in (group.get("soue_items") or []))
        available_lines = max(1, int((cursor_y - y - 2.0 * mm) / (self.BODY_FONT_SIZE * 1.3)))
        visible_items = all_items[:available_lines]
        for index, (item, subsystem) in enumerate(visible_items):
            self._draw_device_line(
                c,
                x=x + self.CARD_PADDING,
                y=cursor_y,
                width=width - 2 * self.CARD_PADDING,
                item=item,
                subsystem=subsystem,
                index=index,
                font_size=self.BODY_FONT_SIZE,
            )
            cursor_y -= self.BODY_FONT_SIZE * 1.45

        hidden_count = len(all_items) - len(visible_items)
        if hidden_count > 0:
            c.setFillColor(colors.black)
            c.setFont(DEFAULT_FONT_NAME, self.SMALL_FONT_SIZE)
            c.drawRightString(x + width - self.CARD_PADDING, y + 2.2 * mm, f"+{hidden_count} поз.")
        elif not all_items:
            c.setFillColor(colors.black)
            c.setFont(DEFAULT_FONT_NAME, self.SMALL_FONT_SIZE)
            c.drawCentredString(x + width / 2, y + height / 2 - 2.0 * mm, "оборудование не размещено")

        return x + width, y + height / 2

    def _floor_sort_key(self, floor: dict[str, Any]) -> tuple[str, float, str]:
        building = self._string(floor.get("building_label"))
        try:
            floor_number = float(floor.get("floor_number"))
        except (TypeError, ValueError):
            floor_number = 0.0
        return building, floor_number, self._string(floor.get("title"))

    def _draw_floors(
        self,
        c: canvas.Canvas,
        *,
        floors: list[dict[str, Any]],
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> dict[str, dict[str, Any]]:
        group_points: dict[str, dict[str, Any]] = {}
        if not floors:
            self._draw_header_box(c, x=x, y=y + height - 12 * mm, width=width, height=12 * mm, text="Этажи и ЗКСПС")
            c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
            c.setFillColor(colors.black)
            c.drawCentredString(x + width / 2, y + height / 2, "Нет размещенного оборудования")
            return group_points

        floors = sorted(floors, key=self._floor_sort_key)
        gap = 4.0 * mm
        floor_count = len(floors)
        band_height = max(32.0 * mm, (height - gap * (floor_count - 1)) / max(1, floor_count))
        if band_height * floor_count + gap * (floor_count - 1) > height:
            band_height = (height - gap * (floor_count - 1)) / max(1, floor_count)

        cursor_top = y + height
        for floor in floors:
            band_y = cursor_top - band_height
            c.setStrokeColor(DEFAULT_BORDER_COLOR)
            c.setFillColor(colors.white)
            c.setLineWidth(DEFAULT_INNER_BORDER_THICKNESS_MM)
            c.rect(x, band_y, width, band_height, stroke=1, fill=1)

            floor_title = self._string(floor.get("title"), "Этаж")
            building = self._string(floor.get("building_label"))
            header = f"{building}. {floor_title}" if building else floor_title
            header_h = min(9.0 * mm, max(6.0 * mm, band_height * 0.18))
            c.setFillColor(LIGHT_GRAY)
            c.rect(x, cursor_top - header_h, width, header_h, stroke=0, fill=1)
            c.setStrokeColor(DEFAULT_BORDER_COLOR)
            c.line(x, cursor_top - header_h, x + width, cursor_top - header_h)
            c.setFillColor(colors.black)
            c.setFont(f"{DEFAULT_FONT_NAME} Bold", self.SECTION_FONT_SIZE)
            self.fit_text_in_box(c, header, x, cursor_top - header_h, width, header_h, CENTER, font_size=self.SECTION_FONT_SIZE)

            groups = list(floor.get("zones") or [])
            if not groups:
                c.setFont(DEFAULT_FONT_NAME, self.BODY_FONT_SIZE)
                c.setFillColor(colors.black)
                c.drawCentredString(x + width / 2, band_y + (band_height - header_h) / 2, "Оборудование на этаже не задано")
                cursor_top = band_y - gap
                continue

            card_gap = 3.0 * mm
            usable_h = max(12.0 * mm, band_height - header_h - 2 * card_gap)
            cols = min(6, max(1, int(math.ceil(math.sqrt(len(groups) * width / max(usable_h, 1.0))))))
            rows = max(1, int(math.ceil(len(groups) / cols)))
            card_w = (width - card_gap * (cols + 1)) / cols
            card_h = (usable_h - card_gap * (rows - 1)) / rows
            min_card_h = 17.0 * mm
            if card_h < min_card_h and cols < 6:
                cols = min(6, max(1, int(math.ceil(len(groups) / max(1, int(usable_h / min_card_h))))))
                rows = max(1, int(math.ceil(len(groups) / cols)))
                card_w = (width - card_gap * (cols + 1)) / cols
                card_h = (usable_h - card_gap * (rows - 1)) / rows

            for index, group in enumerate(groups):
                row = index // cols
                col = index % cols
                card_x = x + card_gap + col * (card_w + card_gap)
                card_y = band_y + card_gap + (rows - 1 - row) * (card_h + card_gap)
                group_key = self._string(group.get("key"))
                if group_key:
                    group_points[group_key] = self._draw_group_card(
                        c,
                        group,
                        x=card_x,
                        y=card_y,
                        width=card_w,
                        height=card_h,
                    )

            cursor_top = band_y - gap
        return group_points

    def _draw_instruments(
        self,
        c: canvas.Canvas,
        *,
        instruments: list[dict[str, Any]],
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> dict[int, tuple[float, float]]:
        instrument_points: dict[int, tuple[float, float]] = {}
        self._draw_header_box(c, x=x, y=y + height - 10 * mm, width=width, height=10 * mm, text="Приборы и сеть")
        body_y = y
        body_h = height - 10 * mm
        c.setStrokeColor(DEFAULT_BORDER_COLOR)
        c.setFillColor(colors.white)
        c.setLineWidth(DEFAULT_INNER_BORDER_THICKNESS_MM)
        c.rect(x, body_y, width, body_h, stroke=1, fill=0)

        resolved = instruments or [
            {
                "id": 0,
                "name": "Прибор СПС/СОУЭ",
                "equipment_name": "Прибор",
                "type": "control_panel",
                "floor_label": "",
            }
        ]
        gap = 5.0 * mm
        item_h = min(24.0 * mm, max(14.0 * mm, (body_h - gap * (len(resolved) + 1)) / max(1, len(resolved))))
        cursor_y = body_y + body_h - gap - item_h
        for index, instrument in enumerate(resolved):
            instrument_id = int(instrument.get("id") or 0)
            c.setFillColor(colors.white)
            c.setStrokeColor(DEFAULT_BORDER_COLOR)
            c.rect(x + 4 * mm, cursor_y, width - 8 * mm, item_h, stroke=1, fill=1)
            symbol_x = x + 12 * mm
            symbol_y = cursor_y + item_h / 2
            draw_signal_instrument_symbol(c, symbol_x, symbol_y, instrument.get("type"), size=7.0 * mm)

            name = self._string(instrument.get("name") or instrument.get("equipment_name"), "Прибор")
            floor_label = self._string(instrument.get("floor_label"))
            text = f"{name} ({floor_label})" if floor_label else name
            self._draw_wrapped_text(
                c,
                text,
                x=x + 22 * mm,
                y=cursor_y + item_h - 5 * mm,
                width=width - 28 * mm,
                font_size=self.BODY_FONT_SIZE,
                max_lines=2,
            )
            point = (x + 4 * mm, cursor_y + item_h / 2)
            instrument_points[instrument_id] = point
            if index == 0:
                instrument_points.setdefault(-1, point)
            cursor_y -= item_h + gap

        c.setStrokeColor(NETWORK_COLOR)
        c.setLineWidth(0.8)
        net_y = body_y + 7 * mm
        c.line(x + 8 * mm, net_y, x + width - 8 * mm, net_y)
        c.setFillColor(NETWORK_COLOR)
        c.setFont(DEFAULT_FONT_NAME, self.SMALL_FONT_SIZE)
        c.drawCentredString(x + width / 2, net_y + 2 * mm, "RS-485 / Ethernet / питание 220В")
        return instrument_points

    def _line_segments(self, points: list[tuple[float, float]]) -> list[tuple[float, float, float, float]]:
        segments: list[tuple[float, float, float, float]] = []
        for start, end in zip(points, points[1:]):
            if abs(start[0] - end[0]) < 0.01 and abs(start[1] - end[1]) < 0.01:
                continue
            segments.append((start[0], start[1], end[0], end[1]))
        return segments

    def _expanded_rect(self, rect: dict[str, float], clearance: float) -> dict[str, float]:
        return {
            "x": float(rect["x"]) - clearance,
            "y": float(rect["y"]) - clearance,
            "width": float(rect["width"]) + 2 * clearance,
            "height": float(rect["height"]) + 2 * clearance,
        }

    def _segment_intersects_rect(
        self,
        segment: tuple[float, float, float, float],
        rect: dict[str, float],
        *,
        clearance: float = 0.0,
    ) -> bool:
        expanded = self._expanded_rect(rect, clearance)
        rect_left = expanded["x"]
        rect_right = expanded["x"] + expanded["width"]
        rect_bottom = expanded["y"]
        rect_top = expanded["y"] + expanded["height"]
        x1, y1, x2, y2 = segment
        if abs(y1 - y2) < 0.01:
            left, right = sorted((x1, x2))
            return rect_bottom <= y1 <= rect_top and max(left, rect_left) <= min(right, rect_right)
        if abs(x1 - x2) < 0.01:
            bottom, top = sorted((y1, y2))
            return rect_left <= x1 <= rect_right and max(bottom, rect_bottom) <= min(top, rect_top)
        return True

    def _route_path_clear(
        self,
        points: list[tuple[float, float]],
        *,
        obstacles: list[dict[str, Any]],
        source_key: str,
    ) -> bool:
        for segment in self._line_segments(points):
            for obstacle in obstacles:
                if obstacle.get("key") == source_key:
                    continue
                rect = obstacle.get("rect")
                if rect and self._segment_intersects_rect(segment, rect, clearance=0.7 * mm):
                    return False
        return True

    def _build_route_points(
        self,
        *,
        start: tuple[float, float],
        end: tuple[float, float],
        lane_x: float,
        source_rect: dict[str, float] | None,
        source_key: str,
        obstacles: list[dict[str, Any]],
        min_y: float,
        max_y: float,
        line_index: int,
    ) -> list[tuple[float, float]]:
        direct = [start, (lane_x, start[1]), (lane_x, end[1]), end]
        if self._route_path_clear(direct, obstacles=obstacles, source_key=source_key):
            return direct

        candidates: list[float] = []
        if source_rect:
            below = float(source_rect["y"]) - 1.2 * mm
            above = float(source_rect["y"]) + float(source_rect["height"]) + 1.2 * mm
            for step in range(14):
                offset = (step + (line_index % 3) * 0.35) * 0.65 * mm
                candidates.extend((below - offset, above + offset))
        candidates.extend(start[1] + offset * mm for offset in (-8, 8, -14, 14, -20, 20))

        for detour_y in candidates:
            if detour_y < min_y + 1.0 * mm or detour_y > max_y - 1.0 * mm:
                continue
            candidate = [start, (start[0], detour_y), (lane_x, detour_y), (lane_x, end[1]), end]
            if self._route_path_clear(candidate, obstacles=obstacles, source_key=source_key):
                return candidate
        return direct

    def _draw_routes(
        self,
        c: canvas.Canvas,
        *,
        floors: list[dict[str, Any]],
        group_points: dict[str, dict[str, Any]],
        instrument_points: dict[int, tuple[float, float]],
        min_x: float,
        max_x: float,
        min_y: float,
        max_y: float,
    ) -> None:
        obstacles = [
            {"key": key, "rect": value.get("rect")}
            for key, value in group_points.items()
            if value.get("rect")
        ]
        rightmost_card_x = max(
            (float(item["rect"]["x"]) + float(item["rect"]["width"]) for item in obstacles),
            default=min_x,
        )
        lane_left = rightmost_card_x + 1.0 * mm
        lane_right = max_x - 1.2 * mm
        line_total = sum(len(route.get("target_group_keys") or []) for floor in floors for route in (floor.get("routes") or []))
        available_lane_width = max(0.0, lane_right - lane_left)
        if line_total > 1 and available_lane_width > 0:
            lane_spacing = min(0.45 * mm, available_lane_width / max(1, line_total - 1))
        else:
            lane_spacing = 0.45 * mm
        route_line_width = max(0.2, min(0.45, lane_spacing * 0.35))
        route_index = 0
        line_index = 0
        for floor in floors:
            for route in floor.get("routes") or []:
                route_index += 1
                subsystem = self._string(route.get("subsystem"), "sps")
                color = SOUE_COLOR if subsystem == "soue" else SPS_COLOR
                instrument_id = int(route.get("instrument_id") or 0)
                end = instrument_points.get(instrument_id) or instrument_points.get(-1)
                if end is None:
                    continue
                target_group_keys = list(route.get("target_group_keys") or [])
                if not target_group_keys:
                    continue
                target_device_ids: list[int] = []
                for raw_device_id in route.get("target_device_ids") or []:
                    try:
                        target_device_ids.append(int(raw_device_id))
                    except (TypeError, ValueError):
                        continue
                for group_key in target_group_keys:
                    group_connector = group_points.get(group_key) or {}
                    route_ports = group_connector.get("route_ports") or {}
                    start = route_ports.get(subsystem)
                    if not start:
                        by_id = group_connector.get("by_id") or {}
                        points = [by_id[device_id] for device_id in target_device_ids if device_id in by_id]
                        if not points:
                            points = list(group_connector.get(subsystem) or group_connector.get("all") or [])
                        start = points[-1] if points else None
                    if not start:
                        continue
                    line_index += 1
                    lane_x = max(lane_left, lane_right - (line_index - 1) * lane_spacing)
                    path = self._build_route_points(
                        start=start,
                        end=end,
                        lane_x=lane_x,
                        source_rect=group_connector.get("rect"),
                        source_key=group_key,
                        obstacles=obstacles,
                        min_y=min_y,
                        max_y=max_y,
                        line_index=line_index,
                    )
                    c.setStrokeColor(color)
                    c.setLineWidth(route_line_width)
                    for start_point, end_point in zip(path, path[1:]):
                        c.line(start_point[0], start_point[1], end_point[0], end_point[1])

    def _route_label(self, route: dict[str, Any]) -> str:
        label = self._string(route.get("label"), "Шлейф")
        length = route.get("length_m")
        try:
            length_text = f"{float(length):.1f} м"
        except (TypeError, ValueError):
            length_text = ""
        return f"{label}, {length_text}" if length_text else label

    def _draw_route_list(
        self,
        c: canvas.Canvas,
        *,
        floors: list[dict[str, Any]],
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        self._draw_header_box(c, x=x, y=y + height - 9 * mm, width=width, height=9 * mm, text="Кабельные шлейфы")
        c.setStrokeColor(DEFAULT_BORDER_COLOR)
        c.setFillColor(colors.white)
        c.rect(x, y, width, height - 9 * mm, stroke=1, fill=0)
        routes = [route for floor in floors for route in (floor.get("routes") or [])]
        if not routes:
            c.setFont(DEFAULT_FONT_NAME, self.BODY_FONT_SIZE)
            c.setFillColor(colors.black)
            c.drawCentredString(x + width / 2, y + (height - 9 * mm) / 2, "Шлейфы не заданы")
            return

        font_size = self.SMALL_FONT_SIZE if len(routes) > 10 else self.BODY_FONT_SIZE
        line_h = font_size * 1.25
        cursor_y = y + height - 13 * mm
        for route in routes:
            if cursor_y < y + 3 * mm:
                c.setFillColor(colors.black)
                c.setFont(DEFAULT_FONT_NAME, self.SMALL_FONT_SIZE)
                c.drawRightString(x + width - 2 * mm, y + 2.5 * mm, "см. планы сетей")
                break
            color = SOUE_COLOR if route.get("subsystem") == "soue" else SPS_COLOR
            c.setStrokeColor(color)
            c.setLineWidth(1.0)
            c.line(x + 2 * mm, cursor_y + 1.5 * mm, x + 9 * mm, cursor_y + 1.5 * mm)
            target_refs = ", ".join(str(ref) for ref in (route.get("target_refs") or [])[:3])
            route_text = self._route_label(route)
            if target_refs:
                route_text = f"{route_text}: {target_refs}"
            self._draw_wrapped_text(
                c,
                route_text,
                x=x + 11 * mm,
                y=cursor_y,
                width=width - 13 * mm,
                font_size=font_size,
                max_lines=1,
                color=color,
            )
            cursor_y -= line_h

    def _draw_equipment_totals(
        self,
        c: canvas.Canvas,
        *,
        equipment_totals: list[dict[str, Any]],
        x: float,
        y: float,
        width: float,
        height: float,
    ) -> None:
        self._draw_header_box(c, x=x, y=y + height - 9 * mm, width=width, height=9 * mm, text="Используемое оборудование")
        body_y = y
        body_h = height - 9 * mm
        c.setStrokeColor(DEFAULT_BORDER_COLOR)
        c.setFillColor(colors.white)
        c.rect(x, body_y, width, body_h, stroke=1, fill=0)
        rows = [row for row in equipment_totals if int(row.get("quantity") or 0) > 0]
        if not rows:
            c.setFont(DEFAULT_FONT_NAME, self.BODY_FONT_SIZE)
            c.setFillColor(colors.black)
            c.drawCentredString(x + width / 2, body_y + body_h / 2, "Оборудование не выбрано")
            return

        columns = 1 if len(rows) <= 12 else 2
        column_width = width / columns
        rows_per_column = int(math.ceil(len(rows) / columns))
        font_size = 7.0 if rows_per_column <= 16 else 5.8
        line_h = font_size * 1.25
        for column in range(columns):
            col_rows = rows[column * rows_per_column : (column + 1) * rows_per_column]
            cursor_y = body_y + body_h - 4 * mm
            text_x = x + column * column_width + 2 * mm
            for row in col_rows:
                if cursor_y < body_y + 2 * mm:
                    break
                name = self._string(row.get("technical_name") or row.get("name"), "Оборудование")
                quantity = int(row.get("quantity") or 0)
                self._draw_wrapped_text(
                    c,
                    f"{name} - {quantity} шт.",
                    x=text_x,
                    y=cursor_y,
                    width=column_width - 4 * mm,
                    font_size=font_size,
                    max_lines=1,
                )
                cursor_y -= line_h
            if column > 0:
                c.setStrokeColor(DEFAULT_BORDER_COLOR)
                c.setLineWidth(0.5)
                c.line(x + column * column_width, body_y, x + column * column_width, body_y + body_h)

    def draw(self, c: canvas.Canvas):
        c.setPageSize((self.page_width, self.page_height))
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        self.draw_outer_border(c)
        self.draw_main_title_box(c, self.main_title_box_type)
        self.fill_main_title_box(c, self.main_title_box_type)

        content_left, content_right, content_top, content_bottom = self._content_bounds()
        margin = 6.0 * mm
        content_x = content_left + margin
        content_width = content_right - content_left - 2 * margin
        cursor_y = self._draw_heading(c, x=content_x, y=content_top - 9 * mm, width=content_width)

        panel_gap = 5.0 * mm
        side_width = 84.0 * mm
        scheme_top = cursor_y - 2.0 * mm
        scheme_bottom = content_bottom + margin
        scheme_height = max(80 * mm, scheme_top - scheme_bottom)
        scheme_x = content_x
        side_x = content_x + content_width - side_width
        scheme_width = side_x - scheme_x - panel_gap

        floors = list(self.structural_scheme.get("floors") or [])
        instruments = list(self.structural_scheme.get("instruments") or [])
        group_points = self._draw_floors(
            c,
            floors=floors,
            x=scheme_x,
            y=scheme_bottom,
            width=scheme_width,
            height=scheme_height,
        )

        instrument_height = scheme_height * 0.55
        route_height = scheme_height - instrument_height - panel_gap
        instrument_points = self._draw_instruments(
            c,
            instruments=instruments,
            x=side_x,
            y=scheme_bottom + route_height + panel_gap,
            width=side_width,
            height=instrument_height,
        )
        self._draw_route_list(
            c,
            floors=floors,
            x=side_x,
            y=scheme_bottom,
            width=side_width,
            height=route_height,
        )
        self._draw_routes(
            c,
            floors=floors,
            group_points=group_points,
            instrument_points=instrument_points,
            min_x=scheme_x,
            max_x=side_x,
            min_y=scheme_bottom,
            max_y=scheme_top,
        )

        c.setStrokeColor(DEFAULT_BORDER_COLOR)
        c.setLineWidth(DEFAULT_OUTER_BORDER_THICKNESS_MM)
        c.showPage()
