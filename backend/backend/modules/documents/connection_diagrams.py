"""Connection diagram payloads for project PDF generation."""

from __future__ import annotations

from typing import Any

from backend.modules.documents.specification import (
    FIRE_ALARM_ROLE_BY_DEVICE_TYPE,
    INSTRUMENT_FALLBACK_ROLES,
    SOUE_ROLE_BY_DEVICE_TYPE,
    get_equipment_technical_name,
)
from backend.modules.equipment.domain.constants import (
    FIRE_ALARM_DEVICE_CATEGORY_MAP,
    SIGNAL_INSTRUMENT_CATEGORY_MAP,
    SOUE_DEVICE_CATEGORY_MAP,
)


CONNECTION_DIAGRAM_CATEGORIES = {
    "linear",
    "smoke",
    "heat",
    "manual",
    "siren",
    "exit_sign",
    "speech",
    "instrument",
    "keyboard",
}


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _equipment_payload(equipment: Any, position_number: int) -> dict[str, Any] | None:
    category = _normalize_text(getattr(equipment, "category", None))
    diagram_path = _normalize_text(getattr(equipment, "connection_diagram_path", None))
    if category not in CONNECTION_DIAGRAM_CATEGORIES or not diagram_path:
        return None

    return {
        "equipment_id": int(getattr(equipment, "id", 0) or 0),
        "position": str(position_number),
        "name": _normalize_text(getattr(equipment, "name", None)),
        "technical_name": get_equipment_technical_name(equipment),
        "category": category,
        "manufacturer": _normalize_text(getattr(equipment, "manufacturer", None)),
        "connection_diagram_path": diagram_path,
        "page_title": "Схема подключения оборудования",
    }


def _resolve_fire_alarm_equipment(alarm: Any, selection_map: dict[str, Any]) -> Any | None:
    equipment = getattr(alarm, "equipment", None)
    if equipment is not None:
        return equipment
    role_key = FIRE_ALARM_ROLE_BY_DEVICE_TYPE.get(_normalize_text(getattr(alarm, "device_type", "")))
    return selection_map.get(role_key) if role_key else None


def _resolve_soue_equipment(device: Any, selection_map: dict[str, Any]) -> Any | None:
    equipment = getattr(device, "equipment", None)
    if equipment is not None:
        return equipment
    role_key = SOUE_ROLE_BY_DEVICE_TYPE.get(_normalize_text(getattr(device, "device_type", "")))
    return selection_map.get(role_key) if role_key else None


def _resolve_instrument_equipment(instrument: Any, selection_map: dict[str, Any]) -> Any | None:
    equipment = getattr(instrument, "equipment", None)
    if equipment is not None:
        return equipment

    candidates = {
        int(getattr(candidate, "id", 0) or 0): candidate
        for role_key in INSTRUMENT_FALLBACK_ROLES
        if (candidate := selection_map.get(role_key)) is not None
        and int(getattr(candidate, "id", 0) or 0) > 0
    }
    if len(candidates) == 1:
        return next(iter(candidates.values()))
    return None


def build_project_connection_diagrams(project: Any, floor_plans: list[Any]) -> list[dict[str, Any]]:
    """Return one connection diagram page payload per used equipment item."""

    selection_map = {
        row.role_key: row.equipment
        for row in (getattr(project, "equipment_selections", None) or [])
        if getattr(row, "equipment", None) is not None
    }
    diagrams_by_equipment_id: dict[int, dict[str, Any]] = {}

    def add_equipment(equipment: Any | None) -> None:
        if equipment is None:
            return
        equipment_id = int(getattr(equipment, "id", 0) or 0)
        if equipment_id <= 0 or equipment_id in diagrams_by_equipment_id:
            return
        payload = _equipment_payload(equipment, len(diagrams_by_equipment_id) + 1)
        if payload is not None:
            diagrams_by_equipment_id[equipment_id] = payload

    for floor_plan in floor_plans:
        for instrument in getattr(floor_plan, "signal_instruments", None) or []:
            equipment = _resolve_instrument_equipment(instrument, selection_map)
            if equipment is not None:
                allowed_categories = SIGNAL_INSTRUMENT_CATEGORY_MAP.get(
                    _normalize_text(getattr(instrument, "instrument_type", "")),
                    (),
                )
                if not allowed_categories or getattr(equipment, "category", None) in allowed_categories:
                    add_equipment(equipment)

        for alarm in getattr(floor_plan, "fire_alarms", None) or []:
            equipment = _resolve_fire_alarm_equipment(alarm, selection_map)
            if equipment is not None:
                allowed_categories = FIRE_ALARM_DEVICE_CATEGORY_MAP.get(
                    _normalize_text(getattr(alarm, "device_type", "")),
                    (),
                )
                if not allowed_categories or getattr(equipment, "category", None) in allowed_categories:
                    add_equipment(equipment)

        for device in getattr(floor_plan, "soue_devices", None) or []:
            equipment = _resolve_soue_equipment(device, selection_map)
            if equipment is not None:
                allowed_categories = SOUE_DEVICE_CATEGORY_MAP.get(
                    _normalize_text(getattr(device, "device_type", "")),
                    (),
                )
                if not allowed_categories or getattr(equipment, "category", None) in allowed_categories:
                    add_equipment(equipment)

    return list(diagrams_by_equipment_id.values())
