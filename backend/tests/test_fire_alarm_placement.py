from __future__ import annotations

from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from backend.fire_alarm_placement import (
    FireAlarmPlacement,
    _detector_symbol_spacing_px,
    _refine_detector_positions_for_drawing,
    calculate_fire_alarm_layout,
    locate_fire_alarm_metadata,
)
from backend.signal_planning import (
    _build_polyline,
    _wall_crossing_summary,
    calculate_zkspc_layout,
    recalculate_cable_routes,
)


def _room_polygon(room: dict, scale_factor: float) -> Polygon:
    meters_per_pixel = scale_factor / 1000.0
    return Polygon(
        [
            (float(point[0]) * meters_per_pixel, float(point[1]) * meters_per_pixel)
            for point in room["boundary_points"]
        ]
    ).buffer(0)


def _detector_disks(room: dict, detectors: list[dict], scale_factor: float):
    meters_per_pixel = scale_factor / 1000.0
    polygon = _room_polygon(room, scale_factor)
    disks = []
    for detector in detectors:
        if detector.get("device_type") != "smoke_detector":
            continue
        radius_mm = detector.get("coverage_radius")
        if radius_mm is None:
            continue
        disks.append(
            Point(
                float(detector["x"]) * meters_per_pixel,
                float(detector["y"]) * meters_per_pixel,
            ).buffer(float(radius_mm) / 1000.0, quad_segs=32).intersection(polygon)
        )
    return polygon, disks


def _assert_exact_room_coverage(room: dict, detectors: list[dict], scale_factor: float, multiplicity: int) -> None:
    polygon, disks = _detector_disks(room, detectors, scale_factor)
    if multiplicity == 1:
        covered = unary_union(disks) if disks else Polygon()
    else:
        covered_once = Polygon()
        covered_twice = Polygon()
        for disk in disks:
            if covered_once.is_empty:
                covered_once = disk
                continue
            overlap = covered_once.intersection(disk)
            covered_twice = overlap if covered_twice.is_empty else unary_union([covered_twice, overlap])
            covered_once = unary_union([covered_once, disk])
        covered = covered_twice
    uncovered = polygon.difference(covered)
    assert uncovered.area <= 1e-4


def test_addressable_layout_minimizes_detectors_for_square_room():
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
        system_type="addressable",
    )

    detectors = layout["detectors"]
    assert len(detectors) == 2
    assert layout["summary"]["smoke_detectors"] == 2
    _assert_exact_room_coverage(room, detectors, scale_factor=100.0, multiplicity=1)


def test_non_addressable_layout_minimizes_detectors_for_square_room():
    room = {
        "id": 102,
        "name": "Room 2",
        "room_type": "general",
        "boundary_points": [[0, 0], [80, 0], [80, 80], [0, 80]],
        "area_sqm": 64.0,
        "center_x": 40,
        "center_y": 40,
    }

    layout = calculate_fire_alarm_layout(
        {"rooms": [room], "doors": [], "stairs": [], "walls": []},
        scale_factor=100.0,
        system_type="non_addressable",
    )

    detectors = layout["detectors"]
    assert len(detectors) == 4
    assert layout["summary"]["smoke_detectors"] == 4
    _assert_exact_room_coverage(room, detectors, scale_factor=100.0, multiplicity=2)


def test_long_corridor_receives_full_coverage_without_extra_addressable_detectors():
    room = {
        "id": 103,
        "name": "Corridor",
        "room_type": "general",
        "boundary_points": [[0, 0], [180, 0], [180, 20], [0, 20]],
        "area_sqm": 36.0,
        "center_x": 90,
        "center_y": 10,
    }

    layout = calculate_fire_alarm_layout(
        {"rooms": [room], "doors": [], "stairs": [], "walls": []},
        scale_factor=100.0,
        system_type="addressable",
    )

    detectors = layout["detectors"]
    assert len(detectors) == 3
    _assert_exact_room_coverage(room, detectors, scale_factor=100.0, multiplicity=1)


