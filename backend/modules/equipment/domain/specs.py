"""Normalization helpers for category-specific equipment specs."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from backend.modules.equipment.domain.constants import (
    INSTRUMENT_SUBTYPE_VALUES,
    SMOKE_ADDRESSING_VALUES,
)


@dataclass(frozen=True)
class SpecFieldDefinition:
    """Defines one allowed field in the equipment specs payload."""

    kind: str
    required: bool = False
    values: tuple[str, ...] | None = None
    copy_from: str | None = None
    minimum: float | None = None


class EquipmentSpecsValidationError(ValueError):
    """Raised when the category-specific specs payload is invalid."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


LEGACY_INSTRUMENT_SUBTYPE_ALIASES: dict[str, str] = {
    "control_panel": "security_fire_control_panel",
}

LEGACY_INSTRUMENT_SPEC_KEYS: tuple[str, ...] = (
    "supported_sps_mode",
    "power_dc_v",
    "controller_current_12v_ma",
    "controller_current_24v_ma",
    "shs_count",
    "zone_count",
)

CATEGORY_SPEC_DEFINITIONS: dict[str, dict[str, SpecFieldDefinition]] = {
    "smoke": {
        "addressing_mode": SpecFieldDefinition("enum", required=True, values=SMOKE_ADDRESSING_VALUES),
        "loop_voltage_v": SpecFieldDefinition("voltage", required=True),
        "standby_current_a": SpecFieldDefinition("float", required=True),
        "alarm_current_a": SpecFieldDefinition("float", copy_from="standby_current_a"),
    },
    "heat": {
        "addressing_mode": SpecFieldDefinition("enum", required=True, values=SMOKE_ADDRESSING_VALUES),
        "loop_voltage_v": SpecFieldDefinition("voltage", required=True),
        "standby_current_a": SpecFieldDefinition("float", required=True),
        "alarm_current_a": SpecFieldDefinition("float", copy_from="standby_current_a"),
    },
    "linear": {
        "addressing_mode": SpecFieldDefinition("enum", required=True, values=SMOKE_ADDRESSING_VALUES),
        "loop_voltage_v": SpecFieldDefinition("voltage", required=True),
        "standby_current_a": SpecFieldDefinition("float", required=True),
        "alarm_current_a": SpecFieldDefinition("float", copy_from="standby_current_a"),
        "range_m": SpecFieldDefinition("float", required=True),
    },
    "manual": {
        "addressing_mode": SpecFieldDefinition("enum", required=True, values=SMOKE_ADDRESSING_VALUES),
        "loop_voltage_v": SpecFieldDefinition("voltage", required=True),
        "standby_current_a": SpecFieldDefinition("float", required=True),
        "alarm_current_a": SpecFieldDefinition("float", copy_from="standby_current_a"),
    },
    "exit_sign": {
        "supply_voltage_v": SpecFieldDefinition("voltage", required=True),
        "standby_current_a": SpecFieldDefinition("float", required=True),
        "alarm_current_a": SpecFieldDefinition("float", copy_from="standby_current_a"),
    },
    "siren": {
        "sound_pressure_db": SpecFieldDefinition("float", required=True),
        "supply_voltage_v": SpecFieldDefinition("voltage", required=True),
        "standby_current_a": SpecFieldDefinition("float", required=True),
        "alarm_current_a": SpecFieldDefinition("float", copy_from="standby_current_a"),
    },
    "cable": {
        "conductors_count": SpecFieldDefinition("int", required=True),
        "conductor_type": SpecFieldDefinition("text", required=True),
        "working_voltage_max_v": SpecFieldDefinition("voltage", required=True),
        "attenuation_db_per_km_1khz_20c": SpecFieldDefinition("float", required=True),
        "sale_multiple_m": SpecFieldDefinition("float", required=True),
    },
    "instrument": {
        "instrument_subtype": SpecFieldDefinition("enum", required=True, values=INSTRUMENT_SUBTYPE_VALUES),
    },
    "keyboard": {},
    "speech": {},
    "battery": {},
    "mounting": {
        "pack_quantity": SpecFieldDefinition("int", required=True, minimum=1),
        "mounting_spacing_m": SpecFieldDefinition("float", required=True, minimum=0.1),
    },
    "other": {},
}

