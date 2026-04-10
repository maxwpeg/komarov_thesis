"""Pipeline API integration tests."""

from __future__ import annotations

import math
from pathlib import Path

import requests
from PIL import Image


def create_project(base_url: str) -> dict:
    response = requests.post(
        f"{base_url}/api/projects",
        json={
            "name": "Pipeline Test Project",
            "project_type": "PS",
            "contractor": "Test Contractor",
            "engineer": "Test Engineer",
            "cpe": "Test CPE",
            "checker": "Test Checker",
            "facility": "Test Facility",
            "facility_address": "Test Address",
            "project_description": "Pipeline tests",
            "stage": "R",
            "number_of_floors": 1,
        },
        timeout=10,
    )
    assert response.status_code == 200
    return response.json()


def create_floor_plan(
    base_url: str,
    project_id: int,
    scale_factor: float = 10.0,
    image_path: Path | None = None,
) -> dict:
    data = {
        "project_id": str(project_id),
        "floor_number": "1",
        "name": "Floor 1",
        "scale_factor": str(scale_factor),
    }
    if image_path is None:
        response = requests.post(
            f"{base_url}/api/floor-plans",
            data=data,
            timeout=10,
        )
    else:
        with image_path.open("rb") as image_file:
            response = requests.post(
                f"{base_url}/api/floor-plans",
                data=data,
                files={"file": ("floor.png", image_file, "image/png")},
                timeout=10,
            )
    assert response.status_code == 200
    return response.json()


def create_wall(
    base_url: str,
    floor_plan_id: int,
    *,
    x1: float = 0,
    y1: float = 0,
    x2: float = 100,
    y2: float = 0,
    thickness: float = 200,
    length_m: float | None = None,
    length_source: str | None = None,
) -> dict:
    payload = {
        "floor_plan_id": floor_plan_id,
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "thickness": thickness,
        "is_load_bearing": False,
        "material": None,
    }
    if length_m is not None:
        payload["length_m"] = length_m
    if length_source is not None:
        payload["length_source"] = length_source
    response = requests.post(f"{base_url}/api/walls", json=payload, timeout=10)
    assert response.status_code == 200
    return response.json()


def prepare_validated_room_plan(base_url: str) -> tuple[dict, dict]:
    project = create_project(base_url)
    floor_plan = create_floor_plan(base_url, project["id"], scale_factor=10.0)
    wall = create_wall(base_url, floor_plan["id"], length_m=1.0, length_source="manual")

    room_response = requests.post(
        f"{base_url}/api/rooms",
        json={
            "floor_plan_id": floor_plan["id"],
            "name": "Room Z",
            "boundary_points": [[0, 0], [100, 0], [100, 100], [0, 100]],
        },
        timeout=10,
    )
    assert room_response.status_code == 200
    room = room_response.json()

    walls_commit = requests.post(
        f"{base_url}/api/floor-plans/{floor_plan['id']}/pipeline/walls/commit",
        json={
            "changes": {},
            "wall_lengths": [{"wall_id": wall["id"], "length_m": 1.0, "length_source": "manual"}],
        },
        timeout=10,
    )
    assert walls_commit.status_code == 200

    openings_commit = requests.post(
        f"{base_url}/api/floor-plans/{floor_plan['id']}/pipeline/openings/commit",
        json={"changes": {}},
        timeout=10,
    )
    assert openings_commit.status_code == 200

    rooms_commit = requests.post(
        f"{base_url}/api/floor-plans/{floor_plan['id']}/pipeline/rooms/commit",
        json={
            "changes": {},
            "room_updates": [{"room_id": room["id"], "name": "Room Z", "room_number": "1"}],
        },
        timeout=10,
    )
    assert rooms_commit.status_code == 200
    return floor_plan, room


