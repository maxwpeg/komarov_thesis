from __future__ import annotations

import io

import pytest
import requests
from PIL import Image

from backend import database
from backend.modules.shared.infrastructure.persistence.models import EquipmentItem


def _create_project(base_url: str) -> dict:
    response = requests.post(
        f"{base_url}/api/projects",
        json={
            "name": "Project 01",
            "project_type": "PS",
            "year": 2026,
            "contractor": "Contractor",
            "engineer": "Engineer",
            "cpe": "CPE",
            "checker": "Checker",
            "facility": "Facility",
            "facility_address": "Address",
            "project_description": "Description",
            "stage": "R",
            "number_of_floors": 1,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def _default_specs(category: str) -> dict:
    if category == "smoke":
        return {
            "addressing_mode": "addressable",
            "loop_voltage_v": 24,
            "standby_current_a": 0.0001,
            "alarm_current_a": 0.0003,
        }
    if category == "heat":
        return {
            "addressing_mode": "non_addressable",
            "loop_voltage_v": 24,
            "standby_current_a": 0.0002,
            "alarm_current_a": 0.0004,
        }
    if category == "linear":
        return {
            "addressing_mode": "addressable",
            "loop_voltage_v": 24,
            "standby_current_a": 0.0002,
            "alarm_current_a": 0.0005,
            "range_m": 100,
        }
    if category == "manual":
        return {
            "addressing_mode": "addressable",
            "loop_voltage_v": 24,
            "standby_current_a": 0.0001,
            "alarm_current_a": 0.0001,
        }
    if category == "siren":
        return {
            "sound_pressure_db": 95,
            "supply_voltage_v": 24,
            "standby_current_a": 0.02,
            "alarm_current_a": 0.04,
        }
    if category == "exit_sign":
        return {
            "supply_voltage_v": 24,
            "standby_current_a": 0.01,
            "alarm_current_a": 0.02,
        }
    if category == "cable":
        return {
            "conductors_count": 2,
            "conductor_type": "Cu",
            "working_voltage_max_v": 300,
            "attenuation_db_per_km_1khz_20c": 12,
            "sale_multiple_m": 100,
        }
    if category == "instrument":
        return {
            "instrument_subtype": "security_fire_control_panel",
            "shs_terminal_voltage_v": 24,
            "standby_current_a": 0.12,
            "alarm_current_a": 0.18,
            "shs_count": 4,
            "zone_count": 8,
        }
    if category == "mounting":
        return {
            "pack_quantity": 100,
            "mounting_spacing_m": 0.4,
        }
    return {}


def _create_equipment(base_url: str, **overrides) -> dict:
    category = overrides.get("category", "smoke")
    payload = {
        "name": "Smoke A" if category == "smoke" else f"{category.title()} A",
        "category": category,
        "description": "Equipment item",
        "price": 1200,
        "manufacturer": "Test Manufacturer",
        "service_life_years": 10,
        "notes": "Test notes",
        "specs": _default_specs(category),
        "compatible_equipment_ids": [],
    }
    payload.update(overrides)
    response = requests.post(f"{base_url}/api/equipment", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def _empty_project_selections(**overrides) -> dict[str, int | None]:
    selections = {
        "sps_linear_detector": None,
        "sps_smoke_detector": None,
        "sps_heat_detector": None,
        "sps_manual_call_point": None,
        "sps_cable": None,
        "soue_siren": None,
        "soue_exit_sign": None,
        "soue_speech_device": None,
        "soue_cable": None,
        "common_instrument": None,
        "common_keyboard": None,
        "common_other": None,
    }
    selections.update(overrides)
    return selections


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), color=(240, 240, 240)).save(buffer, format="PNG")
    return buffer.getvalue()


def _create_floor_plan(base_url: str, project_id: int, scale_factor: float = 10.0) -> dict:
    response = requests.post(
        f"{base_url}/api/floor-plans",
        data={
            "project_id": str(project_id),
            "floor_number": "1",
            "name": "Floor 1",
            "scale_factor": str(scale_factor),
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def _create_wall(base_url: str, floor_plan_id: int) -> dict:
    response = requests.post(
        f"{base_url}/api/walls",
        json={
            "floor_plan_id": floor_plan_id,
            "x1": 0,
            "y1": 0,
            "x2": 100,
            "y2": 0,
            "thickness": 200,
            "is_load_bearing": False,
            "material": None,
            "length_m": 1.0,
            "length_source": "manual",
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def _prepare_validated_floor_plan(base_url: str, project_id: int) -> tuple[dict, dict]:
    floor_plan = _create_floor_plan(base_url, project_id, scale_factor=10.0)
    wall = _create_wall(base_url, floor_plan["id"])
    room_response = requests.post(
        f"{base_url}/api/rooms",
        json={
            "floor_plan_id": floor_plan["id"],
            "name": "Room 1",
            "boundary_points": [[0, 0], [100, 0], [100, 100], [0, 100]],
        },
        timeout=10,
    )
    room_response.raise_for_status()
    room = room_response.json()

    walls_commit = requests.post(
        f"{base_url}/api/floor-plans/{floor_plan['id']}/pipeline/walls/commit",
        json={
            "changes": {},
            "wall_lengths": [{"wall_id": wall["id"], "length_m": 1.0, "length_source": "manual"}],
        },
        timeout=10,
    )
    walls_commit.raise_for_status()

    openings_commit = requests.post(
        f"{base_url}/api/floor-plans/{floor_plan['id']}/pipeline/openings/commit",
        json={"changes": {}},
        timeout=10,
    )
    openings_commit.raise_for_status()

    rooms_commit = requests.post(
        f"{base_url}/api/floor-plans/{floor_plan['id']}/pipeline/rooms/commit",
        json={
            "changes": {},
            "room_updates": [{"room_id": room["id"], "name": "Room 1", "room_number": "1"}],
        },
        timeout=10,
    )
    rooms_commit.raise_for_status()
    return floor_plan, room


def test_equipment_crud_and_image_upload(api_server: str):
    created = _create_equipment(api_server)
    assert created["name"] == "Smoke A"
    assert created["manufacturer"] == "Test Manufacturer"
    assert created["service_life_years"] == 10
    assert created["smoke_addressing"] == "addressable"
    assert created["specs"]["addressing_mode"] == "addressable"

    upload_response = requests.post(
        f"{api_server}/api/equipment/{created['id']}/image",
        files={"image": ("equipment.png", _png_bytes(), "image/png")},
        timeout=10,
    )
    upload_response.raise_for_status()
    uploaded = upload_response.json()
    assert uploaded["image_path"].startswith("uploads/equipment_")

    list_response = requests.get(f"{api_server}/api/equipment", timeout=10)
    list_response.raise_for_status()
    listed_ids = [item["id"] for item in list_response.json()]
    assert created["id"] in listed_ids


def test_non_smoke_equipment_rejects_legacy_smoke_addressing(api_server: str):
    response = requests.post(
        f"{api_server}/api/equipment",
        json={
            "name": "Cable A",
            "category": "cable",
            "description": "Cable",
            "price": 200,
            "manufacturer": "Test",
            "service_life_years": 15,
            "notes": None,
            "specs": _default_specs("cable"),
            "smoke_addressing": "addressable",
            "compatible_equipment_ids": [],
        },
        timeout=10,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "smoke_addressing_only_for_smoke_equipment"


def test_equipment_auto_fills_alarm_current_when_omitted(api_server: str):
    created = _create_equipment(
        api_server,
        name="Smoke Auto Alarm",
        specs={
            "addressing_mode": "addressable",
            "loop_voltage_v": 24,
            "standby_current_a": 0.0008,
        },
    )

    assert created["specs"]["standby_current_a"] == pytest.approx(0.0008)
    assert created["specs"]["alarm_current_a"] == pytest.approx(0.0008)


def test_equipment_accepts_voltage_ranges(api_server: str):
    created = _create_equipment(
        api_server,
        name="Smoke Range",
        specs={
            "addressing_mode": "addressable",
            "loop_voltage_v": {"min": 12, "max": 24},
            "standby_current_a": 0.0008,
        },
    )

    assert created["specs"]["loop_voltage_v"] == {"min": 12.0, "max": 24.0}
    assert created["specs"]["alarm_current_a"] == pytest.approx(0.0008)


def test_equipment_accepts_battery_category_without_additional_specs(api_server: str):
    created = _create_equipment(api_server, category="battery", specs={})

    assert created["category"] == "battery"


def test_equipment_accepts_mounting_category_with_required_specs(api_server: str):
    created = _create_equipment(api_server, category="mounting", specs=_default_specs("mounting"))

    assert created["category"] == "mounting"
    assert created["specs"]["pack_quantity"] == 100
    assert created["specs"]["mounting_spacing_m"] == pytest.approx(0.4)


def test_project_equipment_specification_builds_and_persists_overrides(api_server: str):
    project = _create_project(api_server)
    smoke = _create_equipment(api_server, category="smoke", name="Smoke Spec")
    instrument = _create_equipment(api_server, category="instrument", name="Panel Spec")
    cable = _create_equipment(api_server, category="cable", name="Cable Spec")
    mounting = _create_equipment(api_server, category="mounting", name="Clip Pack", specs=_default_specs("mounting"))

    for equipment in (smoke, instrument, cable, mounting):
        attach_response = requests.post(
            f"{api_server}/api/projects/{project['id']}/equipment",
            json={"equipment_id": equipment["id"]},
            timeout=10,
        )
        attach_response.raise_for_status()

    selections_response = requests.patch(
        f"{api_server}/api/projects/{project['id']}/equipment-selections",
        json={
            "selections": _empty_project_selections(
                sps_smoke_detector=smoke["id"],
                sps_cable=cable["id"],
                common_instrument=instrument["id"],
            )
        },
        timeout=10,
    )
    selections_response.raise_for_status()

    floor_plan, _room = _prepare_validated_floor_plan(api_server, project["id"])

    fire_alarm_response = requests.post(
        f"{api_server}/api/fire-alarms",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 50,
            "y": 50,
            "device_type": "smoke_detector",
            "system_type": "non_addressable",
            "equipment_id": smoke["id"],
        },
        timeout=10,
    )
    fire_alarm_response.raise_for_status()

    instrument_response = requests.post(
        f"{api_server}/api/signal-instruments",
        json={
            "floor_plan_id": floor_plan["id"],
            "system_type": "non_addressable",
            "instrument_type": "control_panel",
            "x": 10,
            "y": 10,
            "equipment_id": instrument["id"],
        },
        timeout=10,
    )
    instrument_response.raise_for_status()

    recalc_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/cable-routes/recalculate",
        json={"system_type": "non_addressable", "use_shared_trunk": True},
        timeout=10,
    )
    recalc_response.raise_for_status()
    routes = recalc_response.json()
    assert routes
    assert routes[0]["length_m"] > 0

    specification_response = requests.get(
        f"{api_server}/api/projects/{project['id']}/equipment-specification",
        timeout=10,
    )
    specification_response.raise_for_status()
    specification = specification_response.json()

    assert [section["key"] for section in specification["sections"]] == ["kipia", "fire_resistant_cable_line"]
    kipia_rows = specification["sections"][0]["rows"]
    cable_rows = specification["sections"][1]["rows"]
    assert any(row["source_key"] == f"instrument:{instrument['id']}" and row["quantity"] == "1" for row in kipia_rows)
    assert any(row["source_key"] == f"fire_alarm:{smoke['id']}" and row["quantity"] == "1" for row in kipia_rows)
    cable_row = next(row for row in cable_rows if row["source_key"] == f"cable:{cable['id']}")
    assert cable_row["quantity"]
    assert cable_row["note"] == "Test notes"
    mounting_row = next(row for row in cable_rows if row["source_key"] == f"mounting:{mounting['id']}")
    assert mounting_row["unit"] == "шт."
    assert mounting_row["quantity"] == "1"

    updated_payload = specification
    updated_payload["page_title"] = "Спецификация проекта"
    updated_payload["sections"][0]["title"] = "КИПиА и автоматика"
    updated_payload["sections"][1]["rows"][0]["note"] = "Уточнить марку кабеля"

    update_response = requests.patch(
        f"{api_server}/api/projects/{project['id']}/equipment-specification",
        json=updated_payload,
        timeout=10,
    )
    update_response.raise_for_status()
    updated_specification = update_response.json()
    assert updated_specification["page_title"] == "Спецификация проекта"
    assert updated_specification["sections"][0]["title"] == "КИПиА и автоматика"
    assert updated_specification["sections"][1]["rows"][0]["note"] == "Уточнить марку кабеля"

    reloaded_response = requests.get(
        f"{api_server}/api/projects/{project['id']}/equipment-specification",
        timeout=10,
    )
    reloaded_response.raise_for_status()
    reloaded_specification = reloaded_response.json()
    assert reloaded_specification["page_title"] == "Спецификация проекта"
    assert reloaded_specification["sections"][0]["title"] == "КИПиА и автоматика"
    assert reloaded_specification["sections"][1]["rows"][0]["note"] == "Уточнить марку кабеля"


def test_project_power_consumption_calculation_builds_and_persists_overrides(api_server: str):
    project = _create_project(api_server)
    smoke = _create_equipment(api_server, category="smoke", name="Smoke Power")
    instrument = _create_equipment(api_server, category="instrument", name="Panel Power")
    siren = _create_equipment(api_server, category="siren", name="Siren Power")

    for equipment in (smoke, instrument, siren):
        requests.post(
            f"{api_server}/api/projects/{project['id']}/equipment",
            json={"equipment_id": equipment["id"]},
            timeout=10,
        ).raise_for_status()

    requests.patch(
        f"{api_server}/api/projects/{project['id']}/equipment-selections",
        json={
            "selections": _empty_project_selections(
                sps_smoke_detector=smoke["id"],
                common_instrument=instrument["id"],
                soue_siren=siren["id"],
            )
        },
        timeout=10,
    ).raise_for_status()

    floor_plan, _room = _prepare_validated_floor_plan(api_server, project["id"])

    requests.post(
        f"{api_server}/api/fire-alarms",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 50,
            "y": 50,
            "device_type": "smoke_detector",
            "system_type": "non_addressable",
            "equipment_id": smoke["id"],
        },
        timeout=10,
    ).raise_for_status()
    requests.post(
        f"{api_server}/api/signal-instruments",
        json={
            "floor_plan_id": floor_plan["id"],
            "system_type": "non_addressable",
            "instrument_type": "control_panel",
            "x": 10,
            "y": 10,
            "equipment_id": instrument["id"],
        },
        timeout=10,
    ).raise_for_status()
    requests.post(
        f"{api_server}/api/soue-devices",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 80,
            "y": 80,
            "device_type": "siren",
            "system_type": "non_addressable",
            "equipment_id": siren["id"],
        },
        timeout=10,
    ).raise_for_status()

    calculation_response = requests.get(
        f"{api_server}/api/projects/{project['id']}/power-consumption-calculation",
        timeout=10,
    )
    calculation_response.raise_for_status()
    calculation = calculation_response.json()

    assert calculation["categories"][0]["rows"][0]["source_key"] == f"instruments:{instrument['id']}"
    assert calculation["categories"][1]["rows"][0]["source_key"] == f"detectors:{smoke['id']}"
    assert calculation["summary_rows"][0]["key"] == "instruments_and_detectors_total"
    assert calculation["summary_rows"][-1]["key"] == "total_capacity"

    updated_payload = calculation
    updated_payload["page_title"] = "Расчет проекта"
    updated_payload["battery_voltage_v"] = "24"
    updated_payload["battery_quantity"] = "2"
    updated_payload["categories"][0]["title"] = "1. Приборы проекта"
    updated_payload["categories"][0]["rows"][0]["quantity"] = "2"
    operation_time_row = next(row for row in updated_payload["summary_rows"] if row["key"] == "operation_time")
    operation_time_row["standby"] = "12"
    operation_time_row["label"] = "Т (Режим работы), час:"

    update_response = requests.patch(
        f"{api_server}/api/projects/{project['id']}/power-consumption-calculation",
        json=updated_payload,
        timeout=10,
    )
    update_response.raise_for_status()
    updated_calculation = update_response.json()
    assert updated_calculation["page_title"] == "Расчет проекта"
    assert updated_calculation["categories"][0]["title"] == "1. Приборы проекта"
    assert updated_calculation["categories"][0]["rows"][0]["quantity"] == "2"
    assert next(row for row in updated_calculation["summary_rows"] if row["key"] == "operation_time")["standby"] == "12"
    assert updated_calculation["battery_voltage_v"] == "24"
    assert updated_calculation["battery_quantity"] == "2"
    assert updated_calculation["final_text"].endswith("24 В, 4 Ач - 2 шт.")

    reloaded_response = requests.get(
        f"{api_server}/api/projects/{project['id']}/power-consumption-calculation",
        timeout=10,
    )
    reloaded_response.raise_for_status()
    reloaded_calculation = reloaded_response.json()
    assert reloaded_calculation["page_title"] == "Расчет проекта"
    assert reloaded_calculation["categories"][0]["title"] == "1. Приборы проекта"
    assert reloaded_calculation["categories"][0]["rows"][0]["quantity"] == "2"
    assert next(row for row in reloaded_calculation["summary_rows"] if row["key"] == "operation_time")["standby"] == "12"


def test_project_power_consumption_calculation_rejects_invalid_numeric_overrides(api_server: str):
    project = _create_project(api_server)
    smoke = _create_equipment(api_server, category="smoke", name="Smoke Invalid")

    requests.post(
        f"{api_server}/api/projects/{project['id']}/equipment",
        json={"equipment_id": smoke["id"]},
        timeout=10,
    ).raise_for_status()
    requests.patch(
        f"{api_server}/api/projects/{project['id']}/equipment-selections",
        json={"selections": _empty_project_selections(sps_smoke_detector=smoke["id"])},
        timeout=10,
    ).raise_for_status()
    floor_plan, _room = _prepare_validated_floor_plan(api_server, project["id"])
    requests.post(
        f"{api_server}/api/fire-alarms",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 50,
            "y": 50,
            "device_type": "smoke_detector",
            "system_type": "non_addressable",
            "equipment_id": smoke["id"],
        },
        timeout=10,
    ).raise_for_status()

    calculation = requests.get(
        f"{api_server}/api/projects/{project['id']}/power-consumption-calculation",
        timeout=10,
    ).json()
    calculation["categories"][1]["rows"][0]["quantity"] = "abc"

    update_response = requests.patch(
        f"{api_server}/api/projects/{project['id']}/power-consumption-calculation",
        json=calculation,
        timeout=10,
    )

    assert update_response.status_code == 400
    assert update_response.json()["code"] == "power_consumption_override_invalid_number"


def test_project_general_data_get_and_patch(api_server: str):
    project = _create_project(api_server)

    read_response = requests.get(
        f"{api_server}/api/projects/{project['id']}/general-data",
        timeout=10,
    )
    read_response.raise_for_status()
    read_payload = read_response.json()
    assert read_payload["page_title"]
    assert read_payload["reference_documents"]
    assert read_payload["drawing_manifest_rows"]

    updated_payload = read_payload
    updated_payload["page_title"] = "Общие данные проекта"
    updated_payload["reference_category_title"] = "Нормативные документы"
    updated_payload["statement_text"] = "Текст подтверждения."
    updated_payload["reference_documents"][0]["designation"] = "СП 1.1"
    updated_payload["drawing_manifest_rows"][0]["name"] = "Лист общих данных"

    update_response = requests.patch(
        f"{api_server}/api/projects/{project['id']}/general-data",
        json=updated_payload,
        timeout=10,
    )
    update_response.raise_for_status()
    updated = update_response.json()
    assert updated["page_title"] == "Общие данные проекта"
    assert updated["reference_category_title"] == "Нормативные документы"
    assert updated["statement_text"] == "Текст подтверждения."
    assert updated["reference_documents"][0]["designation"] == "СП 1.1"
    assert updated["drawing_manifest_rows"][0]["name"] == "Лист общих данных"

    reread_response = requests.get(
        f"{api_server}/api/projects/{project['id']}/general-data",
        timeout=10,
    )
    reread_response.raise_for_status()
    reread = reread_response.json()
    assert reread["page_title"] == "Общие данные проекта"
    assert reread["reference_documents"][0]["designation"] == "СП 1.1"
    assert reread["drawing_manifest_rows"][0]["name"] == "Лист общих данных"


def test_project_general_instructions_get_and_patch(api_server: str):
    project = _create_project(api_server)

    read_response = requests.get(
        f"{api_server}/api/projects/{project['id']}/general-instructions",
        timeout=10,
    )
    read_response.raise_for_status()
    read_payload = read_response.json()
    assert read_payload["page_title"]
    assert read_payload["blocks"]
    assert all(block["key"] for block in read_payload["blocks"])

    updated_payload = read_payload
    updated_payload["page_title"] = "Общие указания проекта"
    updated_payload["heading"] = "ОБЩИЕ УКАЗАНИЯ ПРОЕКТА."
    updated_payload["blocks"][0]["text"] = "Вводный раздел проекта."
    first_bullet_list = next((block for block in updated_payload["blocks"] if block["kind"] == "bullet_list"), None)
    if first_bullet_list is not None:
        first_bullet_list["items"] = ["Первый пункт", "Второй пункт"]

    update_response = requests.patch(
        f"{api_server}/api/projects/{project['id']}/general-instructions",
        json=updated_payload,
        timeout=10,
    )
    update_response.raise_for_status()
    updated = update_response.json()
    assert updated["page_title"] == "Общие указания проекта"
    assert updated["heading"] == "ОБЩИЕ УКАЗАНИЯ ПРОЕКТА."
    assert updated["blocks"][0]["text"] == "Вводный раздел проекта."
    if first_bullet_list is not None:
        updated_bullet_list = next(block for block in updated["blocks"] if block["kind"] == "bullet_list")
        assert updated_bullet_list["items"] == ["Первый пункт", "Второй пункт"]

    reread_response = requests.get(
        f"{api_server}/api/projects/{project['id']}/general-instructions",
        timeout=10,
    )
    reread_response.raise_for_status()
    reread = reread_response.json()
    assert reread["page_title"] == "Общие указания проекта"
    assert reread["blocks"][0]["text"] == "Вводный раздел проекта."


def test_project_additional_info_get_and_patch(api_server: str):
    project = _create_project(api_server)

    read_response = requests.get(
        f"{api_server}/api/projects/{project['id']}/additional-info",
        timeout=10,
    )
    read_response.raise_for_status()
    read_payload = read_response.json()
    assert read_payload["text"] == ""
    assert read_payload["is_empty"] is True

    update_response = requests.patch(
        f"{api_server}/api/projects/{project['id']}/additional-info",
        json={"text": "Первый абзац.\n\nВторой абзац."},
        timeout=10,
    )
    update_response.raise_for_status()
    updated_payload = update_response.json()
    assert updated_payload["text"] == "Первый абзац.\n\nВторой абзац."
    assert updated_payload["is_empty"] is False

    reread_response = requests.get(
        f"{api_server}/api/projects/{project['id']}/additional-info",
        timeout=10,
    )
    reread_response.raise_for_status()
    reread_payload = reread_response.json()
    assert reread_payload["text"] == "Первый абзац.\n\nВторой абзац."
    assert reread_payload["is_empty"] is False


def test_security_fire_control_panel_requires_required_fields(api_server: str):
    response = requests.post(
        f"{api_server}/api/equipment",
        json={
            "name": "Panel A",
            "category": "instrument",
            "description": "Control panel",
            "price": 5000,
            "manufacturer": "Bolid",
            "service_life_years": 8,
            "notes": "No zones",
            "specs": {
                "instrument_subtype": "security_fire_control_panel",
                "shs_terminal_voltage_v": 24,
                "standby_current_a": 0.12,
                "shs_count": 4,
            },
            "compatible_equipment_ids": [],
        },
        timeout=10,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "equipment_item_missing_required_spec"


def test_security_fire_control_panel_auto_fills_alarm_current(api_server: str):
    created = _create_equipment(
        api_server,
        name="Panel Auto Alarm",
        category="instrument",
        specs={
            "instrument_subtype": "security_fire_control_panel",
            "shs_terminal_voltage_v": 24,
            "standby_current_a": 0.12,
            "shs_count": 4,
            "zone_count": 8,
        },
    )

    assert created["specs"]["instrument_subtype"] == "security_fire_control_panel"
    assert created["specs"]["alarm_current_a"] == pytest.approx(0.12)


def test_control_and_management_console_requires_console_fields(api_server: str):
    response = requests.post(
        f"{api_server}/api/equipment",
        json={
            "name": "Console A",
            "category": "instrument",
            "description": "Console",
            "price": 5000,
            "manufacturer": "Bolid",
            "service_life_years": 8,
            "notes": "No currents",
            "specs": {
                "instrument_subtype": "control_and_management_console",
                "sections_count": 4,
                "section_groups_count": 2,
                "supply_voltage_v": 24,
            },
            "compatible_equipment_ids": [],
        },
        timeout=10,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "equipment_item_missing_required_spec"


def test_indication_unit_auto_fills_alarm_current(api_server: str):
    created = _create_equipment(
        api_server,
        name="Indicator A",
        category="instrument",
        specs={
            "instrument_subtype": "indication_unit",
            "supply_voltage_v": {"min": 12, "max": 24},
            "standby_current_a": 0.05,
        },
    )

    assert created["specs"]["instrument_subtype"] == "indication_unit"
    assert created["specs"]["supply_voltage_v"] == {"min": 12.0, "max": 24.0}
    assert created["specs"]["alarm_current_a"] == pytest.approx(0.05)


def test_instrument_rejects_legacy_payload_fields(api_server: str):
    response = requests.post(
        f"{api_server}/api/equipment",
        json={
            "name": "Legacy Panel Payload",
            "category": "instrument",
            "description": "Legacy panel",
            "price": 5000,
            "manufacturer": "Bolid",
            "service_life_years": 8,
            "notes": "Legacy payload",
            "specs": {
                "instrument_subtype": "security_fire_control_panel",
                "supported_sps_mode": "addressable",
                "power_dc_v": 24,
                "controller_current_12v_ma": 110,
                "controller_current_24v_ma": 70,
                "shs_count": 4,
                "zone_count": 8,
                "shs_terminal_voltage_v": 24,
                "standby_current_a": 0.12,
            },
            "compatible_equipment_ids": [],
        },
        timeout=10,
    )

    assert response.status_code == 400
    assert response.json()["code"] == "equipment_item_invalid_spec_value"


def test_equipment_delete_is_blocked_by_compatibility_and_project_usage(api_server: str):
    smoke = _create_equipment(api_server, name="Smoke A")
    heat = _create_equipment(api_server, name="Heat A", category="heat", price=900)

    update_response = requests.patch(
        f"{api_server}/api/equipment/{smoke['id']}",
        json={"compatible_equipment_ids": [heat["id"]]},
        timeout=10,
    )
    update_response.raise_for_status()

    delete_response = requests.delete(f"{api_server}/api/equipment/{smoke['id']}", timeout=10)
    assert delete_response.status_code == 409
    assert delete_response.json()["code"] == "equipment_item_has_compatibility_links"

    requests.patch(
        f"{api_server}/api/equipment/{smoke['id']}",
        json={"compatible_equipment_ids": []},
        timeout=10,
    ).raise_for_status()

    project = _create_project(api_server)
    selection_response = requests.patch(
        f"{api_server}/api/projects/{project['id']}/equipment-selections",
        json={"selections": _empty_project_selections(sps_smoke_detector=smoke["id"])},
        timeout=10,
    )
    selection_response.raise_for_status()

    delete_response = requests.delete(f"{api_server}/api/equipment/{smoke['id']}", timeout=10)
    assert delete_response.status_code == 409
    assert delete_response.json()["code"] == "equipment_item_in_use"


def test_project_equipment_selections_validate_category_and_persist(api_server: str):
    project = _create_project(api_server)
    smoke = _create_equipment(api_server, name="Smoke A")
    siren = _create_equipment(api_server, name="Siren A", category="siren", price=750)

    valid_response = requests.patch(
        f"{api_server}/api/projects/{project['id']}/equipment-selections",
        json={"selections": _empty_project_selections(sps_smoke_detector=smoke["id"], soue_siren=siren["id"])},
        timeout=10,
    )
    valid_response.raise_for_status()
    valid_payload = valid_response.json()
    assert valid_payload["selections"]["sps_smoke_detector"] == smoke["id"]
    assert valid_payload["selections"]["soue_siren"] == siren["id"]

    read_response = requests.get(f"{api_server}/api/projects/{project['id']}/equipment-selections", timeout=10)
    read_response.raise_for_status()
    assert read_response.json()["selections"]["sps_smoke_detector"] == smoke["id"]

    invalid_response = requests.patch(
        f"{api_server}/api/projects/{project['id']}/equipment-selections",
        json={"selections": _empty_project_selections(sps_smoke_detector=siren["id"])},
        timeout=10,
    )
    assert invalid_response.status_code == 400
    assert invalid_response.json()["code"] == "project_equipment_category_mismatch"


def test_list_items_maps_legacy_control_panel_specs_for_read(api_server: str):
    created = _create_equipment(
        api_server,
        name="Legacy Control Panel",
        category="instrument",
        specs={
            "instrument_subtype": "security_fire_control_panel",
            "shs_terminal_voltage_v": 24,
            "standby_current_a": 0.12,
            "alarm_current_a": 0.18,
            "shs_count": 4,
            "zone_count": 8,
        },
    )

    db = database.SessionLocal()
    try:
        item = db.query(EquipmentItem).filter(EquipmentItem.id == created["id"]).one()
        item.specs = {
            "instrument_subtype": "control_panel",
            "supported_sps_mode": "addressable",
            "power_dc_v": 24,
            "controller_current_12v_ma": 110,
            "controller_current_24v_ma": 70,
            "shs_count": 4,
            "zone_count": 8,
        }
        db.commit()
        legacy_id = item.id
    finally:
        db.close()

    response = requests.get(f"{api_server}/api/equipment/{legacy_id}", timeout=10)
    response.raise_for_status()
    payload = response.json()

    assert payload["specs"]["instrument_subtype"] == "security_fire_control_panel"
    assert payload["specs"]["zone_count"] == 8
    assert payload["specs"]["shs_count"] == 4
    assert "power_dc_v" not in payload["specs"]
    assert "controller_current_12v_ma" not in payload["specs"]


def test_init_db_backfills_legacy_smoke_fields_into_specs(isolated_database):
    db = database.SessionLocal()
    try:
        db.connection().exec_driver_sql(
            """
            INSERT INTO equipment_items (
                name,
                category,
                description,
                price,
                coverage_summary,
                standby_current_ma,
                alarm_current_ma,
                smoke_addressing,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (
                "Legacy Smoke",
                "smoke",
                "Legacy detector",
                123.45,
                "До 85 м²",
                0.1,
                0.3,
                "addressable",
            ),
        )
        db.commit()
        database.init_db()
    finally:
        db.close()

    verification_session = database.SessionLocal()
    try:
        item = verification_session.query(EquipmentItem).filter(EquipmentItem.name == "Legacy Smoke").one()
        assert item.specs["addressing_mode"] == "addressable"
        assert item.specs["standby_current_a"] == pytest.approx(0.0001)
        assert item.specs["alarm_current_a"] == pytest.approx(0.0003)
    finally:
        verification_session.close()