INSTRUMENT_SUBTYPE_SPEC_DEFINITIONS: dict[str, dict[str, SpecFieldDefinition]] = {
    "security_fire_control_panel": {
        "zone_count": SpecFieldDefinition("int", required=True),
        "shs_count": SpecFieldDefinition("int", required=True),
        "shs_terminal_voltage_v": SpecFieldDefinition("voltage", required=True),
        "standby_current_a": SpecFieldDefinition("float", required=True),
        "alarm_current_a": SpecFieldDefinition("float", copy_from="standby_current_a"),
    },
    "control_and_management_console": {
        "connected_instruments_count": SpecFieldDefinition("int", required=True),
        "sections_count": SpecFieldDefinition("int", required=True),
        "section_groups_count": SpecFieldDefinition("int", required=True),
        "supply_voltage_v": SpecFieldDefinition("voltage", required=True),
        "current_12v_a": SpecFieldDefinition("float", required=True),
        "current_24v_a": SpecFieldDefinition("float", required=True),
    },
    "indication_unit": {
        "supply_voltage_v": SpecFieldDefinition("voltage", required=True),
        "standby_current_a": SpecFieldDefinition("float", required=True),
        "alarm_current_a": SpecFieldDefinition("float", copy_from="standby_current_a"),
    },
}

CURRENT_SPEC_CATEGORIES = {
    "smoke",
    "heat",
    "linear",
    "manual",
    "exit_sign",
    "siren",
}


def build_legacy_specs(
    category: str,
    *,
    smoke_addressing: str | None = None,
    standby_current_ma: float | int | None = None,
    alarm_current_ma: float | int | None = None,
) -> dict[str, Any]:
    """Build a partial specs payload from legacy top-level columns."""

    specs: dict[str, Any] = {}
    if category == "smoke" and smoke_addressing not in (None, ""):
        specs["addressing_mode"] = smoke_addressing
    if category in CURRENT_SPEC_CATEGORIES:
        standby_current_a = _ma_to_a(standby_current_ma)
        alarm_current_a = _ma_to_a(alarm_current_ma)
        if standby_current_a is not None:
            specs["standby_current_a"] = standby_current_a
        if alarm_current_a is not None:
            specs["alarm_current_a"] = alarm_current_a
    return specs


def coerce_current_specs(
    category: str,
    raw_specs: Any,
    *,
    smoke_addressing: str | None = None,
    standby_current_ma: float | int | None = None,
    alarm_current_ma: float | int | None = None,
) -> dict[str, Any]:
    """Best-effort normalization for reads and legacy backfill."""

    try:
        return normalize_specs(
            category,
            raw_specs,
            smoke_addressing=smoke_addressing,
            standby_current_ma=standby_current_ma,
            alarm_current_ma=alarm_current_ma,
            require_complete=False,
        )
    except EquipmentSpecsValidationError:
        return build_legacy_specs(
            category,
            smoke_addressing=smoke_addressing,
            standby_current_ma=standby_current_ma,
            alarm_current_ma=alarm_current_ma,
        )