def test_walls_commit_returns_missing_wall_ids(api_server: str):
    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"])
    wall = create_wall(api_server, floor_plan["id"])

    response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/walls/commit",
        json={"changes": {}, "wall_lengths": []},
        timeout=10,
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["detail"]["code"] == "walls_missing_dimensions"
    assert wall["id"] in payload["detail"]["missing_wall_ids"]


def test_walls_commit_recalculates_scale_and_room_metrics(api_server: str):
    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"], scale_factor=10.0)
    wall = create_wall(api_server, floor_plan["id"])

    room_response = requests.post(
        f"{api_server}/api/rooms",
        json={
            "floor_plan_id": floor_plan["id"],
            "name": "Room A",
            "boundary_points": [[0, 0], [100, 0], [100, 50], [0, 50]],
        },
        timeout=10,
    )
    assert room_response.status_code == 200

    commit_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/walls/commit",
        json={
            "changes": {},
            "wall_lengths": [
                {"wall_id": wall["id"], "length_m": 2.0, "length_source": "manual"},
            ],
        },
        timeout=10,
    )

    assert commit_response.status_code == 200
    payload = commit_response.json()
    updated_plan = payload["floor_plan"]
    assert math.isclose(updated_plan["scale_factor"], 20.0, rel_tol=1e-4)
    assert payload["pipeline_state"]["steps"]["walls"]["status"] == "validated"

    persisted_room = updated_plan["rooms"][0]
    assert math.isclose(persisted_room["length_m"], 2.0, rel_tol=1e-4)
    assert math.isclose(persisted_room["width_m"], 1.0, rel_tol=1e-4)
    assert math.isclose(persisted_room["area_sqm"], 2.0, rel_tol=1e-4)


def test_walls_commit_preserves_manual_scale_factor(api_server: str):
    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"], scale_factor=10.0)
    wall = create_wall(api_server, floor_plan["id"])

    manual_scale_response = requests.patch(
        f"{api_server}/api/floor-plans/{floor_plan['id']}",
        json={"scale_factor": 15.0},
        timeout=10,
    )
    assert manual_scale_response.status_code == 200
    assert math.isclose(manual_scale_response.json()["scale_factor"], 15.0, rel_tol=1e-4)

    commit_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/walls/commit",
        json={
            "changes": {},
            "wall_lengths": [
                {"wall_id": wall["id"], "length_m": 2.0, "length_source": "manual"},
            ],
        },
        timeout=10,
    )

    assert commit_response.status_code == 200
    payload = commit_response.json()
    assert math.isclose(payload["floor_plan"]["scale_factor"], 15.0, rel_tol=1e-4)


def test_revalidating_walls_marks_downstream_stale_without_data_loss(api_server: str):
    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"], scale_factor=10.0)
    wall = create_wall(api_server, floor_plan["id"], length_m=1.0, length_source="manual")

    door_response = requests.post(
        f"{api_server}/api/doors",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 35,
            "y": -5,
            "width": 30,
            "height": 10,
            "wall_id": wall["id"],
        },
        timeout=10,
    )
    assert door_response.status_code == 200

    room_response = requests.post(
        f"{api_server}/api/rooms",
        json={
            "floor_plan_id": floor_plan["id"],
            "name": "Room B",
            "boundary_points": [[0, 0], [100, 0], [100, 80], [0, 80]],
        },
        timeout=10,
    )
    assert room_response.status_code == 200
    room = room_response.json()

    walls_commit = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/walls/commit",
        json={
            "changes": {},
            "wall_lengths": [{"wall_id": wall["id"], "length_m": 1.0, "length_source": "manual"}],
        },
        timeout=10,
    )
    assert walls_commit.status_code == 200

    openings_commit = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/openings/commit",
        json={"changes": {}},
        timeout=10,
    )
    assert openings_commit.status_code == 200

    rooms_commit = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/rooms/commit",
        json={
            "changes": {},
            "room_updates": [{"room_id": room["id"], "name": "Room B", "room_number": "1"}],
        },
        timeout=10,
    )
    assert rooms_commit.status_code == 200
    assert rooms_commit.json()["pipeline_state"]["steps"]["rooms"]["status"] == "validated"
    assert rooms_commit.json()["floor_plan"]["rooms"][0]["room_number"] == "1"

    walls_recommit = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/walls/commit",
        json={
            "changes": {
                "update_walls": [{"id": wall["id"], "data": {"x2": 120}}],
            },
            "wall_lengths": [{"wall_id": wall["id"], "length_m": 1.2, "length_source": "manual"}],
        },
        timeout=10,
    )
    assert walls_recommit.status_code == 200
    state = walls_recommit.json()["pipeline_state"]["steps"]
    assert state["openings"]["status"] == "stale"
    assert state["rooms"]["status"] == "stale"

    updated_plan = walls_recommit.json()["floor_plan"]
    assert len(updated_plan["doors"]) == 1
    assert len(updated_plan["rooms"]) == 1


