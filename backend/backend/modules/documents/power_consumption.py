"""Power consumption calculation builders and override helpers."""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Any, Callable

from backend.errors import AppError
from backend.modules.documents.specification import (
    _resolve_fire_alarm_equipment,
    _resolve_instrument_equipment,
    _resolve_soue_equipment,
)
from backend.modules.equipment.domain.specs import coerce_current_specs


DEFAULT_POWER_CONSUMPTION_PAGE_TITLE = "Расчет токопотребления системы"
DEFAULT_POWER_CONSUMPTION_TABLE_TITLE = "Расчет токопотребления системы"
DEFAULT_POWER_CONSUMPTION_TABLE_CAPTION = "Таблица 1."
DEFAULT_POWER_CONSUMPTION_INTRODUCTORY_TEXTS = (
    "При отключении сети питания система переходит в режим электропитания от аккумуляторных батарей. "
    "Согласно СП 484.1311500.2020 на объекте необходимо использовать аккумуляторные батареи, "
    "обеспечивающие питание электроприёмников в дежурном режиме в течение 24 ч и в режиме «Тревога» "
    "не менее 1 ч.",
    "Расчёт токопотребления системы показан в таблице 1.",
)

POWER_CONSUMPTION_CATEGORY_ORDER = (
    {
        "key": "instruments",
        "title": "1. Приборы",
        "allowed_categories": {"instrument", "keyboard"},
        "element_attr": "signal_instruments",
        "resolver": _resolve_instrument_equipment,
    },
    {
        "key": "detectors",
        "title": "2. Извещатели",
        "allowed_categories": {"smoke", "heat", "linear", "manual"},
        "element_attr": "fire_alarms",
        "resolver": _resolve_fire_alarm_equipment,
    },
    {
        "key": "notification_devices",
        "title": "3. Оповещатели и устройства коммутационные",
        "allowed_categories": {"siren", "exit_sign", "speech"},
        "element_attr": "soue_devices",
        "resolver": _resolve_soue_equipment,
    },
)

GROUP_KEYS_FOR_INSTRUMENTS_AND_DETECTORS = ("instruments", "detectors")
DEFAULT_STANDBY_OPERATION_TIME_HOURS = Decimal("24")
DEFAULT_ALARM_OPERATION_TIME_HOURS = Decimal("1")
DEFAULT_CORRECTION_FACTOR = Decimal("1.1")
DEFAULT_BATTERY_VOLTAGE = Decimal("12")
DEFAULT_BATTERY_QUANTITY = Decimal("1")

POWER_CONSUMPTION_EDITABLE_TOP_LEVEL_TEXT_FIELDS = (
    "page_title",
    "table_caption",
    "table_title",
)
POWER_CONSUMPTION_EDITABLE_TOP_LEVEL_NUMERIC_FIELDS = (
    "battery_voltage_v",
    "battery_quantity",
)
POWER_CONSUMPTION_EDITABLE_ROW_TEXT_FIELDS = (
    "number",
    "equipment_name",
    "unit",
)
POWER_CONSUMPTION_EDITABLE_ROW_NUMERIC_FIELDS = (
    "quantity",
    "standby_current",
    "alarm_current",
)
POWER_CONSUMPTION_EDITABLE_SUMMARY_VALUE_KEYS = {"operation_time", "correction_factor"}

SUMMARY_ROW_DEFINITIONS = (
    {
        "key": "instruments_and_detectors_total",
        "kind": "summary",
        "label": "I (Итого по токопотреблению приборов и извещателей), А:",
    },
    {
        "key": "notification_total",
        "kind": "summary",
        "label": "I (Итого по токопотреблению оповещателей и устройств коммутационных), А:",
    },
    {
        "key": "overall_total",
        "kind": "summary",
        "label": "I (Итого по токопотреблению), А:",
    },
    {
        "key": "operation_time",
        "kind": "summary",
        "label": "Т (Время работы), час:",
    },
    {
        "key": "capacity",
        "kind": "summary",
        "label": "W=I*T (Итого ёмкость аккумулятора), А/ч:",
    },
    {
        "key": "correction_factor",
        "kind": "summary",
        "label": "Поправочный коэффициент:",
    },
    {
        "key": "corrected_capacity",
        "kind": "summary",
        "label": "Итого с поправочным коэффициентом:",
    },
    {
        "key": "total_capacity",
        "kind": "summary_merged",
        "label": "Wобщ (Общая ёмкость аккумулятора), А/ч:",
    },
)


