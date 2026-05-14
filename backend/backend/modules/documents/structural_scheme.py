"""Build structural SPS/SOUE scheme payloads for PDF rendering."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from backend.modules.documents.specification import (
    FIRE_ALARM_ROLE_BY_DEVICE_TYPE,
    INSTRUMENT_FALLBACK_ROLES,
    SOUE_ROLE_BY_DEVICE_TYPE,
    get_equipment_technical_name,
)


FIRE_ALARM_TYPE_LABELS = {
    "linear_detector": "Линейные извещатели",
    "smoke_detector": "Дымовые извещатели",
    "heat_detector": "Тепловые извещатели",
    "manual_call_point": "Ручные извещатели",
}

SOUE_TYPE_LABELS = {
    "siren": "Звуковые оповещатели",
    "exit_sign": "Световые оповещатели",
    "speech": "Речевые оповещатели",
    "speech_device": "Речевые оповещатели",
}

INSTRUMENT_TYPE_LABELS = {
    "control_panel": "Прибор приемно-контрольный",
    "loop_controller": "Контроллер линии",
    "annunciator": "Блок индикации",
}

CATEGORY_LABELS = {
    "linear": "Линейный извещатель",
    "smoke": "Дымовой извещатель",
    "heat": "Тепловой извещатель",
    "manual": "Ручной извещатель",
    "siren": "Звуковой оповещатель",
    "exit_sign": "Световой оповещатель",
    "speech": "Речевой оповещатель",
    "instrument": "Прибор",
    "keyboard": "Клавиатура",
    "cable": "Кабель",
    "other": "Оборудование",
}


def _normalize_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    normalized = str(value).strip()
    return normalized or default


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _equipment_key(equipment: Any | None, fallback: str) -> str:
    equipment_id = _as_int(getattr(equipment, "id", None), 0)
    return f"equipment:{equipment_id}" if equipment_id > 0 else fallback


def _equipment_name(equipment: Any | None, fallback: str) -> str:
    if equipment is None:
        return fallback
    return _normalize_text(getattr(equipment, "name", None), fallback)


def _equipment_category(equipment: Any | None, fallback: str = "other") -> str:
    return _normalize_text(getattr(equipment, "category", None), fallback)


def _equipment_total_payload(equipment: Any | None, fallback: str, category: str) -> dict[str, Any]:
    if equipment is None:
        return {
            "equipment_id": None,
            "name": fallback,
            "technical_name": fallback,
            "category": category,
            "manufacturer": "",
            "quantity": 0,
        }
    return {
        "equipment_id": getattr(equipment, "id", None),
        "name": _equipment_name(equipment, fallback),
        "technical_name": get_equipment_technical_name(equipment),
        "category": _equipment_category(equipment, category),
        "manufacturer": _normalize_text(getattr(equipment, "manufacturer", None)),
        "quantity": 0,
    }


def _selection_map(project: Any) -> dict[str, Any]:
    return {
        row.role_key: row.equipment
        for row in (getattr(project, "equipment_selections", None) or [])
        if getattr(row, "equipment", None) is not None
    }


def _resolve_fire_alarm_equipment(alarm: Any, selections: dict[str, Any]) -> Any | None:
    equipment = getattr(alarm, "equipment", None)
    if equipment is not None:
        return equipment
    role_key = FIRE_ALARM_ROLE_BY_DEVICE_TYPE.get(_normalize_text(getattr(alarm, "device_type", None)))
    return selections.get(role_key) if role_key else None


def _resolve_soue_equipment(device: Any, selections: dict[str, Any]) -> Any | None:
    equipment = getattr(device, "equipment", None)
    if equipment is not None:
        return equipment
    device_type = _normalize_text(getattr(device, "device_type", None))
    role_key = SOUE_ROLE_BY_DEVICE_TYPE.get(device_type)
    if role_key is None and device_type == "speech":
        role_key = SOUE_ROLE_BY_DEVICE_TYPE.get("speech_device")
    return selections.get(role_key) if role_key else None


def _resolve_instrument_equipment(instrument: Any, selections: dict[str, Any]) -> Any | None:
    equipment = getattr(instrument, "equipment", None)
    if equipment is not None:
        return equipment
    candidates = {
        _as_int(getattr(candidate, "id", None), 0): candidate
        for role_key in INSTRUMENT_FALLBACK_ROLES
        if (candidate := selections.get(role_key)) is not None
    }
    candidates.pop(0, None)
    if len(candidates) == 1:
        return next(iter(candidates.values()))
    return None


def _floor_label(floor_plan: Any) -> str:
    name = _normalize_text(getattr(floor_plan, "name", None))
    if name:
        return name
    floor_number = getattr(floor_plan, "floor_number", None)
    return f"Этаж {floor_number}" if floor_number is not None else "Этаж"


def _building_label(project: Any, floor_plan: Any) -> str:
    for field_name in ("building_name", "building", "facility_building"):
        value = _normalize_text(getattr(floor_plan, field_name, None))
        if value:
            return value
    return _normalize_text(getattr(project, "facility", None), "Объект")


def _zone_label(zone: Any) -> str:
    zone_name = _normalize_text(getattr(zone, "name", None))
    zone_number = getattr(zone, "zone_number", None)
    if zone_name:
        return zone_name
    if zone_number is not None:
        return f"ЗКСПС №{zone_number}"
    return "ЗКСПС"


def _loop_label(prefix: str, route: Any) -> str:
    route_kind = _normalize_text(getattr(route, "route_kind", None), "шлейф")
    route_number = getattr(route, "route_number", None)
    if route_number is None:
        return f"{prefix} {route_kind}"
    return f"{prefix} {route_kind} {route_number}"


def _device_reference(device: Any, fallback_prefix: str) -> str:
    floor_plan = getattr(device, "floor_plan", None)
    floor_number = getattr(floor_plan, "floor_number", None) if floor_plan is not None else None
    loop_number = getattr(device, "loop_number", None)
    device_number = getattr(device, "device_number", None)
    if floor_number is not None and loop_number is not None and device_number is not None:
        return f"{floor_number}ВТН{loop_number}.{device_number}"
    if loop_number is not None and device_number is not None:
        return f"{fallback_prefix}{loop_number}.{device_number}"
    return f"{fallback_prefix}{getattr(device, 'id', '')}".strip()


def build_project_structural_scheme(project: Any, floor_plans: list[Any]) -> dict[str, Any]:
    """Aggregate project elements into a renderable structural SPS/SOUE scheme."""

    selections = _selection_map(project)
    equipment_totals: dict[str, dict[str, Any]] = {}
    instruments: dict[int, dict[str, Any]] = {}
    device_index: dict[tuple[str, int], dict[str, Any]] = {}
    floor_payloads: list[dict[str, Any]] = []

    def add_total(equipment: Any | None, fallback: str, category: str, quantity: int = 1) -> str:
        key = _equipment_key(equipment, f"{category}:{fallback}")
        if key not in equipment_totals:
            equipment_totals[key] = _equipment_total_payload(equipment, fallback, category)
        equipment_totals[key]["quantity"] += quantity
        return key

    for floor_plan in floor_plans:
        zones_by_id = {
            getattr(zone, "id", None): zone
            for zone in (getattr(floor_plan, "zkspc_zones", None) or [])
        }
        zone_payloads: dict[str, dict[str, Any]] = {}

        def get_zone_payload(zone: Any | None) -> dict[str, Any]:
            if zone is None:
                key = f"floor:{getattr(floor_plan, 'id', 'unknown')}:no-zone"
                title = "Вне ЗКСПС"
                zone_number = None
                area_sqm = None
                room_count = 0
            else:
                key = f"zone:{getattr(zone, 'id', 'unknown')}"
                title = _zone_label(zone)
                zone_number = getattr(zone, "zone_number", None)
                area_sqm = getattr(zone, "area_sqm", None)
                room_count = getattr(zone, "room_count", None)
            if key not in zone_payloads:
                zone_payloads[key] = {
                    "key": key,
                    "title": title,
                    "zone_number": zone_number,
                    "area_sqm": area_sqm,
                    "room_count": room_count,
                    "sps_counts": defaultdict(int),
                    "sps_items": {},
                    "soue_counts": defaultdict(int),
                    "soue_items": {},
                    "route_keys": set(),
                }
            return zone_payloads[key]

        for zone in zones_by_id.values():
            get_zone_payload(zone)

        for alarm in getattr(floor_plan, "fire_alarms", None) or []:
            device_type = _normalize_text(getattr(alarm, "device_type", None), "fire_alarm")
            fallback = FIRE_ALARM_TYPE_LABELS.get(device_type, "Извещатели")
            equipment = _resolve_fire_alarm_equipment(alarm, selections)
            total_key = add_total(equipment, _equipment_name(equipment, fallback), _equipment_category(equipment, "other"))
            zone = zones_by_id.get(getattr(alarm, "zkspc_zone_id", None))
            zone_payload = get_zone_payload(zone)
            zone_payload["sps_counts"][total_key] += 1
            alarm_id = int(getattr(alarm, "id", 0) or 0)
            existing_device_ids = list(zone_payload["sps_items"].get(total_key, {}).get("device_ids") or [])
            zone_payload["sps_items"][total_key] = {
                "label": _equipment_name(equipment, fallback),
                "technical_name": get_equipment_technical_name(equipment) if equipment is not None else fallback,
                "category": _equipment_category(equipment, "other"),
                "device_type": device_type,
                "device_ids": [*existing_device_ids, alarm_id],
            }
            device_index[("sps", alarm_id)] = {
                "group_key": zone_payload["key"],
                "label": _device_reference(alarm, "ИП"),
            }

        soue_floor_key = f"floor:{getattr(floor_plan, 'id', 'unknown')}:soue"
        soue_floor_group = {
            "key": soue_floor_key,
            "title": "СОУЭ",
            "zone_number": None,
            "area_sqm": None,
            "room_count": 0,
            "sps_counts": defaultdict(int),
            "sps_items": {},
            "soue_counts": defaultdict(int),
            "soue_items": {},
            "route_keys": set(),
        }

        for device in getattr(floor_plan, "soue_devices", None) or []:
            device_type = _normalize_text(getattr(device, "device_type", None), "soue")
            fallback = SOUE_TYPE_LABELS.get(device_type, "Оповещатели")
            equipment = _resolve_soue_equipment(device, selections)
            total_key = add_total(equipment, _equipment_name(equipment, fallback), _equipment_category(equipment, "other"))
            soue_floor_group["soue_counts"][total_key] += 1
            device_id = int(getattr(device, "id", 0) or 0)
            existing_device_ids = list(soue_floor_group["soue_items"].get(total_key, {}).get("device_ids") or [])
            soue_floor_group["soue_items"][total_key] = {
                "label": _equipment_name(equipment, fallback),
                "technical_name": get_equipment_technical_name(equipment) if equipment is not None else fallback,
                "category": _equipment_category(equipment, "other"),
                "device_type": device_type,
                "device_ids": [*existing_device_ids, device_id],
            }
            device_index[("soue", device_id)] = {
                "group_key": soue_floor_key,
                "label": _device_reference(device, "ОП"),
            }

        for instrument in getattr(floor_plan, "signal_instruments", None) or []:
            instrument_id = int(getattr(instrument, "id", 0) or 0)
            if instrument_id <= 0:
                continue
            instrument_type = _normalize_text(getattr(instrument, "instrument_type", None), "control_panel")
            fallback = INSTRUMENT_TYPE_LABELS.get(instrument_type, "Прибор")
            equipment = _resolve_instrument_equipment(instrument, selections)
            add_total(equipment, _equipment_name(equipment, fallback), _equipment_category(equipment, "instrument"))
            instruments[instrument_id] = {
                "id": instrument_id,
                "name": _normalize_text(getattr(instrument, "name", None), _equipment_name(equipment, fallback)),
                "type": instrument_type,
                "equipment_name": _equipment_name(equipment, fallback),
                "floor_label": _floor_label(floor_plan),
                "building_label": _building_label(project, floor_plan),
            }

        routes: list[dict[str, Any]] = []
        for route in getattr(floor_plan, "cable_routes", None) or []:
            subsystem = _normalize_text(getattr(route, "subsystem_type", None), "sps")
            route_id = int(getattr(route, "id", 0) or 0)
            route_key = f"route:{route_id}" if route_id else f"{subsystem}:{len(routes) + 1}"
            target_refs: list[str] = []
            target_device_ids: list[int] = []
            target_groups: set[str] = set()
            for raw_device_id in getattr(route, "device_ids", None) or []:
                try:
                    device_id = int(raw_device_id)
                except (TypeError, ValueError):
                    continue
                device_ref = device_index.get((subsystem, device_id))
                if not device_ref:
                    continue
                target_refs.append(device_ref["label"])
                target_device_ids.append(device_id)
                target_groups.add(device_ref["group_key"])
            for group_key in target_groups:
                if group_key in zone_payloads:
                    zone_payloads[group_key]["route_keys"].add(route_key)
                if group_key == soue_floor_key:
                    soue_floor_group["route_keys"].add(route_key)
            routes.append(
                {
                    "key": route_key,
                    "subsystem": subsystem,
                    "instrument_id": getattr(route, "instrument_id", None),
                    "label": _loop_label("СОУЭ" if subsystem == "soue" else "СПС", route),
                    "length_m": getattr(route, "length_m", None),
                    "target_group_keys": sorted(target_groups),
                    "target_device_ids": target_device_ids,
                    "target_refs": target_refs,
                }
            )

        resolved_zones = list(zone_payloads.values())
        if soue_floor_group["soue_counts"]:
            resolved_zones.append(soue_floor_group)

        floor_payloads.append(
            {
                "id": getattr(floor_plan, "id", None),
                "floor_number": getattr(floor_plan, "floor_number", None),
                "title": _floor_label(floor_plan),
                "building_label": _building_label(project, floor_plan),
                "zones": [_finalize_group_payload(group) for group in resolved_zones],
                "routes": routes,
            }
        )

    return {
        "page_title": "Структурная схема СПС и СОУЭ",
        "facility": _normalize_text(getattr(project, "facility", None), "Объект"),
        "project_code": _normalize_text(getattr(project, "code", None)),
        "floors": floor_payloads,
        "instruments": list(instruments.values()),
        "equipment_totals": sorted(
            equipment_totals.values(),
            key=lambda item: (str(item.get("category") or ""), str(item.get("name") or "")),
        ),
    }


def _finalize_group_payload(group: dict[str, Any]) -> dict[str, Any]:
    def finalize_items(count_key: str, item_key: str) -> list[dict[str, Any]]:
        counts = group.get(count_key) or {}
        items = group.get(item_key) or {}
        return [
            {
                **items.get(key, {"label": key, "category": "other"}),
                "quantity": int(quantity),
            }
            for key, quantity in counts.items()
            if int(quantity) > 0
        ]

    return {
        "key": group["key"],
        "title": group["title"],
        "zone_number": group.get("zone_number"),
        "area_sqm": group.get("area_sqm"),
        "room_count": group.get("room_count"),
        "sps_items": finalize_items("sps_counts", "sps_items"),
        "soue_items": finalize_items("soue_counts", "soue_items"),
        "route_keys": sorted(group.get("route_keys") or []),
    }