def test_pipeline_room_detection_keeps_perimeter_room_with_small_outer_gap(api_server: str, tmp_path: Path):
    image_path = tmp_path / "rooms-gap.png"
    Image.new("RGB", (260, 260), color="white").save(image_path)

    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"], scale_factor=10.0, image_path=image_path)

    manual_scale_response = requests.patch(
        f"{api_server}/api/floor-plans/{floor_plan['id']}",
        json={"scale_factor": 10.0},
        timeout=10,
    )
    assert manual_scale_response.status_code == 200

    wall_specs = [
        (30, 30, 116, 30),
        (144, 30, 230, 30),
        (30, 230, 230, 230),
        (30, 30, 30, 230),
        (230, 30, 230, 230),
        (30, 130, 230, 130),
        (130, 130, 130, 230),
    ]
    walls = [
        create_wall(
            api_server,
            floor_plan["id"],
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            thickness=200,
        )
        for x1, y1, x2, y2 in wall_specs
    ]

    walls_commit = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/walls/commit",
        json={
            "changes": {},
            "wall_lengths": [
                {
                    "wall_id": wall["id"],
                    "length_m": round(math.hypot(wall["x2"] - wall["x1"], wall["y2"] - wall["y1"]) * 10.0 / 1000.0, 3),
                    "length_source": "manual",
                }
                for wall in walls
            ],
        },
        timeout=10,
    )
    assert walls_commit.status_code == 200

    openings_commit = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/openings/commit",
        json={"changes": {}},
        timeout=10,
    )
    assert openings_commit.status_code == 200

    rooms_detect = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/rooms/detect",
        timeout=10,
    )

    assert rooms_detect.status_code == 200
    payload = rooms_detect.json()
    rooms = payload["floor_plan"]["rooms"]
    assert payload["pipeline_state"]["steps"]["rooms"]["status"] == "draft"
    assert len(rooms) == 3
    assert any(float(room["center_y"]) < 120 for room in rooms)


def test_pipeline_room_detection_keeps_perimeter_room_with_shifted_parallel_outer_seam(
    api_server: str,
    tmp_path: Path,
):
    image_path = tmp_path / "rooms-shifted-seam.png"
    Image.new("RGB", (360, 360), color="white").save(image_path)

    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"], scale_factor=10.0, image_path=image_path)

    manual_scale_response = requests.patch(
        f"{api_server}/api/floor-plans/{floor_plan['id']}",
        json={"scale_factor": 10.0},
        timeout=10,
    )
    assert manual_scale_response.status_code == 200

    wall_specs = [
        (40, 40, 280, 40),
        (40, 40, 40, 280),
        (40, 150, 280, 150),
        (40, 280, 180, 280),
        (180, 150, 180, 280),
        (280, 40, 280, 90),
        (270, 102, 270, 150),
    ]
    walls = [
        create_wall(
            api_server,
            floor_plan["id"],
            x1=x1,
            y1=y1,
            x2=x2,
            y2=y2,
            thickness=80,
        )
        for x1, y1, x2, y2 in wall_specs
    ]

    walls_commit = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/walls/commit",
        json={
            "changes": {},
            "wall_lengths": [
                {
                    "wall_id": wall["id"],
                    "length_m": round(math.hypot(wall["x2"] - wall["x1"], wall["y2"] - wall["y1"]) * 10.0 / 1000.0, 3),
                    "length_source": "manual",
                }
                for wall in walls
            ],
        },
        timeout=10,
    )
    assert walls_commit.status_code == 200

    openings_commit = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/openings/commit",
        json={"changes": {}},
        timeout=10,
    )
    assert openings_commit.status_code == 200

    rooms_detect = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/rooms/detect",
        timeout=10,
    )

    assert rooms_detect.status_code == 200
    payload = rooms_detect.json()
    rooms = payload["floor_plan"]["rooms"]
    assert payload["pipeline_state"]["steps"]["rooms"]["status"] == "draft"
    assert len(rooms) == 2
    assert any(float(room["center_y"]) < 140 for room in rooms)