def _power_override_error(field_path: str, value: Any) -> AppError:
    return AppError(
        400,
        "power_consumption_override_invalid_number",
        f"Invalid numeric value for power consumption calculation at '{field_path}': {value!r}",
    )


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _to_decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value).replace(",", "."))
    except (InvalidOperation, ValueError):
        return None


def _require_decimal(value: Any, field_path: str, *, default: Decimal | None = None) -> Decimal:
    decimal_value = _to_decimal(value)
    if decimal_value is None:
        if default is not None:
            return default
        raise _power_override_error(field_path, value)
    return decimal_value


def _format_decimal(value: Decimal, *, precision: int = 6) -> str:
    text = f"{value:.{precision}f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _format_numeric_value(value: Decimal) -> str:
    return _format_decimal(value)


def _normalize_numeric_text(value: Any, field_path: str, *, default: Decimal | None = None) -> str:
    return _format_numeric_value(_require_decimal(value, field_path, default=default))


def _summary_row_defaults() -> dict[str, dict[str, str]]:
    return {definition["key"]: definition for definition in SUMMARY_ROW_DEFINITIONS}


def _selection_map(project: Any) -> dict[str, Any]:
    return {
        row.role_key: row.equipment
        for row in (getattr(project, "equipment_selections", None) or [])
        if getattr(row, "equipment", None) is not None
    }


def _extract_currents(equipment: Any) -> tuple[Decimal, Decimal] | None:
    category = str(getattr(equipment, "category", "") or "")
    specs = coerce_current_specs(
        category,
        getattr(equipment, "specs", None),
        smoke_addressing=getattr(equipment, "smoke_addressing", None),
        standby_current_ma=getattr(equipment, "standby_current_ma", None),
        alarm_current_ma=getattr(equipment, "alarm_current_ma", None),
    )
    instrument_subtype = str(specs.get("instrument_subtype") or "")

    if category == "instrument" and instrument_subtype == "control_and_management_console":
        console_current = _to_decimal(specs.get("current_12v_a"))
        if console_current is not None:
            return console_current, console_current

    standby_current = _to_decimal(specs.get("standby_current_a"))
    alarm_current = _to_decimal(specs.get("alarm_current_a"))
    if standby_current is None or alarm_current is None:
        return None
    return standby_current, alarm_current


def _new_aggregate_row(group_key: str, equipment: Any, standby_current: Decimal, alarm_current: Decimal) -> dict[str, Any]:
    equipment_id = int(getattr(equipment, "id", 0) or 0)
    return {
        "source_key": f"{group_key}:{equipment_id}",
        "group_key": group_key,
        "equipment_id": equipment_id,
        "equipment_name": _normalize_text(getattr(equipment, "name", "")).strip(),
        "quantity_value": Decimal("0"),
        "standby_current_value": standby_current,
        "alarm_current_value": alarm_current,
        "standby_total_value": Decimal("0"),
        "alarm_total_value": Decimal("0"),
    }


