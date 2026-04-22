"""Equipment specification generation and override helpers."""

from __future__ import annotations

from copy import deepcopy
import math
from typing import Any


DEFAULT_EQUIPMENT_SPECIFICATION_PAGE_TITLE = "Спецификация используемого оборудования"
DEFAULT_EQUIPMENT_SPECIFICATION_COLUMN_HEADERS = [
    "Позиция",
    "Наименование и\nтехническая характеристика",
    "Тип, марка,\nобозначение документа,\nопросного листа",
    "Код оборудования,\nизделия,\nматериала",
    "Производитель",
    "Единица\nизмерения",
    "Количество",
    "Масса\nединицы,\nкг",
    "Примечание",
]

SPECIFICATION_EDITABLE_ROW_FIELDS = (
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

SECTION_KEY_KIPIA = "kipia"
SECTION_KEY_FIRE_RESISTANT_CABLE_LINE = "fire_resistant_cable_line"

FIRE_ALARM_ROLE_BY_DEVICE_TYPE = {
    "linear_detector": "sps_linear_detector",
    "smoke_detector": "sps_smoke_detector",
    "heat_detector": "sps_heat_detector",
    "manual_call_point": "sps_manual_call_point",
}

SOUE_ROLE_BY_DEVICE_TYPE = {
    "siren": "soue_siren",
    "exit_sign": "soue_exit_sign",
    "speech_device": "soue_speech_device",
}

INSTRUMENT_FALLBACK_ROLES = (
    "common_instrument",
    "common_keyboard",
    "common_other",
)

KIPIA_CATEGORY_ORDER = {
    "instrument": 10,
    "keyboard": 20,
    "smoke": 30,
    "heat": 40,
    "linear": 50,
    "manual": 60,
    "siren": 70,
    "exit_sign": 80,
    "speech": 90,
    "other": 100,
}

CABLE_SECTION_CATEGORY_ORDER = {
    "cable": 10,
    "mounting": 20,
}


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _format_decimal(value: float, precision: int = 2) -> str:
    text = f"{float(value):.{precision}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _format_count(value: float) -> str:
    if abs(value - round(value)) <= 1e-9:
        return str(int(round(value)))
    return _format_decimal(value, precision=2)


def _format_cable_length(value: float) -> str:
    return _format_decimal(value, precision=2)


def _get_numeric_spec(equipment, field_name: str) -> float | None:
    specs = getattr(equipment, "specs", None) or {}
    value = specs.get(field_name)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _get_mounting_pack_count(equipment, total_cable_length_m: float) -> float | None:
    pack_quantity = _get_numeric_spec(equipment, "pack_quantity")
    mounting_spacing_m = _get_numeric_spec(equipment, "mounting_spacing_m")
    if pack_quantity is None or mounting_spacing_m is None:
        return None
    if pack_quantity <= 0 or mounting_spacing_m <= 0:
        return None
    if total_cable_length_m <= 0:
        return 0.0
    pieces_required = total_cable_length_m / mounting_spacing_m
    return float(math.ceil(pieces_required / pack_quantity))


def _get_addressing_suffix(equipment) -> str:
    specs = getattr(equipment, "specs", None) or {}
    mode = specs.get("addressing_mode")
    if mode == "addressable":
        return " адресный"
    if mode == "non_addressable":
        return " безадресный"
    return ""


def _get_instrument_technical_name(equipment) -> str:
    specs = getattr(equipment, "specs", None) or {}
    subtype = specs.get("instrument_subtype")
    mapping = {
        "security_fire_control_panel": "Прибор приемно-контрольный охранно-пожарный",
        "control_and_management_console": "Пульт контроля и управления",
        "indication_unit": "Блок индикации",
    }
    return mapping.get(subtype, _normalize_text(getattr(equipment, "name", "")).strip() or "Прибор")


def get_equipment_technical_name(equipment) -> str:
    category = str(getattr(equipment, "category", "") or "")
    if category == "instrument":
        return _get_instrument_technical_name(equipment)
    if category == "smoke":
        return f"Извещатель пожарный дымовой{_get_addressing_suffix(equipment)}"
    if category == "heat":
        return f"Извещатель пожарный тепловой{_get_addressing_suffix(equipment)}"
    if category == "linear":
        return f"Извещатель пожарный дымовой линейный{_get_addressing_suffix(equipment)}"
    if category == "manual":
        return f"Извещатель противопожарный ручной{_get_addressing_suffix(equipment)}"
    if category == "siren":
        return "Оповещатель охранно-пожарный звуковой"
    if category == "exit_sign":
        return "Оповещатель охранно-пожарный световой (табло)"
    if category == "speech":
        return "Оповещатель речевой"
    if category == "cable":
        return "Кабель огнестойкий"
    if category == "mounting":
        return _normalize_text(getattr(equipment, "name", ""))
    return _normalize_text(getattr(equipment, "name", ""))


def _get_floor_label(floor_plan) -> str:
    floor_name = _normalize_text(getattr(floor_plan, "name", "")).strip()
    if floor_name:
        return floor_name
    floor_number = getattr(floor_plan, "floor_number", None)
    if floor_number is not None:
        return f"Этаж {floor_number}"
    return "План"


def _build_warning(floor_plan, element_kind: str, element_id: Any, reason: str) -> str:
    floor_label = _get_floor_label(floor_plan)
    return f"{floor_label}: {element_kind} #{element_id} не включён в спецификацию: {reason}"


def _resolve_fire_alarm_equipment(floor_plan, alarm, selection_map: dict[str, Any]) -> tuple[Any | None, str | None]:
    equipment = getattr(alarm, "equipment", None)
    if equipment is not None:
        return equipment, None
    role_key = FIRE_ALARM_ROLE_BY_DEVICE_TYPE.get(str(getattr(alarm, "device_type", "") or ""))
    if role_key and selection_map.get(role_key) is not None:
        return selection_map[role_key], None
    return None, _build_warning(floor_plan, "элемент СПС", getattr(alarm, "id", "—"), "не выбрано оборудование проекта")


def _resolve_soue_equipment(floor_plan, device, selection_map: dict[str, Any]) -> tuple[Any | None, str | None]:
    equipment = getattr(device, "equipment", None)
    if equipment is not None:
        return equipment, None
    role_key = SOUE_ROLE_BY_DEVICE_TYPE.get(str(getattr(device, "device_type", "") or ""))
    if role_key and selection_map.get(role_key) is not None:
        return selection_map[role_key], None
    return None, _build_warning(floor_plan, "элемент СОУЭ", getattr(device, "id", "—"), "не выбрано оборудование проекта")


def _resolve_instrument_equipment(floor_plan, instrument, selection_map: dict[str, Any]) -> tuple[Any | None, str | None]:
    equipment = getattr(instrument, "equipment", None)
    if equipment is not None:
        return equipment, None
    candidates = {
        candidate.id: candidate
        for role_key in INSTRUMENT_FALLBACK_ROLES
        if (candidate := selection_map.get(role_key)) is not None
    }
    if len(candidates) == 1:
        return next(iter(candidates.values())), None
    if len(candidates) > 1:
        reason = "для прибора есть несколько возможных соответствий в проекте"
    else:
        reason = "не выбрано оборудование проекта"
    return None, _build_warning(floor_plan, "прибор", getattr(instrument, "id", "—"), reason)


def _new_row(
    source_key: str,
    equipment,
    *,
    quantity_value: float | None,
    section_key: str,
    source_order: int,
) -> dict[str, Any]:
    category = str(getattr(equipment, "category", "") or "")
    unit = "м." if category == "cable" else "шт."
    return {
        "source_key": source_key,
        "position": "",
        "technical_name": get_equipment_technical_name(equipment),
        "type_mark": _normalize_text(getattr(equipment, "name", "")),
        "code": "",
        "manufacturer": _normalize_text(getattr(equipment, "manufacturer", "")),
        "unit": unit,
        "quantity": "",
        "unit_mass_kg": "",
        "note": _normalize_text(getattr(equipment, "notes", "")),
        "_quantity_value": quantity_value,
        "_section_key": section_key,
        "_source_order": source_order,
        "_category": category,
        "_sort_name": _normalize_text(getattr(equipment, "name", "")).lower(),
        "_equipment_id": getattr(equipment, "id", 0) or 0,
    }


def _add_piece_count_row(rows: dict[str, dict[str, Any]], source_key: str, equipment, *, source_order: int) -> None:
    row = rows.get(source_key)
    if row is None:
        row = _new_row(
            source_key,
            equipment,
            quantity_value=0.0,
            section_key=SECTION_KEY_KIPIA,
            source_order=source_order,
        )
        rows[source_key] = row
    row["_quantity_value"] = float(row["_quantity_value"] or 0.0) + 1.0


def _add_cable_length_row(rows: dict[str, dict[str, Any]], source_key: str, equipment, *, length_m: float, source_order: int) -> None:
    row = rows.get(source_key)
    if row is None:
        row = _new_row(
            source_key,
            equipment,
            quantity_value=0.0,
            section_key=SECTION_KEY_FIRE_RESISTANT_CABLE_LINE,
            source_order=source_order,
        )
        rows[source_key] = row
    row["_quantity_value"] = float(row["_quantity_value"] or 0.0) + max(0.0, float(length_m or 0.0))


def _add_mounting_row(
    rows: dict[str, dict[str, Any]],
    source_key: str,
    equipment,
    *,
    quantity_value: float | None,
) -> None:
    if source_key in rows:
        rows[source_key]["_quantity_value"] = quantity_value
        return
    rows[source_key] = _new_row(
        source_key,
        equipment,
        quantity_value=quantity_value,
        section_key=SECTION_KEY_FIRE_RESISTANT_CABLE_LINE,
        source_order=CABLE_SECTION_CATEGORY_ORDER.get("mounting", 999),
    )


def _finalize_rows(rows: dict[str, dict[str, Any]], *, section_key: str) -> list[dict[str, Any]]:
    category_order_map = KIPIA_CATEGORY_ORDER if section_key == SECTION_KEY_KIPIA else CABLE_SECTION_CATEGORY_ORDER
    finalized = sorted(
        rows.values(),
        key=lambda row: (
            row["_source_order"],
            category_order_map.get(row["_category"], 999),
            row["_sort_name"],
            row["_equipment_id"],
        ),
    )
    result: list[dict[str, Any]] = []
    for row in finalized:
        quantity_value = row.pop("_quantity_value", None)
        row.pop("_section_key", None)
        row.pop("_source_order", None)
        row.pop("_category", None)
        row.pop("_sort_name", None)
        row.pop("_equipment_id", None)
        if quantity_value is None:
            row["quantity"] = ""
        elif row["unit"] == "м.":
            row["quantity"] = _format_cable_length(float(quantity_value))
        else:
            row["quantity"] = _format_count(float(quantity_value))
        result.append(row)
    return result


def build_project_equipment_specification(project, floor_plans: list[Any]) -> dict[str, Any]:
    selection_map = {
        row.role_key: row.equipment
        for row in (getattr(project, "equipment_selections", None) or [])
        if getattr(row, "equipment", None) is not None
    }
    linked_mounting_items = [
        link.equipment
        for link in (getattr(project, "equipment_links", None) or [])
        if getattr(link, "equipment", None) is not None and getattr(link.equipment, "category", None) == "mounting"
    ]
    kipia_rows: dict[str, dict[str, Any]] = {}
    cable_rows: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    total_cable_length_m = 0.0

    for floor_plan in floor_plans:
        for instrument in getattr(floor_plan, "signal_instruments", None) or []:
            equipment, warning = _resolve_instrument_equipment(floor_plan, instrument, selection_map)
            if warning:
                warnings.append(warning)
            if equipment is not None:
                _add_piece_count_row(
                    kipia_rows,
                    f"instrument:{equipment.id}",
                    equipment,
                    source_order=KIPIA_CATEGORY_ORDER.get(getattr(equipment, "category", "other"), 999),
                )

        for alarm in getattr(floor_plan, "fire_alarms", None) or []:
            equipment, warning = _resolve_fire_alarm_equipment(floor_plan, alarm, selection_map)
            if warning:
                warnings.append(warning)
            if equipment is not None:
                _add_piece_count_row(
                    kipia_rows,
                    f"fire_alarm:{equipment.id}",
                    equipment,
                    source_order=KIPIA_CATEGORY_ORDER.get(getattr(equipment, "category", "other"), 999),
                )

        for device in getattr(floor_plan, "soue_devices", None) or []:
            equipment, warning = _resolve_soue_equipment(floor_plan, device, selection_map)
            if warning:
                warnings.append(warning)
            if equipment is not None:
                _add_piece_count_row(
                    kipia_rows,
                    f"soue:{equipment.id}",
                    equipment,
                    source_order=KIPIA_CATEGORY_ORDER.get(getattr(equipment, "category", "other"), 999),
                )

        for route in getattr(floor_plan, "cable_routes", None) or []:
            route_length = float(getattr(route, "length_m", 0.0) or 0.0)
            if route_length <= 0:
                continue
            subsystem_type = str(getattr(route, "subsystem_type", "") or "sps")
            role_key = "soue_cable" if subsystem_type == "soue" else "sps_cable"
            equipment = selection_map.get(role_key)
            if equipment is None:
                warnings.append(
                    _build_warning(
                        floor_plan,
                        "кабельная линия",
                        getattr(route, "id", "—"),
                        "не выбран кабель проекта для подсистемы",
                    )
                )
                continue
            _add_cable_length_row(
                cable_rows,
                f"cable:{equipment.id}",
                equipment,
                length_m=route_length,
                source_order=CABLE_SECTION_CATEGORY_ORDER.get("cable", 999),
            )
            total_cable_length_m += max(0.0, route_length)

    for equipment in linked_mounting_items:
        mounting_quantity = _get_mounting_pack_count(equipment, total_cable_length_m)
        if mounting_quantity is None and total_cable_length_m > 0:
            warnings.append(
                (
                    f'Крепление "{getattr(equipment, "name", "")}" не включено в автоподсчет: '
                    'заполните поля "Кол-во штук" и "Кратность крепления, м".'
                )
            )
        _add_mounting_row(
            cable_rows,
            f"mounting:{equipment.id}",
            equipment,
            quantity_value=mounting_quantity,
        )

    kipia_final = _finalize_rows(kipia_rows, section_key=SECTION_KEY_KIPIA)
    cable_final = _finalize_rows(cable_rows, section_key=SECTION_KEY_FIRE_RESISTANT_CABLE_LINE)

    position_counter = 1
    for section_rows in (kipia_final, cable_final):
        for row in section_rows:
            row["position"] = str(position_counter)
            position_counter += 1

    return {
        "project_id": getattr(project, "id", None),
        "page_title": DEFAULT_EQUIPMENT_SPECIFICATION_PAGE_TITLE,
        "column_headers": list(DEFAULT_EQUIPMENT_SPECIFICATION_COLUMN_HEADERS),
        "sections": [
            {
                "key": SECTION_KEY_KIPIA,
                "title": "КИПиА",
                "rows": kipia_final,
            },
            {
                "key": SECTION_KEY_FIRE_RESISTANT_CABLE_LINE,
                "title": "Огнестойкая кабельная линия",
                "rows": cable_final,
            },
        ],
        "warnings": warnings,
    }


def apply_equipment_specification_overrides(specification: dict[str, Any], overrides: dict[str, Any] | None) -> dict[str, Any]:
    result = deepcopy(specification)
    if not isinstance(overrides, dict):
        return result

    page_title = overrides.get("page_title")
    if isinstance(page_title, str):
        result["page_title"] = page_title

    headers = overrides.get("column_headers")
    if isinstance(headers, list) and len(headers) == len(result.get("column_headers") or []):
        result["column_headers"] = [_normalize_text(value) for value in headers]

    section_titles = overrides.get("section_titles") if isinstance(overrides.get("section_titles"), dict) else {}
    row_overrides = overrides.get("rows") if isinstance(overrides.get("rows"), dict) else {}

    for section in result.get("sections") or []:
        if isinstance(section_titles.get(section.get("key")), str):
            section["title"] = section_titles[section["key"]]
        for row in section.get("rows") or []:
            row_override = row_overrides.get(row.get("source_key"))
            if not isinstance(row_override, dict):
                continue
            for field_name in SPECIFICATION_EDITABLE_ROW_FIELDS:
                if field_name in row_override and row_override[field_name] is not None:
                    row[field_name] = _normalize_text(row_override[field_name])
    return result


def extract_equipment_specification_overrides(base_specification: dict[str, Any], updated_specification: dict[str, Any]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}

    if _normalize_text(updated_specification.get("page_title")) != _normalize_text(base_specification.get("page_title")):
        overrides["page_title"] = _normalize_text(updated_specification.get("page_title"))

    updated_headers = updated_specification.get("column_headers")
    base_headers = base_specification.get("column_headers")
    if isinstance(updated_headers, list) and isinstance(base_headers, list):
        normalized_updated_headers = [_normalize_text(value) for value in updated_headers]
        normalized_base_headers = [_normalize_text(value) for value in base_headers]
        if normalized_updated_headers != normalized_base_headers:
            overrides["column_headers"] = normalized_updated_headers

    updated_sections = {
        section.get("key"): section
        for section in (updated_specification.get("sections") or [])
        if isinstance(section, dict) and section.get("key")
    }
    section_titles: dict[str, str] = {}
    row_overrides: dict[str, dict[str, str]] = {}

    for base_section in base_specification.get("sections") or []:
        section_key = base_section.get("key")
        updated_section = updated_sections.get(section_key) or {}
        if _normalize_text(updated_section.get("title")) != _normalize_text(base_section.get("title")):
            section_titles[section_key] = _normalize_text(updated_section.get("title"))

        updated_rows = {
            row.get("source_key"): row
            for row in (updated_section.get("rows") or [])
            if isinstance(row, dict) and row.get("source_key")
        }
        for base_row in base_section.get("rows") or []:
            source_key = base_row.get("source_key")
            updated_row = updated_rows.get(source_key)
            if not isinstance(updated_row, dict):
                continue
            changed_fields: dict[str, str] = {}
            for field_name in SPECIFICATION_EDITABLE_ROW_FIELDS:
                if _normalize_text(updated_row.get(field_name)) != _normalize_text(base_row.get(field_name)):
                    changed_fields[field_name] = _normalize_text(updated_row.get(field_name))
            if changed_fields:
                row_overrides[source_key] = changed_fields

    if section_titles:
        overrides["section_titles"] = section_titles
    if row_overrides:
        overrides["rows"] = row_overrides
    return overrides