def test_walls_commit_relinks_openings_when_wall_ids_change(api_server: str):
    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"], scale_factor=10.0)
    wall = create_wall(api_server, floor_plan["id"], length_m=1.0, length_source="manual")

    door_response = requests.post(
        f"{api_server}/api/doors",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 20,
            "y": -5,
            "width": 30,
            "height": 10,
            "wall_id": wall["id"],
        },
        timeout=10,
    )
    assert door_response.status_code == 200
    door = door_response.json()

    walls_commit = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/walls/commit",
        json={
            "changes": {
                "deleted": [{"element_type": "walls", "id": wall["id"]}],
                "create_walls": [
                    {
                        "floor_plan_id": floor_plan["id"],
                        "x1": 0,
                        "y1": 20,
                        "x2": 100,
                        "y2": 20,
                        "thickness": 200,
                        "is_load_bearing": False,
                        "material": None,
                        "length_m": 1.0,
                        "length_source": "manual",
                    }
                ],
            },
            "wall_lengths": [],
        },
        timeout=10,
    )

    assert walls_commit.status_code == 200
    updated_plan = walls_commit.json()["floor_plan"]
    assert len(updated_plan["walls"]) == 1
    assert len(updated_plan["doors"]) == 1
    updated_door = updated_plan["doors"][0]
    assert updated_door["id"] == door["id"]
    assert updated_door["wall_id"] == updated_plan["walls"][0]["id"]
    assert updated_door["y"] > 0


def test_walls_commit_prunes_openings_that_are_outside_new_walls(api_server: str):
    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"], scale_factor=10.0)
    wall = create_wall(api_server, floor_plan["id"], length_m=1.0, length_source="manual")

    door_response = requests.post(
        f"{api_server}/api/doors",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 20,
            "y": -5,
            "width": 30,
            "height": 10,
            "wall_id": wall["id"],
        },
        timeout=10,
    )
    assert door_response.status_code == 200

    walls_commit = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/walls/commit",
        json={
            "changes": {
                "deleted": [{"element_type": "walls", "id": wall["id"]}],
                "create_walls": [
                    {
                        "floor_plan_id": floor_plan["id"],
                        "x1": 0,
                        "y1": 200,
                        "x2": 100,
                        "y2": 200,
                        "thickness": 200,
                        "is_load_bearing": False,
                        "material": None,
                        "length_m": 1.0,
                        "length_source": "manual",
                    }
                ],
            },
            "wall_lengths": [],
        },
        timeout=10,
    )

    assert walls_commit.status_code == 200
    updated_plan = walls_commit.json()["floor_plan"]
    assert len(updated_plan["walls"]) == 1
    assert updated_plan["doors"] == []


