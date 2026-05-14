from __future__ import annotations

from types import SimpleNamespace

import pytest

from PowerConsumptionCalculationPage import PowerConsumptionCalculationPage
from backend.bootstrap import register_pdf_fonts
from backend.errors import AppError
from backend.modules.documents.power_consumption import (
    apply_power_consumption_overrides,
    build_project_power_consumption_calculation,
    extract_power_consumption_overrides,
)


def _equipment(equipment_id: int, name: str, category: str, specs: dict | None = None):
    return SimpleNamespace(
        id=equipment_id,
        name=name,
        category=category,
        specs=specs or {},
        smoke_addressing=None,
        standby_current_ma=None,
        alarm_current_ma=None,
    )


def _selection(role_key: str, equipment):
    return SimpleNamespace(role_key=role_key, equipment=equipment)


def _floor_plan(
    *,
    signal_instruments: list | None = None,
    fire_alarms: list | None = None,
    soue_devices: list | None = None,
):
    return SimpleNamespace(
        name="Floor 1",
        floor_number=1,
        signal_instruments=signal_instruments or [],
        fire_alarms=fire_alarms or [],
        soue_devices=soue_devices or [],
    )


def test_build_project_power_consumption_calculation_groups_and_summarizes_rows():
    control_panel = _equipment(
        1,
        "Панель B",
        "instrument",
        {
            "instrument_subtype": "security_fire_control_panel",
            "standby_current_a": 0.12,
            "alarm_current_a": 0.18,
        },
    )
    smoke = _equipment(
        2,
        "Smoke B",
        "smoke",
        {
            "standby_current_a": 0.0001,
            "alarm_current_a": 0.0003,
        },
    )
    heat = _equipment(
        3,
        "Heat A",
        "heat",
        {
            "standby_current_a": 0.0002,
            "alarm_current_a": 0.0004,
        },
    )
    exit_sign = _equipment(
        4,
        "Exit A",
        "exit_sign",
        {
            "standby_current_a": 0.01,
            "alarm_current_a": 0.02,
        },
    )
    siren = _equipment(
        5,
        "Siren Z",
        "siren",
        {
            "standby_current_a": 0.02,
            "alarm_current_a": 0.04,
        },
    )

    project = SimpleNamespace(id=7, equipment_selections=[], equipment_links=[])
    floor_plan = _floor_plan(
        signal_instruments=[
            SimpleNamespace(id=11, equipment=control_panel),
            SimpleNamespace(id=12, equipment=control_panel),
        ],
        fire_alarms=[
            SimpleNamespace(id=21, equipment=smoke, device_type="smoke_detector"),
            SimpleNamespace(id=22, equipment=smoke, device_type="smoke_detector"),
            SimpleNamespace(id=23, equipment=heat, device_type="heat_detector"),
        ],
        soue_devices=[
            SimpleNamespace(id=31, equipment=siren, device_type="siren"),
            SimpleNamespace(id=32, equipment=exit_sign, device_type="exit_sign"),
        ],
    )

    calculation = build_project_power_consumption_calculation(project, [floor_plan])

    assert [category["title"] for category in calculation["categories"]] == [
        "1. Приборы",
        "2. Извещатели",
        "3. Оповещатели и устройства коммутационные",
    ]

    instrument_rows = calculation["categories"][0]["rows"]
    detector_rows = calculation["categories"][1]["rows"]
    notification_rows = calculation["categories"][2]["rows"]

    assert instrument_rows[0]["equipment_name"] == "Панель B"
    assert instrument_rows[0]["source_key"] == "instruments:1"
    assert instrument_rows[0]["quantity"] == "2"
    assert instrument_rows[0]["standby_total"] == "0,24"
    assert instrument_rows[0]["alarm_total"] == "0,36"

    assert [row["equipment_name"] for row in detector_rows] == ["Heat A", "Smoke B"]
    assert [row["number"] for row in detector_rows] == ["1", "2"]
    assert detector_rows[0]["quantity"] == "1"
    assert detector_rows[1]["quantity"] == "2"

    assert [row["equipment_name"] for row in notification_rows] == ["Exit A", "Siren Z"]
    assert [row["key"] for row in calculation["summary_rows"]] == [
        "instruments_and_detectors_total",
        "notification_total",
        "overall_total",
        "operation_time",
        "capacity",
        "correction_factor",
        "corrected_capacity",
        "total_capacity",
    ]

    computed = calculation["computed_values"]
    assert computed["instruments_and_detectors_standby"] == pytest.approx(0.2404)
    assert computed["instruments_and_detectors_alarm"] == pytest.approx(0.361)
    assert computed["notification_standby"] == pytest.approx(0.03)
    assert computed["notification_alarm"] == pytest.approx(0.06)
    assert computed["overall_standby"] == pytest.approx(0.2704)
    assert computed["overall_alarm"] == pytest.approx(0.421)
    assert computed["capacity_standby"] == pytest.approx(6.4896)
    assert computed["capacity_alarm"] == pytest.approx(0.421)
    assert computed["corrected_capacity_standby"] == pytest.approx(7.13856)
    assert computed["corrected_capacity_alarm"] == pytest.approx(0.4631)
    assert computed["total_capacity"] == pytest.approx(7.60166)
    assert calculation["battery_capacity_ah"] == 8
    assert calculation["final_text"].endswith("12 В, 8 Ач - 1 шт.")