def _finalize_category_rows(group_key: str, rows_by_equipment_id: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    ordered_rows = sorted(
        rows_by_equipment_id.values(),
        key=lambda row: (row["equipment_name"].lower(), row["equipment_id"]),
    )
    finalized: list[dict[str, Any]] = []
    for index, row in enumerate(ordered_rows, start=1):
        quantity_value = row["quantity_value"]
        standby_current_value = row["standby_current_value"]
        alarm_current_value = row["alarm_current_value"]
        standby_total_value = row["standby_total_value"]
        alarm_total_value = row["alarm_total_value"]
        finalized.append(
            {
                "source_key": row["source_key"],
                "group_key": group_key,
                "equipment_id": row["equipment_id"],
                "number": str(index),
                "equipment_name": row["equipment_name"],
                "unit": "шт.",
                "quantity": _format_numeric_value(quantity_value),
                "standby_current": _format_decimal(standby_current_value),
                "alarm_current": _format_decimal(alarm_current_value),
                "standby_total": _format_decimal(standby_total_value),
                "alarm_total": _format_decimal(alarm_total_value),
                "quantity_value": quantity_value,
                "standby_current_value": standby_current_value,
                "alarm_current_value": alarm_current_value,
                "standby_total_value": standby_total_value,
                "alarm_total_value": alarm_total_value,
            }
        )
    return finalized


def _sum_group_values(categories: list[dict[str, Any]], group_keys: tuple[str, ...]) -> tuple[Decimal, Decimal]:
    standby_total = Decimal("0")
    alarm_total = Decimal("0")
    for category in categories:
        if category.get("key") not in group_keys:
            continue
        for row in category.get("rows") or []:
            standby_total += row["standby_total_value"]
            alarm_total += row["alarm_total_value"]
    return standby_total, alarm_total


def _summary_row_map(summary_rows: list[dict[str, Any]] | None) -> dict[str, dict[str, Any]]:
    return {
        row.get("key"): row
        for row in (summary_rows or [])
        if isinstance(row, dict) and row.get("key")
    }


def _build_summary_rows(
    categories: list[dict[str, Any]],
    *,
    labels: dict[str, str] | None = None,
    operation_time_standby: Decimal = DEFAULT_STANDBY_OPERATION_TIME_HOURS,
    operation_time_alarm: Decimal = DEFAULT_ALARM_OPERATION_TIME_HOURS,
    correction_factor_standby: Decimal = DEFAULT_CORRECTION_FACTOR,
    correction_factor_alarm: Decimal = DEFAULT_CORRECTION_FACTOR,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    summary_defaults = _summary_row_defaults()
    summary_labels = {
        key: _normalize_text((labels or {}).get(key) or definition["label"])
        for key, definition in summary_defaults.items()
    }

    instruments_and_detectors_standby, instruments_and_detectors_alarm = _sum_group_values(
        categories,
        GROUP_KEYS_FOR_INSTRUMENTS_AND_DETECTORS,
    )
    notification_standby, notification_alarm = _sum_group_values(categories, ("notification_devices",))
    overall_standby = instruments_and_detectors_standby + notification_standby
    overall_alarm = instruments_and_detectors_alarm + notification_alarm

    capacity_standby = overall_standby * operation_time_standby
    capacity_alarm = overall_alarm * operation_time_alarm
    corrected_capacity_standby = capacity_standby * correction_factor_standby
    corrected_capacity_alarm = capacity_alarm * correction_factor_alarm
    total_capacity = corrected_capacity_standby + corrected_capacity_alarm
    battery_capacity_rounded = int(total_capacity.to_integral_value(rounding=ROUND_CEILING)) if total_capacity else 0

    summary_rows = [
        {
            "key": "instruments_and_detectors_total",
            "kind": "summary",
            "label": summary_labels["instruments_and_detectors_total"],
            "standby_value": instruments_and_detectors_standby,
            "alarm_value": instruments_and_detectors_alarm,
            "standby": _format_decimal(instruments_and_detectors_standby),
            "alarm": _format_decimal(instruments_and_detectors_alarm),
        },
        {
            "key": "notification_total",
            "kind": "summary",
            "label": summary_labels["notification_total"],
            "standby_value": notification_standby,
            "alarm_value": notification_alarm,
            "standby": _format_decimal(notification_standby),
            "alarm": _format_decimal(notification_alarm),
        },
        {
            "key": "overall_total",
            "kind": "summary",
            "label": summary_labels["overall_total"],
            "standby_value": overall_standby,
            "alarm_value": overall_alarm,
            "standby": _format_decimal(overall_standby),
            "alarm": _format_decimal(overall_alarm),
        },
        {
            "key": "operation_time",
            "kind": "summary",
            "label": summary_labels["operation_time"],
            "standby_value": operation_time_standby,
            "alarm_value": operation_time_alarm,
            "standby": _format_numeric_value(operation_time_standby),
            "alarm": _format_numeric_value(operation_time_alarm),
        },
        {
            "key": "capacity",
            "kind": "summary",
            "label": summary_labels["capacity"],
            "standby_value": capacity_standby,
            "alarm_value": capacity_alarm,
            "standby": _format_decimal(capacity_standby),
            "alarm": _format_decimal(capacity_alarm),
        },
        {
            "key": "correction_factor",
            "kind": "summary",
            "label": summary_labels["correction_factor"],
            "standby_value": correction_factor_standby,
            "alarm_value": correction_factor_alarm,
            "standby": _format_numeric_value(correction_factor_standby),
            "alarm": _format_numeric_value(correction_factor_alarm),
        },
        {
            "key": "corrected_capacity",
            "kind": "summary",
            "label": summary_labels["corrected_capacity"],
            "standby_value": corrected_capacity_standby,
            "alarm_value": corrected_capacity_alarm,
            "standby": _format_decimal(corrected_capacity_standby),
            "alarm": _format_decimal(corrected_capacity_alarm),
        },
        {
            "key": "total_capacity",
            "kind": "summary_merged",
            "label": summary_labels["total_capacity"],
            "value": _format_decimal(total_capacity),
            "value_decimal": total_capacity,
        },
    ]

    computed_values = {
        "instruments_and_detectors_standby": instruments_and_detectors_standby,
        "instruments_and_detectors_alarm": instruments_and_detectors_alarm,
        "notification_standby": notification_standby,
        "notification_alarm": notification_alarm,
        "overall_standby": overall_standby,
        "overall_alarm": overall_alarm,
        "operation_time_standby": operation_time_standby,
        "operation_time_alarm": operation_time_alarm,
        "capacity_standby": capacity_standby,
        "capacity_alarm": capacity_alarm,
        "correction_factor_standby": correction_factor_standby,
        "correction_factor_alarm": correction_factor_alarm,
        "corrected_capacity_standby": corrected_capacity_standby,
        "corrected_capacity_alarm": corrected_capacity_alarm,
        "total_capacity": total_capacity,
        "battery_capacity_rounded": battery_capacity_rounded,
    }
    return summary_rows, computed_values


def _append_equipment_row(
    aggregates: dict[str, dict[int, dict[str, Any]]],
    *,
    group_key: str,
    equipment: Any,
    standby_current: Decimal,
    alarm_current: Decimal,
) -> None:
    equipment_id = int(getattr(equipment, "id", 0) or 0)
    group_rows = aggregates.setdefault(group_key, {})
    row = group_rows.get(equipment_id)
    if row is None:
        row = _new_aggregate_row(group_key, equipment, standby_current, alarm_current)
        group_rows[equipment_id] = row
    row["quantity_value"] += Decimal("1")
    row["standby_total_value"] += standby_current
    row["alarm_total_value"] += alarm_current


def _collect_category_rows(project: Any, floor_plans: list[Any]) -> list[dict[str, Any]]:
    selection_map = _selection_map(project)
    aggregates: dict[str, dict[int, dict[str, Any]]] = {
        definition["key"]: {}
        for definition in POWER_CONSUMPTION_CATEGORY_ORDER
    }

    for floor_plan in floor_plans:
        for definition in POWER_CONSUMPTION_CATEGORY_ORDER:
            group_key = definition["key"]
            allowed_categories = definition["allowed_categories"]
            element_attr = definition["element_attr"]
            resolver: Callable[[Any, Any, dict[str, Any]], tuple[Any | None, str | None]] = definition["resolver"]

            for element in getattr(floor_plan, element_attr, None) or []:
                equipment, _warning = resolver(floor_plan, element, selection_map)
                if equipment is None:
                    continue
                category = str(getattr(equipment, "category", "") or "")
                if category not in allowed_categories:
                    continue
                currents = _extract_currents(equipment)
                if currents is None:
                    continue
                standby_current, alarm_current = currents
                _append_equipment_row(
                    aggregates,
                    group_key=group_key,
                    equipment=equipment,
                    standby_current=standby_current,
                    alarm_current=alarm_current,
                )

    categories: list[dict[str, Any]] = []
    for definition in POWER_CONSUMPTION_CATEGORY_ORDER:
        group_key = definition["key"]
        categories.append(
            {
                "key": group_key,
                "title": definition["title"],
                "rows": _finalize_category_rows(group_key, aggregates.get(group_key, {})),
            }
        )
    return categories


def _recalculate_power_consumption_payload(calculation: dict[str, Any]) -> dict[str, Any]:
    categories = calculation.get("categories") or []
    for category in categories:
        category["title"] = _normalize_text(category.get("title"))
        for row in category.get("rows") or []:
            source_key = _normalize_text(row.get("source_key"))
            row["source_key"] = source_key
            row["number"] = _normalize_text(row.get("number"))
            row["equipment_name"] = _normalize_text(row.get("equipment_name")).strip()
            row["unit"] = _normalize_text(row.get("unit")).strip()

            quantity_value = _require_decimal(
                row.get("quantity"),
                f"rows.{source_key}.quantity",
                default=Decimal("0"),
            )
            standby_current_value = _require_decimal(
                row.get("standby_current"),
                f"rows.{source_key}.standby_current",
                default=Decimal("0"),
            )
            alarm_current_value = _require_decimal(
                row.get("alarm_current"),
                f"rows.{source_key}.alarm_current",
                default=Decimal("0"),
            )
            standby_total_value = quantity_value * standby_current_value
            alarm_total_value = quantity_value * alarm_current_value

            row["quantity_value"] = quantity_value
            row["standby_current_value"] = standby_current_value
            row["alarm_current_value"] = alarm_current_value
            row["standby_total_value"] = standby_total_value
            row["alarm_total_value"] = alarm_total_value

            row["quantity"] = _format_numeric_value(quantity_value)
            row["standby_current"] = _format_decimal(standby_current_value)
            row["alarm_current"] = _format_decimal(alarm_current_value)
            row["standby_total"] = _format_decimal(standby_total_value)
            row["alarm_total"] = _format_decimal(alarm_total_value)

    summary_rows = calculation.get("summary_rows") or []
    summary_map = _summary_row_map(summary_rows)
    labels = {
        definition["key"]: _normalize_text(
            (summary_map.get(definition["key"]) or {}).get("label") or definition["label"]
        )
        for definition in SUMMARY_ROW_DEFINITIONS
    }
    operation_time_row = summary_map.get("operation_time") or {}
    correction_factor_row = summary_map.get("correction_factor") or {}
    operation_time_standby = _require_decimal(
        operation_time_row.get("standby"),
        "summary_rows.operation_time.standby",
        default=DEFAULT_STANDBY_OPERATION_TIME_HOURS,
    )
    operation_time_alarm = _require_decimal(
        operation_time_row.get("alarm"),
        "summary_rows.operation_time.alarm",
        default=DEFAULT_ALARM_OPERATION_TIME_HOURS,
    )
    correction_factor_standby = _require_decimal(
        correction_factor_row.get("standby"),
        "summary_rows.correction_factor.standby",
        default=DEFAULT_CORRECTION_FACTOR,
    )
    correction_factor_alarm = _require_decimal(
        correction_factor_row.get("alarm"),
        "summary_rows.correction_factor.alarm",
        default=DEFAULT_CORRECTION_FACTOR,
    )
    next_summary_rows, computed_values = _build_summary_rows(
        categories,
        labels=labels,
        operation_time_standby=operation_time_standby,
        operation_time_alarm=operation_time_alarm,
        correction_factor_standby=correction_factor_standby,
        correction_factor_alarm=correction_factor_alarm,
    )
    calculation["summary_rows"] = next_summary_rows

    battery_voltage_value = _require_decimal(
        calculation.get("battery_voltage_v"),
        "battery_voltage_v",
        default=DEFAULT_BATTERY_VOLTAGE,
    )
    battery_quantity_value = _require_decimal(
        calculation.get("battery_quantity"),
        "battery_quantity",
        default=DEFAULT_BATTERY_QUANTITY,
    )
    calculation["battery_voltage_v"] = _format_numeric_value(battery_voltage_value)
    calculation["battery_quantity"] = _format_numeric_value(battery_quantity_value)
    calculation["battery_capacity_ah"] = int(computed_values["battery_capacity_rounded"])
    calculation["final_text"] = (
        "Исходя из расчетов принимаем использование аккумуляторной батареи "
        f"{calculation['battery_voltage_v']} В, {calculation['battery_capacity_ah']} Ач - {calculation['battery_quantity']} шт."
    )
    calculation["computed_values"] = {
        key: float(value) if isinstance(value, Decimal) else value
        for key, value in computed_values.items()
    }
    return calculation


def build_project_power_consumption_calculation(project: Any, floor_plans: list[Any]) -> dict[str, Any]:
    calculation = {
        "project_id": getattr(project, "id", None),
        "page_title": DEFAULT_POWER_CONSUMPTION_PAGE_TITLE,
        "introductory_texts": list(DEFAULT_POWER_CONSUMPTION_INTRODUCTORY_TEXTS),
        "table_caption": DEFAULT_POWER_CONSUMPTION_TABLE_CAPTION,
        "table_title": DEFAULT_POWER_CONSUMPTION_TABLE_TITLE,
        "categories": _collect_category_rows(project, floor_plans),
        "summary_rows": [],
        "battery_voltage_v": _format_numeric_value(DEFAULT_BATTERY_VOLTAGE),
        "battery_capacity_ah": 0,
        "battery_quantity": _format_numeric_value(DEFAULT_BATTERY_QUANTITY),
        "final_text": "",
        "computed_values": {},
    }
    return _recalculate_power_consumption_payload(calculation)


def apply_power_consumption_overrides(
    calculation: dict[str, Any],
    overrides: dict[str, Any] | None,
) -> dict[str, Any]:
    result = deepcopy(calculation)
    if not isinstance(overrides, dict):
        return result

    for field_name in POWER_CONSUMPTION_EDITABLE_TOP_LEVEL_TEXT_FIELDS:
        if field_name in overrides and overrides[field_name] is not None:
            result[field_name] = _normalize_text(overrides[field_name])

    introductory_texts = overrides.get("introductory_texts")
    if isinstance(introductory_texts, list):
        result["introductory_texts"] = [_normalize_text(value) for value in introductory_texts]

    for field_name in POWER_CONSUMPTION_EDITABLE_TOP_LEVEL_NUMERIC_FIELDS:
        if field_name in overrides and overrides[field_name] not in (None, ""):
            result[field_name] = _normalize_text(overrides[field_name])

    category_titles = overrides.get("category_titles") if isinstance(overrides.get("category_titles"), dict) else {}
    row_overrides = overrides.get("rows") if isinstance(overrides.get("rows"), dict) else {}
    summary_row_overrides = overrides.get("summary_rows") if isinstance(overrides.get("summary_rows"), dict) else {}

    for category in result.get("categories") or []:
        if isinstance(category_titles.get(category.get("key")), str):
            category["title"] = category_titles[category["key"]]
        for row in category.get("rows") or []:
            row_override = row_overrides.get(row.get("source_key"))
            if not isinstance(row_override, dict):
                continue
            for field_name in (*POWER_CONSUMPTION_EDITABLE_ROW_TEXT_FIELDS, *POWER_CONSUMPTION_EDITABLE_ROW_NUMERIC_FIELDS):
                if field_name in row_override and row_override[field_name] is not None:
                    row[field_name] = _normalize_text(row_override[field_name])

    for summary_row in result.get("summary_rows") or []:
        row_override = summary_row_overrides.get(summary_row.get("key"))
        if not isinstance(row_override, dict):
            continue
        if "label" in row_override and row_override["label"] is not None:
            summary_row["label"] = _normalize_text(row_override["label"])
        if summary_row.get("key") in POWER_CONSUMPTION_EDITABLE_SUMMARY_VALUE_KEYS:
            for field_name in ("standby", "alarm"):
                if field_name in row_override and row_override[field_name] is not None:
                    summary_row[field_name] = _normalize_text(row_override[field_name])

    return _recalculate_power_consumption_payload(result)


def extract_power_consumption_overrides(
    base_calculation: dict[str, Any],
    updated_calculation: dict[str, Any],
) -> dict[str, Any]:
    overrides: dict[str, Any] = {}

    for field_name in POWER_CONSUMPTION_EDITABLE_TOP_LEVEL_TEXT_FIELDS:
        if _normalize_text(updated_calculation.get(field_name)) != _normalize_text(base_calculation.get(field_name)):
            overrides[field_name] = _normalize_text(updated_calculation.get(field_name))

    updated_introductory_texts = [_normalize_text(value) for value in (updated_calculation.get("introductory_texts") or [])]
    base_introductory_texts = [_normalize_text(value) for value in (base_calculation.get("introductory_texts") or [])]
    if updated_introductory_texts != base_introductory_texts:
        overrides["introductory_texts"] = updated_introductory_texts

    for field_name in POWER_CONSUMPTION_EDITABLE_TOP_LEVEL_NUMERIC_FIELDS:
        updated_value = _normalize_numeric_text(
            updated_calculation.get(field_name),
            field_name,
            default=DEFAULT_BATTERY_VOLTAGE if field_name == "battery_voltage_v" else DEFAULT_BATTERY_QUANTITY,
        )
        base_value = _normalize_numeric_text(
            base_calculation.get(field_name),
            field_name,
            default=DEFAULT_BATTERY_VOLTAGE if field_name == "battery_voltage_v" else DEFAULT_BATTERY_QUANTITY,
        )
        if updated_value != base_value:
            overrides[field_name] = updated_value

    updated_categories = {
        category.get("key"): category
        for category in (updated_calculation.get("categories") or [])
        if isinstance(category, dict) and category.get("key")
    }
    category_titles: dict[str, str] = {}
    row_overrides: dict[str, dict[str, str]] = {}

    for base_category in base_calculation.get("categories") or []:
        category_key = base_category.get("key")
        updated_category = updated_categories.get(category_key) or {}
        if _normalize_text(updated_category.get("title")) != _normalize_text(base_category.get("title")):
            category_titles[category_key] = _normalize_text(updated_category.get("title"))

        updated_rows = {
            row.get("source_key"): row
            for row in (updated_category.get("rows") or [])
            if isinstance(row, dict) and row.get("source_key")
        }
        for base_row in base_category.get("rows") or []:
            source_key = base_row.get("source_key")
            updated_row = updated_rows.get(source_key)
            if not isinstance(updated_row, dict):
                continue
            changed_fields: dict[str, str] = {}
            for field_name in POWER_CONSUMPTION_EDITABLE_ROW_TEXT_FIELDS:
                if _normalize_text(updated_row.get(field_name)) != _normalize_text(base_row.get(field_name)):
                    changed_fields[field_name] = _normalize_text(updated_row.get(field_name))
            for field_name in POWER_CONSUMPTION_EDITABLE_ROW_NUMERIC_FIELDS:
                updated_value = _normalize_numeric_text(updated_row.get(field_name), f"rows.{source_key}.{field_name}")
                base_value = _normalize_numeric_text(base_row.get(field_name), f"rows.{source_key}.{field_name}")
                if updated_value != base_value:
                    changed_fields[field_name] = updated_value
            if changed_fields:
                row_overrides[source_key] = changed_fields

    updated_summary_rows = {
        row.get("key"): row
        for row in (updated_calculation.get("summary_rows") or [])
        if isinstance(row, dict) and row.get("key")
    }
    summary_row_overrides: dict[str, dict[str, str]] = {}
    for base_summary_row in base_calculation.get("summary_rows") or []:
        summary_key = base_summary_row.get("key")
        updated_summary_row = updated_summary_rows.get(summary_key)
        if not isinstance(updated_summary_row, dict):
            continue
        changed_fields: dict[str, str] = {}
        if _normalize_text(updated_summary_row.get("label")) != _normalize_text(base_summary_row.get("label")):
            changed_fields["label"] = _normalize_text(updated_summary_row.get("label"))
        if summary_key in POWER_CONSUMPTION_EDITABLE_SUMMARY_VALUE_KEYS:
            for field_name in ("standby", "alarm"):
                updated_value = _normalize_numeric_text(
                    updated_summary_row.get(field_name),
                    f"summary_rows.{summary_key}.{field_name}",
                )
                base_value = _normalize_numeric_text(
                    base_summary_row.get(field_name),
                    f"summary_rows.{summary_key}.{field_name}",
                )
                if updated_value != base_value:
                    changed_fields[field_name] = updated_value
        if changed_fields:
            summary_row_overrides[summary_key] = changed_fields

    if category_titles:
        overrides["category_titles"] = category_titles
    if row_overrides:
        overrides["rows"] = row_overrides
    if summary_row_overrides:
        overrides["summary_rows"] = summary_row_overrides
    return overrides