def test_openings_commit_rejects_opening_outside_wall(api_server: str):
    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"])
    wall = create_wall(api_server, floor_plan["id"], length_m=1.0, length_source="manual")

    walls_commit = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/walls/commit",
        json={
            "changes": {},
            "wall_lengths": [{"wall_id": wall["id"], "length_m": 1.0, "length_source": "manual"}],
        },
        timeout=10,
    )
    assert walls_commit.status_code == 200

    door_response = requests.post(
        f"{api_server}/api/doors",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 20,
            "y": -5,
            "width": 30,
            "height": 10,
            "wall_id": wall["id"],
        },
        timeout=10,
    )
    assert door_response.status_code == 200
    door = door_response.json()

    invalid_commit = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/openings/commit",
        json={
            "changes": {
                "update_doors": [
                    {
                        "id": door["id"],
                        "data": {"x": 300, "y": 300, "wall_id": wall["id"]},
                    }
                ]
            }
        },
        timeout=10,
    )
    assert invalid_commit.status_code == 422
    assert invalid_commit.json()["code"] == "opening_outside_wall"


def test_openings_commit_prioritizes_deleted_openings_over_local_updates(api_server: str):
    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"])
    wall = create_wall(api_server, floor_plan["id"], length_m=1.0, length_source="manual")

    walls_commit = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/walls/commit",
        json={
            "changes": {},
            "wall_lengths": [{"wall_id": wall["id"], "length_m": 1.0, "length_source": "manual"}],
        },
        timeout=10,
    )
    assert walls_commit.status_code == 200

    door_response = requests.post(
        f"{api_server}/api/doors",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 20,
            "y": -5,
            "width": 30,
            "height": 10,
            "wall_id": wall["id"],
        },
        timeout=10,
    )
    assert door_response.status_code == 200
    door = door_response.json()

    commit_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/openings/commit",
        json={
            "changes": {
                "deleted": [{"element_type": "doors", "id": door["id"]}],
                "update_doors": [
                    {
                        "id": door["id"],
                        "data": {"x": 30, "y": -5, "wall_id": wall["id"]},
                    }
                ],
            }
        },
        timeout=10,
    )
    assert commit_response.status_code == 200
    assert commit_response.json()["floor_plan"]["doors"] == []


def test_rooms_commit_applies_length_width_area_formula(api_server: str):
    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"])
    wall = create_wall(api_server, floor_plan["id"], length_m=1.0, length_source="manual")

    room_response = requests.post(
        f"{api_server}/api/rooms",
        json={
            "floor_plan_id": floor_plan["id"],
            "name": "Room C",
            "boundary_points": [[0, 0], [100, 0], [100, 100], [0, 100]],
        },
        timeout=10,
    )
    assert room_response.status_code == 200
    room = room_response.json()

    walls_commit = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/walls/commit",
        json={
            "changes": {},
            "wall_lengths": [{"wall_id": wall["id"], "length_m": 1.0, "length_source": "manual"}],
        },
        timeout=10,
    )
    assert walls_commit.status_code == 200

    openings_commit = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/openings/commit",
        json={"changes": {}},
        timeout=10,
    )
    assert openings_commit.status_code == 200

    rooms_commit = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/rooms/commit",
        json={
            "changes": {},
            "room_updates": [
                {
                    "room_id": room["id"],
                    "name": "Conference",
                    "length_m": 4.0,
                    "width_m": 3.0,
                }
            ],
        },
        timeout=10,
    )
    assert rooms_commit.status_code == 200

    updated_room = rooms_commit.json()["floor_plan"]["rooms"][0]
    assert updated_room["name"] == "Conference"
    assert math.isclose(updated_room["length_m"], 1.0, rel_tol=1e-4)
    assert math.isclose(updated_room["width_m"], 1.0, rel_tol=1e-4)
    assert math.isclose(updated_room["area_sqm"], 1.0, rel_tol=1e-4)
    assert math.isclose(updated_room["perimeter_m"], 4.0, rel_tol=1e-4)