def test_l_shaped_room_has_no_uncovered_inner_pocket():
    room = {
        "id": 104,
        "name": "L Room",
        "room_type": "general",
        "boundary_points": [[0, 0], [100, 0], [100, 40], [40, 40], [40, 100], [0, 100]],
        "area_sqm": 76.0,
        "center_x": 35,
        "center_y": 35,
    }

    layout = calculate_fire_alarm_layout(
        {"rooms": [room], "doors": [], "stairs": [], "walls": []},
        scale_factor=100.0,
        system_type="addressable",
    )

    _assert_exact_room_coverage(room, layout["detectors"], scale_factor=100.0, multiplicity=1)


def test_complex_non_addressable_room_falls_back_without_hanging():
    room = {
        "id": 13,
        "name": "Complex room",
        "room_type": "general",
        "center_x": 639.4285714285714,
        "center_y": 375.85714285714283,
        "boundary_points": [
            [1096.0, 61.0],
            [708.0, 61.0],
            [684.0, 438.0],
            [680.0, 314.0],
            [306.0, 314.0],
            [300.0, 418.0],
            [34.0, 404.0],
            [34.0, 643.0],
            [671.0, 643.0],
            [674.0, 479.0],
            [698.0, 661.0],
            [1096.0, 661.0],
            [1096.0, 84.0],
            [875.0, 81.0],
        ],
    }

    layout = calculate_fire_alarm_layout(
        {"rooms": [room], "doors": [], "stairs": [], "walls": []},
        scale_factor=16.37353128882235,
        system_type="non_addressable",
    )

    assert len(layout["detectors"]) > 0
    assert any("approximate detector placement" in warning for warning in layout["warnings"])


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

    detector_points = {(round(float(device["x"]), 3), round(float(device["y"]), 3)) for device in layout["detectors"]}
    assert len(layout["detectors"]) == 2
    assert len(detector_points) == 2
    _assert_exact_room_coverage(
        {
            "id": 7,
            "name": "Tiny",
            "room_type": "general",
            "boundary_points": [[0, 0], [20, 0], [20, 20], [0, 20]],
        },
        layout["detectors"],
        scale_factor=100.0,
        multiplicity=2,
    )


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


def test_layout_preserves_room_and_zone_metadata_for_detectors():
    room = {
        "id": 21,
        "name": "Zone Room",
        "room_type": "general",
        "boundary_points": [[0, 0], [80, 0], [80, 80], [0, 80]],
        "area_sqm": 64.0,
        "center_x": 40,
        "center_y": 40,
    }

    layout = calculate_fire_alarm_layout(
        {"rooms": [room], "doors": [], "stairs": [], "walls": []},
        scale_factor=100.0,
        system_type="addressable",
        zkspc_zones=[{"id": 7, "zone_number": 3, "room_ids": [21]}],
    )

    assert layout["detectors"]
    assert {device["room_id"] for device in layout["detectors"]} == {21}
    assert {device["zkspc_zone_id"] for device in layout["detectors"]} == {7}
    assert {device["zone"] for device in layout["detectors"]} == {"3"}


def test_non_addressable_layout_warns_when_full_coverage_exceeds_zone_limit():
    rooms = []
    for index in range(11):
        x = float(index * 20)
        rooms.append(
            {
                "id": index + 1,
                "name": f"R{index + 1}",
                "room_type": "general",
                "boundary_points": [[x, 0], [x + 10, 0], [x + 10, 10], [x, 10]],
                "area_sqm": 1.0,
                "center_x": x + 5,
                "center_y": 5,
            }
        )

    layout = calculate_fire_alarm_layout(
        {"rooms": rooms, "doors": [], "stairs": [], "walls": []},
        scale_factor=100.0,
        system_type="non_addressable",
    )

    assert any("превышает лимит 20" in warning for warning in layout["warnings"])


