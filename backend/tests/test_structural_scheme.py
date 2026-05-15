from __future__ import annotations

from types import SimpleNamespace

from backend.modules.documents.structural_scheme import build_project_structural_scheme


def _equipment(equipment_id: int, name: str, category: str):
    return SimpleNamespace(
        id=equipment_id,
        name=name,
        category=category,
        manufacturer="",
        specs={"addressing_mode": "addressable"} if category == "smoke" else {},
    )


def test_build_project_structural_scheme_aggregates_zones_routes_and_equipment():
    smoke = _equipment(1, "ДИП-34А", "smoke")
    siren = _equipment(2, "Свирель", "siren")
    panel = _equipment(3, "С2000М", "instrument")
    project = SimpleNamespace(id=7, facility="Административное здание", code="PS-7", equipment_selections=[])
    zone = SimpleNamespace(id=10, zone_number=3, name="", area_sqm=42.5, room_count=2)
    floor = SimpleNamespace(
        id=100,
        name="",
        floor_number=2,
        building_name="Литер А",
        zkspc_zones=[zone],
        fire_alarms=[],
        soue_devices=[],
        signal_instruments=[],
        cable_routes=[],
    )
    alarm_1 = SimpleNamespace(
        id=21,
        floor_plan=floor,
        device_type="smoke_detector",
        equipment=smoke,
        zkspc_zone_id=10,
        loop_number=1,
        device_number=1,
    )
    alarm_2 = SimpleNamespace(
        id=22,
        floor_plan=floor,
        device_type="smoke_detector",
        equipment=smoke,
        zkspc_zone_id=10,
        loop_number=1,
        device_number=2,
    )
    soue_device = SimpleNamespace(
        id=31,
        floor_plan=floor,
        device_type="siren",
        equipment=siren,
        loop_number=2,
        device_number=1,
    )
    instrument = SimpleNamespace(
        id=41,
        floor_plan=floor,
        instrument_type="control_panel",
        equipment=panel,
        name="ППКП",
    )
    route_sps = SimpleNamespace(
        id=51,
        subsystem_type="sps",
        route_kind="address_loop",
        route_number=1,
        instrument_id=41,
        device_ids=[21, 22],
        length_m=35.4,
    )
    route_soue = SimpleNamespace(
        id=52,
        subsystem_type="soue",
        route_kind="siren_loop",
        route_number=2,
        instrument_id=41,
        device_ids=[31],
        length_m=11.2,
    )
    floor.fire_alarms = [alarm_1, alarm_2]
    floor.soue_devices = [soue_device]
    floor.signal_instruments = [instrument]
    floor.cable_routes = [route_sps, route_soue]

    payload = build_project_structural_scheme(project, [floor])

    assert payload["facility"] == "Административное здание"
    assert payload["floors"][0]["building_label"] == "Литер А"
    assert payload["floors"][0]["title"] == "Этаж 2"
    zone_group = payload["floors"][0]["zones"][0]
    assert zone_group["title"] == "ЗКСПС №3"
    assert zone_group["area_sqm"] == 42.5
    assert zone_group["sps_items"][0]["quantity"] == 2
    assert zone_group["sps_items"][0]["device_ids"] == [21, 22]
    soue_group = payload["floors"][0]["zones"][1]
    assert soue_group["title"] == "СОУЭ"
    assert soue_group["soue_items"][0]["quantity"] == 1
    assert soue_group["soue_items"][0]["device_ids"] == [31]
    assert {route["key"] for route in payload["floors"][0]["routes"]} == {"route:51", "route:52"}
    route_by_key = {route["key"]: route for route in payload["floors"][0]["routes"]}
    assert route_by_key["route:51"]["target_device_ids"] == [21, 22]
    assert route_by_key["route:52"]["target_device_ids"] == [31]
    assert any(item["quantity"] == 2 and item["category"] == "smoke" for item in payload["equipment_totals"])
    assert any(item["quantity"] == 1 and item["category"] == "instrument" for item in payload["equipment_totals"])