def test_fire_alarm_batch_save_does_not_modify_walls_or_openings(api_server: str):
    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"], scale_factor=10.0)
    wall = create_wall(api_server, floor_plan["id"], length_m=1.0, length_source="manual")

    door_response = requests.post(
        f"{api_server}/api/doors",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 20,
            "y": -5,
            "width": 30,
            "height": 10,
            "wall_id": wall["id"],
        },
        timeout=10,
    )
    assert door_response.status_code == 200
    door = door_response.json()

    save_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/batch-save",
        json={
            "create_fire_alarms": [
                {
                    "floor_plan_id": floor_plan["id"],
                    "x": 15,
                    "y": 25,
                    "device_type": "smoke_detector",
                    "coverage_radius": 4500,
                }
            ]
        },
        timeout=10,
    )

    assert save_response.status_code == 200
    updated_plan = save_response.json()["floor_plan"]
    assert len(updated_plan["walls"]) == 1
    assert len(updated_plan["doors"]) == 1
    assert updated_plan["doors"][0]["id"] == door["id"]
    assert len(updated_plan["fire_alarms"]) == 1


def test_zkspc_detect_and_commit_unlock_branch_steps(api_server: str):
    floor_plan, room = prepare_validated_room_plan(api_server)

    detect_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/zkspc/detect",
        timeout=10,
    )

    assert detect_response.status_code == 200
    detected_payload = detect_response.json()
    assert detected_payload["pipeline_state"]["steps"]["zkspc"]["status"] == "draft"
    assert detected_payload["pipeline_state"]["branches"]["non_addressable"]["steps"]["fire_alarms"]["status"] == "locked"
    assert len(detected_payload["floor_plan"]["zkspc_zones"]) == 1

    commit_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/zkspc/commit",
        json={
            "zones": [
                {
                    "zone_number": 1,
                    "name": "Zone 1",
                    "room_ids": [room["id"]],
                    "is_manual": True,
                    "is_locked": False,
                }
            ]
        },
        timeout=10,
    )

    assert commit_response.status_code == 200
    committed_payload = commit_response.json()
    assert committed_payload["pipeline_state"]["steps"]["zkspc"]["status"] == "validated"
    assert committed_payload["pipeline_state"]["branches"]["non_addressable"]["steps"]["fire_alarms"]["status"] == "draft"
    assert committed_payload["pipeline_state"]["branches"]["addressable"]["steps"]["devices_cables"]["status"] == "draft"


def test_branch_specific_fire_alarm_saves_do_not_overwrite_other_system(api_server: str):
    floor_plan, room = prepare_validated_room_plan(api_server)

    detect_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/zkspc/detect",
        timeout=10,
    )
    assert detect_response.status_code == 200
    zkspc_zone_id = detect_response.json()["floor_plan"]["zkspc_zones"][0]["id"]

    commit_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/zkspc/commit",
        json={
            "zones": [
                {
                    "id": zkspc_zone_id,
                    "zone_number": 1,
                    "name": "Zone 1",
                    "room_ids": [room["id"]],
                    "is_manual": True,
                    "is_locked": False,
                }
            ]
        },
        timeout=10,
    )
    assert commit_response.status_code == 200

    save_non_addressable = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/batch-save",
        json={
            "create_fire_alarms": [
                {
                    "floor_plan_id": floor_plan["id"],
                    "x": 20,
                    "y": 20,
                    "device_type": "smoke_detector",
                    "coverage_radius": 4500,
                    "system_type": "non_addressable",
                    "zkspc_zone_id": zkspc_zone_id,
                }
            ]
        },
        timeout=10,
    )
    assert save_non_addressable.status_code == 200

    save_addressable = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/batch-save",
        json={
            "create_fire_alarms": [
                {
                    "floor_plan_id": floor_plan["id"],
                    "x": 60,
                    "y": 60,
                    "device_type": "smoke_detector",
                    "coverage_radius": 4500,
                    "system_type": "addressable",
                    "zkspc_zone_id": zkspc_zone_id,
                }
            ]
        },
        timeout=10,
    )
    assert save_addressable.status_code == 200

    floor_plan_response = requests.get(
        f"{api_server}/api/floor-plans/{floor_plan['id']}?include_elements=true",
        timeout=10,
    )
    assert floor_plan_response.status_code == 200
    systems = sorted(alarm["system_type"] for alarm in floor_plan_response.json()["fire_alarms"])
    assert systems == ["addressable", "non_addressable"]

    pipeline_state = requests.get(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline-state",
        timeout=10,
    )
    assert pipeline_state.status_code == 200
    pipeline_payload = pipeline_state.json()
    assert pipeline_payload["branches"]["non_addressable"]["steps"]["fire_alarms"]["status"] == "validated"
    assert pipeline_payload["branches"]["addressable"]["steps"]["fire_alarms"]["status"] == "validated"