def test_build_project_power_consumption_calculation_uses_selection_fallback_and_control_console_12v_current():
    console = _equipment(
        10,
        "Console A",
        "instrument",
        {
            "instrument_subtype": "control_and_management_console",
            "current_12v_a": 0.05,
            "current_24v_a": 0.08,
        },
    )
    keyboard = _equipment(11, "Keyboard A", "keyboard", {})
    project = SimpleNamespace(
        id=8,
        equipment_selections=[_selection("common_instrument", console)],
        equipment_links=[],
    )
    floor_plan = _floor_plan(
        signal_instruments=[
            SimpleNamespace(id=41, equipment=None, instrument_type="control_panel"),
            SimpleNamespace(id=42, equipment=keyboard, instrument_type="control_panel"),
        ],
    )

    calculation = build_project_power_consumption_calculation(project, [floor_plan])
    instrument_rows = calculation["categories"][0]["rows"]

    assert len(instrument_rows) == 1
    assert instrument_rows[0]["equipment_name"] == "Console A"
    assert instrument_rows[0]["standby_current"] == "0,05"
    assert instrument_rows[0]["alarm_current"] == "0,05"
    assert calculation["computed_values"]["overall_standby"] == pytest.approx(0.05)
    assert calculation["computed_values"]["overall_alarm"] == pytest.approx(0.05)


def test_build_project_power_consumption_calculation_skips_items_without_currents_and_keeps_empty_categories():
    keyboard = _equipment(21, "Keyboard A", "keyboard", {})
    project = SimpleNamespace(id=9, equipment_selections=[], equipment_links=[])
    floor_plan = _floor_plan(
        signal_instruments=[SimpleNamespace(id=51, equipment=keyboard, instrument_type="control_panel")],
    )

    calculation = build_project_power_consumption_calculation(project, [floor_plan])

    assert [len(category["rows"]) for category in calculation["categories"]] == [0, 0, 0]
    assert calculation["battery_capacity_ah"] == 0
    assert calculation["computed_values"]["total_capacity"] == pytest.approx(0.0)


