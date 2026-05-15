"""Conventional symbols payload builder for PDF generation."""

from __future__ import annotations

from typing import Any

from backend.modules.documents.specification import (
    _resolve_fire_alarm_equipment,
    _resolve_instrument_equipment,
    _resolve_soue_equipment,
)


DEFAULT_CONVENTIONAL_SYMBOLS_PAGE_TITLE = "Условные графические обозначения"
DEFAULT_CONVENTIONAL_SYMBOLS_HEADING = "УСЛОВНЫЕ ГРАФИЧЕСКИЕ ОБОЗНАЧЕНИЯ"

ROW_KIND_ORDER = {
    "instrument": 10,
    "smoke_detector": 20,
    "heat_detector": 30,
    "linear_detector": 40,
    "manual_call_point": 50,
    "siren": 60,
    "exit_sign": 70,
    "speech_device": 80,
}

DECODE_LINE_BY_TOKEN = {
    "[этаж]": "[этаж] - номер этажа, на котором установлен элемент.",
    "[шлейф]": "[шлейф] - номер шлейфа (линии) пожарной сигнализации.",
    "[адрес]": "[адрес] - адрес извещателя в шлейфе.",
    "[номер]": "[номер] - порядковый номер устройства в линии.",
    "BTH": "BTH - автоматический пожарный извещатель.",
    "BTM": "BTM - ручной пожарный извещатель.",
    "BIAS1": "BIAS1 - звуковой оповещатель.",
    "BIAL2": "BIAL2 - световой или речевой оповещатель.",
    "ARK": "ARK - прибор контроля и управления.",
}

DECODE_TOKEN_ORDER = (
    "[этаж]",
    "[шлейф]",
    "[адрес]",
    "[номер]",
    "BTH",
    "BTM",
    "BIAS1",
    "BIAL2",
    "ARK",
)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _selection_map(project: Any) -> dict[str, Any]:
    return {
        row.role_key: row.equipment
        for row in (getattr(project, "equipment_selections", None) or [])
        if getattr(row, "equipment", None) is not None
    }


def _equipment_name(equipment: Any | None, *, fallback: str = "") -> str:
    return _normalize_text(getattr(equipment, "name", None)) or _normalize_text(fallback)


def _instrument_label(instrument: Any, equipment: Any | None) -> str:
    instrument_type = _normalize_text(getattr(instrument, "instrument_type", None))
    if instrument_type == "control_panel":
        return "ARK"
    return (
        _normalize_text(getattr(instrument, "equipment_name", None))
        or _normalize_text(getattr(instrument, "name", None))
        or _equipment_name(equipment)
    )


def _fire_alarm_template(device_type: str) -> tuple[str, tuple[str, ...]]:
    if device_type == "manual_call_point":
        return "[этаж]BTM[шлейф].[адрес]", ("[этаж]", "[шлейф]", "[адрес]", "BTM")
    return "[этаж]BTH[шлейф].[адрес]", ("[этаж]", "[шлейф]", "[адрес]", "BTH")


def _soue_template(device_type: str) -> tuple[str, tuple[str, ...]]:
    if device_type == "siren":
        return "[этаж]BIAS1.[номер]", ("[этаж]", "[номер]", "BIAS1")
    return "[этаж]BIAL2.[номер]", ("[этаж]", "[номер]", "BIAL2")


def _row_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        int(row.get("_sort_order") or 999),
        _normalize_text(row.get("name", "")).lower(),
        _normalize_text(row.get("designation", "")).lower(),
    )


def _build_decode_lines(tokens: set[str]) -> list[str]:
    return [DECODE_LINE_BY_TOKEN[token] for token in DECODE_TOKEN_ORDER if token in tokens]


def build_project_conventional_symbols(project: Any, floor_plans: list[Any]) -> dict[str, Any]:
    selection_map = _selection_map(project)
    unique_rows: dict[tuple[Any, ...], dict[str, Any]] = {}
    used_tokens: set[str] = set()

    for floor_plan in floor_plans:
        for instrument in getattr(floor_plan, "signal_instruments", None) or []:
            equipment, _warning = _resolve_instrument_equipment(floor_plan, instrument, selection_map)
            if equipment is None:
                continue
            designation = _instrument_label(instrument, equipment)
            name = _equipment_name(equipment, fallback=_normalize_text(getattr(instrument, "name", None)) or designation)
            if not designation or not name:
                continue
            instrument_type = _normalize_text(getattr(instrument, "instrument_type", None)) or "instrument"
            row_key = ("instrument", instrument_type, designation, int(getattr(equipment, "id", 0) or 0), name)
            unique_rows[row_key] = {
                "designation": designation,
                "name": name,
                "symbol_kind": "instrument",
                "symbol_type": instrument_type,
                "_sort_order": ROW_KIND_ORDER.get("instrument", 10),
            }
            if designation == "ARK":
                used_tokens.add("ARK")

        for alarm in getattr(floor_plan, "fire_alarms", None) or []:
            equipment, _warning = _resolve_fire_alarm_equipment(floor_plan, alarm, selection_map)
            if equipment is None:
                continue
            device_type = _normalize_text(getattr(alarm, "device_type", None)) or "smoke_detector"
            designation, tokens = _fire_alarm_template(device_type)
            name = _equipment_name(equipment, fallback=_normalize_text(getattr(alarm, "device_model", None)))
            if not name:
                continue
            row_key = ("fire_alarm", device_type, designation, int(getattr(equipment, "id", 0) or 0), name)
            unique_rows[row_key] = {
                "designation": designation,
                "name": name,
                "symbol_kind": "fire_alarm",
                "symbol_type": device_type,
                "_sort_order": ROW_KIND_ORDER.get(device_type, 999),
            }
            used_tokens.update(tokens)

        for device in getattr(floor_plan, "soue_devices", None) or []:
            equipment, _warning = _resolve_soue_equipment(floor_plan, device, selection_map)
            if equipment is None:
                continue
            device_type = _normalize_text(getattr(device, "device_type", None)) or "exit_sign"
            designation, tokens = _soue_template(device_type)
            name = _equipment_name(equipment, fallback=_normalize_text(getattr(device, "device_model", None)))
            if not name:
                continue
            row_key = ("soue_device", device_type, designation, int(getattr(equipment, "id", 0) or 0), name)
            unique_rows[row_key] = {
                "designation": designation,
                "name": name,
                "symbol_kind": "soue_device",
                "symbol_type": device_type,
                "_sort_order": ROW_KIND_ORDER.get(device_type, 999),
            }
            used_tokens.update(tokens)

    rows = [
        {
            "designation": row["designation"],
            "name": row["name"],
            "symbol_kind": row["symbol_kind"],
            "symbol_type": row["symbol_type"],
        }
        for row in sorted(unique_rows.values(), key=_row_sort_key)
    ]
    return {
        "page_title": DEFAULT_CONVENTIONAL_SYMBOLS_PAGE_TITLE,
        "heading": DEFAULT_CONVENTIONAL_SYMBOLS_HEADING,
        "rows": rows,
        "decode_lines": _build_decode_lines(used_tokens),
    }
