"""Constants for the equipment catalog domain."""

from __future__ import annotations


EQUIPMENT_CATEGORIES: tuple[str, ...] = (
    "linear",
    "smoke",
    "heat",
    "manual",
    "siren",
    "exit_sign",
    "speech",
    "instrument",
    "keyboard",
    "cable",
    "battery",
    "mounting",
    "other",
)

SMOKE_ADDRESSING_VALUES: tuple[str, ...] = (
    "addressable",
    "non_addressable",
)

SUPPORTED_SPS_MODE_VALUES: tuple[str, ...] = (
    "addressable",
    "non_addressable",
    "both",
)

INSTRUMENT_SUBTYPE_VALUES: tuple[str, ...] = (
    "security_fire_control_panel",
    "control_and_management_console",
    "indication_unit",
)

PROJECT_EQUIPMENT_ROLE_CATEGORY_MAP: dict[str, str] = {
    "sps_linear_detector": "linear",
    "sps_smoke_detector": "smoke",
    "sps_heat_detector": "heat",
    "sps_manual_call_point": "manual",
    "sps_cable": "cable",
    "soue_siren": "siren",
    "soue_exit_sign": "exit_sign",
    "soue_speech_device": "speech",
    "soue_cable": "cable",
    "common_instrument": "instrument",
    "common_keyboard": "keyboard",
    "common_other": "other",
}

PROJECT_EQUIPMENT_ROLES: tuple[str, ...] = tuple(PROJECT_EQUIPMENT_ROLE_CATEGORY_MAP.keys())

PROJECT_EQUIPMENT_GROUP_CATEGORY_MAP: dict[str, tuple[str, ...]] = {
    "sps": ("linear", "smoke", "heat", "manual", "cable"),
    "soue": ("siren", "exit_sign", "speech", "cable"),
    "instruments": ("instrument", "keyboard"),
    "mounting": ("mounting",),
    "other": ("battery", "other"),
}

FIRE_ALARM_DEVICE_CATEGORY_MAP: dict[str, tuple[str, ...]] = {
    "linear_detector": ("linear",),
    "manual_call_point": ("manual",),
    "smoke_detector": ("smoke",),
    "heat_detector": ("heat",),
}

SOUE_DEVICE_CATEGORY_MAP: dict[str, tuple[str, ...]] = {
    "siren": ("siren",),
    "exit_sign": ("exit_sign",),
    "speech_device": ("speech",),
}

SIGNAL_INSTRUMENT_CATEGORY_MAP: dict[str, tuple[str, ...]] = {
    "control_panel": ("instrument", "keyboard"),
    "loop_controller": ("instrument", "keyboard"),
    "annunciator": ("instrument", "keyboard"),
}