def test_build_project_power_consumption_calculation_counts_detectors_from_legacy_current_fields():
    smoke = _equipment(31, "Smoke Legacy", "smoke", {})
    smoke.smoke_addressing = "addressable"
    smoke.standby_current_ma = 0.1
    smoke.alarm_current_ma = 0.3

    heat = _equipment(32, "Heat Legacy", "heat", {})
    heat.standby_current_ma = 0.2
    heat.alarm_current_ma = 0.4

    linear = _equipment(33, "Linear Legacy", "linear", {"range_m": 100, "addressing_mode": "addressable", "loop_voltage_v": 24})
    linear.standby_current_ma = 0.2
    linear.alarm_current_ma = 0.5

    project = SimpleNamespace(id=10, equipment_selections=[], equipment_links=[])
    floor_plan = _floor_plan(
        fire_alarms=[
            SimpleNamespace(id=61, equipment=smoke, device_type="smoke_detector"),
            SimpleNamespace(id=62, equipment=heat, device_type="heat_detector"),
            SimpleNamespace(id=63, equipment=linear, device_type="linear_detector"),
        ],
    )

    calculation = build_project_power_consumption_calculation(project, [floor_plan])
    detector_rows = calculation["categories"][1]["rows"]

    assert [row["equipment_name"] for row in detector_rows] == ["Heat Legacy", "Linear Legacy", "Smoke Legacy"]
    assert calculation["computed_values"]["overall_standby"] == pytest.approx(0.0005)
    assert calculation["computed_values"]["overall_alarm"] == pytest.approx(0.0012)


def test_apply_power_consumption_overrides_recalculates_rows_summary_and_final_text():
    control_panel = _equipment(
        100,
        "Panel A",
        "instrument",
        {
            "instrument_subtype": "security_fire_control_panel",
            "standby_current_a": 0.1,
            "alarm_current_a": 0.2,
        },
    )
    project = SimpleNamespace(id=11, equipment_selections=[], equipment_links=[])
    floor_plan = _floor_plan(signal_instruments=[SimpleNamespace(id=101, equipment=control_panel)])
    base = build_project_power_consumption_calculation(project, [floor_plan])

    updated = apply_power_consumption_overrides(
        base,
        {
            "page_title": "Обновленный расчет",
            "battery_voltage_v": "24",
            "battery_quantity": "2",
            "category_titles": {"instruments": "1. Приборы проекта"},
            "rows": {
                "instruments:100": {
                    "quantity": "3",
                    "standby_current": "0,15",
                    "alarm_current": "0,25",
                },
            },
            "summary_rows": {
                "operation_time": {"standby": "12", "alarm": "2"},
                "correction_factor": {"standby": "1,2", "alarm": "1,3"},
            },
        },
    )

    row = updated["categories"][0]["rows"][0]
    assert updated["page_title"] == "Обновленный расчет"
    assert updated["categories"][0]["title"] == "1. Приборы проекта"
    assert row["quantity"] == "3"
    assert row["standby_total"] == "0,45"
    assert row["alarm_total"] == "0,75"
    assert updated["summary_rows"][3]["standby"] == "12"
    assert updated["summary_rows"][3]["alarm"] == "2"
    assert updated["summary_rows"][5]["standby"] == "1,2"
    assert updated["summary_rows"][5]["alarm"] == "1,3"
    assert updated["battery_capacity_ah"] == 9
    assert updated["final_text"].endswith("24 В, 9 Ач - 2 шт.")
    assert updated["computed_values"]["total_capacity"] == pytest.approx(8.43)


def test_extract_power_consumption_overrides_returns_only_changed_editable_fields():
    smoke = _equipment(
        120,
        "Smoke A",
        "smoke",
        {
            "standby_current_a": 0.0001,
            "alarm_current_a": 0.0003,
        },
    )
    project = SimpleNamespace(id=12, equipment_selections=[], equipment_links=[])
    floor_plan = _floor_plan(fire_alarms=[SimpleNamespace(id=121, equipment=smoke, device_type="smoke_detector")])
    base = build_project_power_consumption_calculation(project, [floor_plan])
    updated = apply_power_consumption_overrides(
        base,
        {
            "table_title": "Новая таблица",
            "rows": {"detectors:120": {"quantity": "2"}},
            "summary_rows": {"operation_time": {"label": "Время", "standby": "48"}},
        },
    )

    overrides = extract_power_consumption_overrides(base, updated)

    assert overrides == {
        "table_title": "Новая таблица",
        "rows": {"detectors:120": {"quantity": "2"}},
        "summary_rows": {"operation_time": {"label": "Время", "standby": "48"}},
    }