def test_signal_instrument_creation_and_cable_routes_work_per_branch(api_server: str):
    floor_plan, room = prepare_validated_room_plan(api_server)

    detect_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/zkspc/detect",
        timeout=10,
    )
    assert detect_response.status_code == 200
    zkspc_zone_id = detect_response.json()["floor_plan"]["zkspc_zones"][0]["id"]

    commit_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/zkspc/commit",
        json={
            "zones": [
                {
                    "id": zkspc_zone_id,
                    "zone_number": 1,
                    "name": "Zone 1",
                    "room_ids": [room["id"]],
                    "is_manual": True,
                    "is_locked": False,
                }
            ]
        },
        timeout=10,
    )
    assert commit_response.status_code == 200

    alarms_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/batch-save",
        json={
            "create_fire_alarms": [
                {
                    "floor_plan_id": floor_plan["id"],
                    "x": 15,
                    "y": 25,
                    "device_type": "smoke_detector",
                    "coverage_radius": 4500,
                    "system_type": "non_addressable",
                    "zkspc_zone_id": zkspc_zone_id,
                    "loop_number": 1,
                    "device_number": 1,
                },
                {
                    "floor_plan_id": floor_plan["id"],
                    "x": 75,
                    "y": 25,
                    "device_type": "smoke_detector",
                    "coverage_radius": 4500,
                    "system_type": "non_addressable",
                    "zkspc_zone_id": zkspc_zone_id,
                    "loop_number": 1,
                    "device_number": 2,
                },
            ]
        },
        timeout=10,
    )
    assert alarms_response.status_code == 200

    instrument_response = requests.post(
        f"{api_server}/api/signal-instruments",
        json={
            "floor_plan_id": floor_plan["id"],
            "system_type": "non_addressable",
            "instrument_type": "control_panel",
            "x": 10,
            "y": 10,
        },
        timeout=10,
    )
    assert instrument_response.status_code == 200
    instrument = instrument_response.json()

    recalc_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/cable-routes/recalculate",
        json={"system_type": "non_addressable", "use_shared_trunk": True},
        timeout=10,
    )
    assert recalc_response.status_code == 200
    routes = recalc_response.json()
    assert routes
    assert all(route["system_type"] == "non_addressable" for route in routes)
    assert all(route["length_m"] > 0 for route in routes)

    updated_route = requests.patch(
        f"{api_server}/api/cable-routes/{routes[0]['id']}",
        json={
            "polyline_points": routes[0]["polyline_points"][:1] + [[50, 10]] + routes[0]["polyline_points"][1:],
            "is_manual": True,
        },
        timeout=10,
    )
    assert updated_route.status_code == 200
    assert updated_route.json()["is_manual"] is True
    assert len(updated_route.json()["polyline_points"]) == len(routes[0]["polyline_points"]) + 1

    pipeline_state = requests.get(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline-state",
        timeout=10,
    )
    assert pipeline_state.status_code == 200
    assert pipeline_state.json()["branches"]["non_addressable"]["steps"]["devices_cables"]["status"] == "validated"