def normalize_specs(
    category: str,
    raw_specs: Any,
    *,
    smoke_addressing: str | None = None,
    standby_current_ma: float | int | None = None,
    alarm_current_ma: float | int | None = None,
    require_complete: bool = True,
) -> dict[str, Any]:
    """Normalize and validate the category-specific specs payload."""

    definitions = CATEGORY_SPEC_DEFINITIONS.get(category, {})
    if not definitions:
        return {}

    parsed_specs = _parse_specs_payload(raw_specs)
    if category == "instrument":
        return _normalize_instrument_specs(parsed_specs, require_complete=require_complete)

    merged_specs = {
        **build_legacy_specs(
            category,
            smoke_addressing=smoke_addressing,
            standby_current_ma=standby_current_ma,
            alarm_current_ma=alarm_current_ma,
        ),
        **parsed_specs,
    }

    if require_complete:
        _validate_unknown_spec_fields(category, parsed_specs, set(definitions.keys()))

    normalized: dict[str, Any] = {}
    for field_name, definition in definitions.items():
        if field_name in merged_specs:
            normalized[field_name] = _normalize_spec_value(field_name, merged_specs[field_name], definition)

    for field_name, definition in definitions.items():
        if field_name not in normalized and definition.copy_from:
            copied = normalized.get(definition.copy_from)
            if copied is not None:
                normalized[field_name] = copied

    if require_complete:
        for field_name, definition in definitions.items():
            if definition.required and normalized.get(field_name) is None:
                raise EquipmentSpecsValidationError(
                    "equipment_item_missing_required_spec",
                    f"Field specs.{field_name} is required for category {category}",
                )

    return normalized


def _normalize_instrument_specs(raw_specs: dict[str, Any], *, require_complete: bool) -> dict[str, Any]:
    subtype = _resolve_instrument_subtype(raw_specs, require_complete=require_complete)
    if subtype is None:
        return {}

    definitions = INSTRUMENT_SUBTYPE_SPEC_DEFINITIONS[subtype]
    allowed_fields = {"instrument_subtype", *definitions.keys()}
    if require_complete:
        _validate_unknown_spec_fields("instrument", raw_specs, allowed_fields)

    normalized: dict[str, Any] = {"instrument_subtype": subtype}
    for field_name, definition in definitions.items():
        if field_name in raw_specs:
            normalized[field_name] = _normalize_spec_value(field_name, raw_specs[field_name], definition)

    for field_name, definition in definitions.items():
        if field_name not in normalized and definition.copy_from:
            copied = normalized.get(definition.copy_from)
            if copied is not None:
                normalized[field_name] = copied

    if require_complete:
        for field_name, definition in definitions.items():
            if definition.required and normalized.get(field_name) is None:
                raise EquipmentSpecsValidationError(
                    "equipment_item_missing_required_spec",
                    f"Field specs.{field_name} is required for instrument subtype {subtype}",
                )

    return normalized


def _resolve_instrument_subtype(raw_specs: dict[str, Any], *, require_complete: bool) -> str | None:
    raw_subtype = raw_specs.get("instrument_subtype")
    if raw_subtype in (None, ""):
        if not require_complete and any(key in raw_specs for key in LEGACY_INSTRUMENT_SPEC_KEYS):
            return "security_fire_control_panel"
        if require_complete:
            raise EquipmentSpecsValidationError(
                "equipment_item_missing_required_spec",
                "Field specs.instrument_subtype is required for category instrument",
            )
        return None

    normalized = str(raw_subtype).strip()
    if normalized in LEGACY_INSTRUMENT_SUBTYPE_ALIASES:
        if require_complete:
            raise EquipmentSpecsValidationError(
                "equipment_item_invalid_spec_value",
                f"Field specs.instrument_subtype has unsupported value: {raw_subtype}",
            )
        normalized = LEGACY_INSTRUMENT_SUBTYPE_ALIASES[normalized]

    if normalized not in INSTRUMENT_SUBTYPE_VALUES:
        raise EquipmentSpecsValidationError(
            "equipment_item_invalid_spec_value",
            f"Field specs.instrument_subtype has unsupported value: {raw_subtype}",
        )
    return normalized


def _validate_unknown_spec_fields(category: str, raw_specs: dict[str, Any], allowed_fields: set[str]) -> None:
    unknown_fields = sorted(set(raw_specs.keys()) - allowed_fields)
    if not unknown_fields:
        return
    field_names = ", ".join(f"specs.{field_name}" for field_name in unknown_fields)
    raise EquipmentSpecsValidationError(
        "equipment_item_invalid_spec_value",
        f"Unsupported spec fields for category {category}: {field_names}",
    )