def test_extract_power_consumption_overrides_rejects_invalid_numeric_values():
    smoke = _equipment(
        130,
        "Smoke B",
        "smoke",
        {
            "standby_current_a": 0.0001,
            "alarm_current_a": 0.0003,
        },
    )
    project = SimpleNamespace(id=13, equipment_selections=[], equipment_links=[])
    floor_plan = _floor_plan(fire_alarms=[SimpleNamespace(id=131, equipment=smoke, device_type="smoke_detector")])
    base = build_project_power_consumption_calculation(project, [floor_plan])
    updated = {
        **base,
        "categories": [
            {
                **category,
                "rows": [
                    {
                        **row,
                        "quantity": "not-a-number" if row["source_key"] == "detectors:130" else row["quantity"],
                    }
                    for row in category["rows"]
                ],
            }
            for category in base["categories"]
        ],
    }

    with pytest.raises(AppError) as exc_info:
        extract_power_consumption_overrides(base, updated)

    assert exc_info.value.code == "power_consumption_override_invalid_number"


def test_power_consumption_page_paginate_creates_continuation_pages_and_keeps_summary_last():
    register_pdf_fonts()
    calculation = {
        "page_title": "Расчет токопотребления системы",
        "introductory_texts": [
            "Первый абзац для теста пагинации.",
            "Второй абзац для теста пагинации.",
        ],
        "table_caption": "Таблица 1.",
        "table_title": "Расчет токопотребления системы",
        "categories": [
            {
                "key": "instruments",
                "title": "1. Приборы",
                "rows": [
                    {
                        "number": str(index + 1),
                        "equipment_name": f"Панель {index + 1}",
                        "unit": "шт.",
                        "quantity": "1",
                        "standby_current": "0,12",
                        "alarm_current": "0,18",
                        "standby_total": "0,12",
                        "alarm_total": "0,18",
                    }
                    for index in range(22)
                ],
            },
            {"key": "detectors", "title": "2. Извещатели", "rows": []},
            {"key": "notification_devices", "title": "3. Оповещатели и устройства коммутационные", "rows": []},
        ],
        "summary_rows": [
            {"kind": "summary", "label": "1. Итого", "standby": "1", "alarm": "1"},
            {"kind": "summary", "label": "2. Итого", "standby": "1", "alarm": "1"},
            {"kind": "summary", "label": "3. Итого", "standby": "1", "alarm": "1"},
            {"kind": "summary", "label": "4. Время", "standby": "24", "alarm": "1"},
            {"kind": "summary", "label": "5. Ёмкость", "standby": "24", "alarm": "1"},
            {"kind": "summary", "label": "6. Коэффициент", "standby": "1,1", "alarm": "1,1"},
            {"kind": "summary", "label": "7. С коэффициентом", "standby": "26,4", "alarm": "1,1"},
            {"kind": "summary_merged", "label": "8. Wобщ", "value": "27,5"},
        ],
        "final_text": "Исходя из расчетов принимаем использование аккумуляторной батареи 12 В, 28 Ач - 1 шт.",
    }

    segments = PowerConsumptionCalculationPage.paginate(calculation)

    assert len(segments) > 1
    assert segments[0]["show_intro"] is True
    assert segments[0]["is_continuation"] is False
    assert all(segment["is_continuation"] is True for segment in segments[1:])
    assert segments[-1]["show_summary"] is True
    assert all(segment["show_summary"] is False for segment in segments[:-1])
