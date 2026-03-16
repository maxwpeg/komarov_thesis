from __future__ import annotations

from backend.fire_alarm_placement import calculate_fire_alarm_layout, locate_fire_alarm_metadata
from backend.signal_planning import calculate_zkspc_layout, recalculate_cable_routes


def _coverage_count(point: tuple[float, float], devices: list[dict]) -> int:
    covered = 0
    for device in devices:
        radius_mm = device.get("coverage_radius")
        if device.get("device_type") != "smoke_detector" or radius_mm is None:
            continue
        dx = device["x"] - point[0]
        dy = device["y"] - point[1]
        if (dx * dx + dy * dy) ** 0.5 <= radius_mm / 100.0 + 1e-6:
            covered += 1
    return covered


def test_calculate_fire_alarm_layout_provides_double_coverage_for_room():
    room = {
        "id": 101,
        "name": "Room 1",
        "room_type": "general",
        "boundary_points": [[0, 0], [80, 0], [80, 80], [0, 80]],
        "area_sqm": 64.0,
        "center_x": 40,
        "center_y": 40,
    }

    layout = calculate_fire_alarm_layout(
        {"rooms": [room], "doors": [], "stairs": [], "walls": []},
        scale_factor=100.0,
    )

    detectors = layout["detectors"]
    assert len(detectors) >= 2
    assert layout["summary"]["smoke_detectors"] == len(detectors)

    for x in range(6, 75, 6):
        for y in range(6, 75, 6):
            assert _coverage_count((x, y), detectors) >= 2


def test_small_room_still_receives_two_smoke_detectors():
    layout = calculate_fire_alarm_layout(
        {
            "rooms": [
                {
                    "id": 7,
                    "name": "Tiny",
                    "room_type": "general",
                    "boundary_points": [[0, 0], [20, 0], [20, 20], [0, 20]],
                    "area_sqm": 4.0,
                    "center_x": 10,
                    "center_y": 10,
                }
            ],
            "doors": [],
            "stairs": [],
            "walls": [],
        },
        scale_factor=100.0,
    )

    assert len(layout["detectors"]) >= 2


def test_unserviceable_room_is_skipped():
    layout = calculate_fire_alarm_layout(
        {
            "rooms": [
                {
                    "id": 9,
                    "name": "Service",
                    "room_type": "необслуживаемое",
                    "boundary_points": [[0, 0], [50, 0], [50, 50], [0, 50]],
                    "area_sqm": 25.0,
                    "center_x": 25,
                    "center_y": 25,
                }
            ],
            "doors": [],
            "stairs": [],
            "walls": [],
        },
        scale_factor=100.0,
    )

    assert layout["detectors"] == []


def test_unserviceable_room_is_excluded_from_zkspc_layout():
    zones = calculate_zkspc_layout(
        [
            {
                "id": 1,
                "name": "Serviceable",
                "room_type": "general",
                "boundary_points": [[0, 0], [40, 0], [40, 40], [0, 40]],
                "area_sqm": 16.0,
            },
            {
                "id": 2,
                "name": "Skipped",
                "room_type": "необслуживаемое",
                "boundary_points": [[60, 0], [100, 0], [100, 40], [60, 40]],
                "area_sqm": 16.0,
            },
        ]
    )

    assert len(zones) == 1
    assert zones[0]["room_ids"] == [1]


def test_manual_call_points_are_created_for_external_and_stair_doors():
    layout = calculate_fire_alarm_layout(
        {
            "rooms": [
                {
                    "id": 11,
                    "name": "Hall",
                    "room_type": "general",
                    "boundary_points": [[0, 0], [100, 0], [100, 100], [0, 100]],
                    "area_sqm": 100.0,
                    "center_x": 50,
                    "center_y": 50,
                }
            ],
            "doors": [
                {"id": 1, "x": 40, "y": -5, "width": 20, "height": 10, "rotation_deg": 0, "wall_id": 1},
                {"id": 2, "x": 40, "y": 95, "width": 20, "height": 10, "rotation_deg": 0, "wall_id": 2},
            ],
            "stairs": [
                {"id": 1, "x": 30, "y": 105, "width": 40, "height": 30},
            ],
            "walls": [
                {"id": 1, "x1": 0, "y1": 0, "x2": 100, "y2": 0},
                {"id": 2, "x1": 0, "y1": 100, "x2": 100, "y2": 100},
            ],
        },
        scale_factor=100.0,
    )

    manual_points = layout["manual_call_points"]
    assert len(manual_points) == 2
    assert all(device["device_type"] == "manual_call_point" for device in manual_points)
    assert {device["loop_kind"] for device in manual_points} == {"manual_line"}
    assert {device["loop_number"] for device in manual_points} == {2}
    assert [device["device_number"] for device in sorted(manual_points, key=lambda item: item["device_number"])] == [1, 2]

    routes = recalculate_cable_routes(
        {"scale_factor": 100.0, "walls": []},
        system_type="non_addressable",
        instrument={"id": 99, "x": 10.0, "y": 10.0},
        alarms=manual_points,
    )
    manual_routes = [route for route in routes if route["route_kind"] == "manual_line"]
    assert len(manual_routes) == 1
    assert manual_routes[0]["polyline_points"][0] != manual_routes[0]["polyline_points"][-1]


def test_manual_call_points_are_not_created_for_unserviceable_room():
    layout = calculate_fire_alarm_layout(
        {
            "rooms": [
                {
                    "id": 15,
                    "name": "Stair lobby",
                    "room_type": "необслуживаемое",
                    "boundary_points": [[0, 0], [100, 0], [100, 100], [0, 100]],
                    "area_sqm": 100.0,
                    "center_x": 50,
                    "center_y": 50,
                }
            ],
            "doors": [
                {"id": 1, "x": 40, "y": -5, "width": 20, "height": 10, "rotation_deg": 0, "wall_id": 1},
            ],
            "stairs": [],
            "walls": [
                {"id": 1, "x1": 0, "y1": 0, "x2": 100, "y2": 0},
            ],
        },
        scale_factor=100.0,
    )

    assert layout["manual_call_points"] == []


def test_locate_fire_alarm_metadata_returns_room_offsets_in_meters():
    metadata = locate_fire_alarm_metadata(
        x=35.0,
        y=25.0,
        rooms=[
            {
                "id": 77,
                "boundary_points": [[10, 10], [60, 10], [60, 40], [10, 40]],
            }
        ],
        scale_factor=100.0,
    )

    assert metadata["room_id"] == 77
    assert metadata["offset_left_m"] == 2.5
    assert metadata["offset_top_m"] == 1.5