def test_addressable_layout_warns_when_full_coverage_exceeds_zone_limit():
    rooms = []
    for index in range(33):
        x = float((index % 11) * 20)
        y = float((index // 11) * 20)
        rooms.append(
            {
                "id": index + 1,
                "name": f"A{index + 1}",
                "room_type": "general",
                "boundary_points": [[x, y], [x + 10, y], [x + 10, y + 10], [x, y + 10]],
                "area_sqm": 1.0,
                "center_x": x + 5,
                "center_y": y + 5,
            }
        )

    layout = calculate_fire_alarm_layout(
        {"rooms": rooms, "doors": [], "stairs": [], "walls": []},
        scale_factor=100.0,
        system_type="addressable",
    )

    assert any("превышает лимит 32" in warning for warning in layout["warnings"])


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
    assert {device["loop_number"] for device in manual_points} == {2, 3}
    assert {device["device_number"] for device in manual_points} == {1}
    assert all(device["x"] > 60 for device in manual_points)

    routes = recalculate_cable_routes(
        {"scale_factor": 100.0, "walls": []},
        system_type="non_addressable",
        instrument={"id": 99, "x": 10.0, "y": 10.0},
        alarms=manual_points,
    )
    manual_routes = [route for route in routes if route["route_kind"] == "manual_line"]
    assert len(manual_routes) == 2
    assert {route["route_number"] for route in manual_routes} == {2, 3}
    assert all(len(route["device_ids"]) == 1 for route in manual_routes)
    assert all(route["polyline_points"][0] != route["polyline_points"][-1] for route in manual_routes)


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


def test_manual_call_points_are_not_created_for_internal_stair_door():
    layout = calculate_fire_alarm_layout(
        {
            "rooms": [
                {
                    "id": 21,
                    "name": "Office",
                    "room_type": "general",
                    "boundary_points": [[0, 0], [100, 0], [100, 100], [0, 100]],
                    "area_sqm": 100.0,
                    "center_x": 50,
                    "center_y": 50,
                },
                {
                    "id": 22,
                    "name": "Stair",
                    "room_type": "РЅРµРѕР±СЃР»СѓР¶РёРІР°РµРјРѕРµ",
                    "boundary_points": [[100, 0], [180, 0], [180, 100], [100, 100]],
                    "area_sqm": 80.0,
                    "center_x": 140,
                    "center_y": 50,
                },
            ],
            "doors": [
                {"id": 1, "x": 95, "y": 40, "width": 10, "height": 20, "rotation_deg": 90, "wall_id": 1},
            ],
            "stairs": [
                {"id": 1, "x": 120, "y": 25, "width": 30, "height": 50},
            ],
            "walls": [
                {"id": 1, "x1": 100, "y1": 0, "x2": 100, "y2": 100},
            ],
        },
        scale_factor=100.0,
    )

    assert layout["manual_call_points"] == []


def test_manual_call_points_are_created_for_stair_room_external_door():
    layout = calculate_fire_alarm_layout(
        {
            "rooms": [
                {
                    "id": 31,
                    "name": "Stair",
                    "room_type": "РЅРµРѕР±СЃР»СѓР¶РёРІР°РµРјРѕРµ",
                    "boundary_points": [[0, 0], [100, 0], [100, 100], [0, 100]],
                    "area_sqm": 100.0,
                    "center_x": 50,
                    "center_y": 50,
                }
            ],
            "doors": [
                {"id": 1, "x": 40, "y": -5, "width": 20, "height": 10, "rotation_deg": 0, "wall_id": 1},
            ],
            "stairs": [
                {"id": 1, "x": 30, "y": 20, "width": 40, "height": 40},
            ],
            "walls": [
                {"id": 1, "x1": 0, "y1": 0, "x2": 100, "y2": 0},
            ],
        },
        scale_factor=100.0,
    )

    assert len(layout["manual_call_points"]) == 1
    assert layout["manual_call_points"][0]["device_type"] == "manual_call_point"


def test_detector_symbol_spacing_keeps_half_symbol_gap_between_edges():
    assert _detector_symbol_spacing_px(10.0) == 42.0
    assert _detector_symbol_spacing_px(100.0) == 42.0


def test_non_addressable_refinement_pushes_smoke_detectors_apart_to_visual_minimum():
    room = {
        "id": 555,
        "name": "Wide Room",
        "room_type": "general",
        "boundary_points": [[0, 0], [120, 0], [120, 120], [0, 120]],
        "area_sqm": 144.0,
        "center_x": 60,
        "center_y": 60,
    }

    refined, has_overlap = _refine_detector_positions_for_drawing(
        room,
        [(58.0, 60.0), (62.0, 60.0)],
        radius_px=100.0,
        scale_factor=100.0,
        coverage_need=1,
    )

    assert has_overlap is False
    min_spacing = _detector_symbol_spacing_px(100.0)
    for left_index in range(len(refined) - 1):
        for right_index in range(left_index + 1, len(refined)):
            left = refined[left_index]
            right = refined[right_index]
            distance = ((left[0] - right[0]) ** 2 + (left[1] - right[1]) ** 2) ** 0.5
            assert distance >= min_spacing - 1e-6


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


def test_recalculate_cable_routes_ignores_shared_trunk_and_deduplicates_devices():
    floor_plan = {"scale_factor": 100.0, "walls": []}
    instrument = {"id": 99, "x": 0.0, "y": 0.0}
    alarms = [
        {"id": 11, "device_type": "smoke_detector", "loop_number": 1, "device_number": 2, "x": 30.0, "y": 10.0},
        {"id": 10, "device_type": "smoke_detector", "loop_number": 1, "device_number": 1, "x": 10.0, "y": 10.0},
        {"id": 10, "device_type": "smoke_detector", "loop_number": 1, "device_number": 1, "x": 10.0, "y": 10.0},
        {"id": 21, "device_type": "smoke_detector", "loop_number": 2, "device_number": 1, "x": 10.0, "y": 30.0},
    ]

    without_merge = recalculate_cable_routes(
        floor_plan,
        system_type="non_addressable",
        instrument=instrument,
        alarms=alarms,
        use_shared_trunk=False,
    )
    with_merge_flag = recalculate_cable_routes(
        floor_plan,
        system_type="non_addressable",
        instrument=instrument,
        alarms=alarms,
        use_shared_trunk=True,
    )

    assert with_merge_flag == without_merge
    assert len(with_merge_flag) == 2
    assert [route["route_number"] for route in with_merge_flag] == [1, 2]
    assert with_merge_flag[0]["device_ids"] == [10, 11]
    assert with_merge_flag[1]["device_ids"] == [21]
    assert all(route["polyline_points"][0] == [0.0, 0.0] for route in with_merge_flag)
    flattened_device_ids = [device_id for route in with_merge_flag for device_id in route["device_ids"]]
    assert flattened_device_ids == [10, 11, 21]


def test_non_addressable_route_appends_zc_terminal_point():
    routes = recalculate_cable_routes(
        {"scale_factor": 100.0, "walls": []},
        system_type="non_addressable",
        instrument={"id": 77, "x": 0.0, "y": 0.0},
        alarms=[
            {"id": 1, "device_type": "smoke_detector", "loop_number": 1, "device_number": 1, "x": 20.0, "y": 0.0},
            {"id": 2, "device_type": "smoke_detector", "loop_number": 1, "device_number": 2, "x": 40.0, "y": 0.0},
        ],
    )

    assert len(routes) == 1
    route = routes[0]
    assert route["route_kind"] == "zone_loop"
    assert route["device_ids"] == [1, 2]
    assert route["polyline_points"][-3] == [26.0, 0.0]
    assert route["polyline_points"][-2] == [40.0, 0.0]
    assert route["polyline_points"][-1] == [59.4, 0.0]


def test_intermediate_device_uses_different_entry_and_exit_sides():
    routes = recalculate_cable_routes(
        {"scale_factor": 100.0, "walls": []},
        system_type="addressable",
        instrument={"id": 55, "x": 0.0, "y": 0.0},
        alarms=[
            {"id": 1, "device_type": "smoke_detector", "address": "1", "x": 40.0, "y": 0.0},
            {"id": 2, "device_type": "smoke_detector", "address": "2", "x": 40.0, "y": 40.0},
        ],
    )

    route = routes[0]
    points = route["polyline_points"]
    assert [26.0, 0.0] in points
    assert [40.0, 14.0] in points
    assert points.index([26.0, 0.0]) < points.index([40.0, 14.0])


def test_non_addressable_zc_uses_alternative_side_when_forward_side_is_blocked():
    routes = recalculate_cable_routes(
        {
            "scale_factor": 100.0,
            "walls": [{"id": 1, "x1": 50.0, "y1": -20.0, "x2": 50.0, "y2": 20.0}],
        },
        system_type="non_addressable",
        instrument={"id": 77, "x": 0.0, "y": 0.0},
        alarms=[
            {"id": 1, "device_type": "smoke_detector", "loop_number": 1, "device_number": 1, "x": 40.0, "y": 0.0},
        ],
    )

    route = routes[0]
    assert route["polyline_points"][-2] == [40.0, 0.0]
    assert route["polyline_points"][-1] == [40.0, -19.4]


def test_addressable_routes_form_ring_without_duplicate_device_ids():
    routes = recalculate_cable_routes(
        {"scale_factor": 100.0, "walls": []},
        system_type="addressable",
        instrument={"id": 88, "x": 0.0, "y": 0.0},
        alarms=[
            {"id": 1, "device_type": "smoke_detector", "address": "3", "x": 50.0, "y": 10.0},
            {"id": 2, "device_type": "manual_call_point", "address": "1", "x": 15.0, "y": 45.0},
            {"id": 3, "device_type": "smoke_detector", "address": "2", "x": 35.0, "y": 30.0},
        ],
    )

    assert len(routes) == 1
    route = routes[0]
    assert route["route_kind"] == "ring"
    assert route["polyline_points"][0] == [0.0, 0.0]
    assert route["polyline_points"][-1] == [0.0, 0.0]
    assert sorted(route["device_ids"]) == [1, 2, 3]
    assert len(route["device_ids"]) == len(set(route["device_ids"]))


def test_single_device_addressable_ring_uses_separate_return_leg():
    routes = recalculate_cable_routes(
        {"scale_factor": 100.0, "walls": []},
        system_type="addressable",
        instrument={"id": 99, "x": 0.0, "y": 0.0},
        alarms=[
            {"id": 10, "device_type": "smoke_detector", "address": "1", "x": 0.0, "y": 40.0},
        ],
    )

    route = routes[0]
    assert route["polyline_points"][0] == [0.0, 0.0]
    assert route["polyline_points"][-1] == [0.0, 0.0]
    assert len(route["polyline_points"]) > 4


def test_polyline_prefers_reusing_wall_crossing_point_when_route_crosses_same_wall_twice():
    walls = [
        {"id": 1, "x1": 50.0, "y1": 0.0, "x2": 50.0, "y2": 120.0},
    ]

    polyline = _build_polyline(
        start=(0.0, 20.0),
        targets=[(100.0, 20.0), (0.0, 80.0)],
        walls=walls,
        close_ring=False,
        trunk_anchor=None,
    )
    crossings, repeated_spread = _wall_crossing_summary(
        [(float(point[0]), float(point[1])) for point in polyline],
        walls,
    )

    assert polyline == [[0.0, 20.0], [100.0, 20.0], [0.0, 20.0], [0.0, 80.0]]
    assert crossings == 2
    assert repeated_spread == 0.0