def _parse_specs_payload(raw_specs: Any) -> dict[str, Any]:
    if raw_specs in (None, ""):
        return {}
    if isinstance(raw_specs, str):
        try:
            raw_specs = json.loads(raw_specs)
        except json.JSONDecodeError as exc:
            raise EquipmentSpecsValidationError(
                "equipment_item_invalid_specs_payload",
                "Field specs must be a JSON object",
            ) from exc
    if not isinstance(raw_specs, dict):
        raise EquipmentSpecsValidationError(
            "equipment_item_invalid_specs_payload",
            "Field specs must be an object",
        )
    return dict(raw_specs)


def _normalize_spec_value(field_name: str, value: Any, definition: SpecFieldDefinition) -> Any:
    if definition.kind == "text":
        normalized = None if value is None else str(value).strip()
        return normalized or None
    if value in (None, ""):
        return None
    if definition.kind == "float":
        try:
            normalized = float(value)
        except (TypeError, ValueError) as exc:
            raise EquipmentSpecsValidationError(
                "equipment_item_invalid_spec_value",
                f"Field specs.{field_name} must be a number",
            ) from exc
        if definition.minimum is not None and normalized < definition.minimum:
            raise EquipmentSpecsValidationError(
                "equipment_item_invalid_spec_value",
                f"Field specs.{field_name} must be greater than or equal to {definition.minimum}",
            )
        return normalized
    if definition.kind == "voltage":
        return _normalize_voltage_value(field_name, value)
    if definition.kind == "int":
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise EquipmentSpecsValidationError(
                "equipment_item_invalid_spec_value",
                f"Field specs.{field_name} must be an integer",
            ) from exc
        if not numeric.is_integer():
            raise EquipmentSpecsValidationError(
                "equipment_item_invalid_spec_value",
                f"Field specs.{field_name} must be an integer",
            )
        normalized = int(numeric)
        if definition.minimum is not None and normalized < definition.minimum:
            raise EquipmentSpecsValidationError(
                "equipment_item_invalid_spec_value",
                f"Field specs.{field_name} must be greater than or equal to {int(definition.minimum)}",
            )
        return normalized
    if definition.kind == "enum":
        normalized = str(value).strip()
        if normalized not in (definition.values or ()):
            raise EquipmentSpecsValidationError(
                "equipment_item_invalid_spec_value",
                f"Field specs.{field_name} has unsupported value: {value}",
            )
        return normalized
    raise EquipmentSpecsValidationError(
        "equipment_item_invalid_spec_definition",
        f"Unsupported spec definition for field {field_name}",
    )


def _ma_to_a(value: float | int | None) -> float | None:
    if value in (None, ""):
        return None
    return float(value) / 1000.0


def _normalize_voltage_value(field_name: str, value: Any) -> float | dict[str, float] | None:
    if value in (None, ""):
        return None
    if isinstance(value, dict):
        min_value = value.get("min")
        max_value = value.get("max")
        normalized_min = _normalize_optional_voltage_endpoint(field_name, min_value)
        normalized_max = _normalize_optional_voltage_endpoint(field_name, max_value)
        if normalized_min is None and normalized_max is None:
            return None
        if normalized_min is None:
            return normalized_max
        if normalized_max is None:
            return normalized_min
        if normalized_min == normalized_max:
            return normalized_min
        if normalized_min > normalized_max:
            normalized_min, normalized_max = normalized_max, normalized_min
        return {"min": normalized_min, "max": normalized_max}
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise EquipmentSpecsValidationError(
            "equipment_item_invalid_spec_value",
            f"Field specs.{field_name} must be a number or a min/max range object",
        ) from exc


def _normalize_optional_voltage_endpoint(field_name: str, value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise EquipmentSpecsValidationError(
            "equipment_item_invalid_spec_value",
            f"Field specs.{field_name} range values must be numbers",
        ) from exc
