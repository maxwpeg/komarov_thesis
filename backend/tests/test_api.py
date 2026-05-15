"""API integration tests against a temporary local server."""

from __future__ import annotations

from pathlib import Path

import requests
from PIL import Image


def create_project(base_url: str) -> dict:
    response = requests.post(
        f"{base_url}/api/projects",
        json={
            "name": "Test Project",
            "project_type": "PS",
            "contractor": "Test Contractor",
            "engineer": "Test Engineer",
            "cpe": "Test CPE",
            "checker": "Test Checker",
            "facility": "Test Facility",
            "facility_address": "Test Address",
            "project_description": "Test Description",
            "stage": "R",
            "number_of_floors": 1,
        },
        timeout=10,
    )
    assert response.status_code == 200
    return response.json()


def test_health_endpoints_and_request_id(api_server: str):
    root_response = requests.get(f"{api_server}/", timeout=10)
    assert root_response.status_code == 200
    assert root_response.json()["status"] == "ok"
    assert root_response.headers["X-Request-ID"]

    live_response = requests.get(f"{api_server}/health/live", timeout=10)
    assert live_response.status_code == 200
    assert live_response.json()["status"] == "ok"
    assert live_response.headers["X-Request-ID"]

    ready_response = requests.get(f"{api_server}/health/ready", timeout=10)
    assert ready_response.status_code == 200
    payload = ready_response.json()
    assert payload["status"] in {"ok", "degraded"}
    assert payload["checks"]["database"]["status"] == "ok"
    assert payload["checks"]["storage"]["status"] == "ok"


def create_floor_plan(
    base_url: str,
    project_id: int,
    image_path: Path | None = None,
    scale_factor: float = 10.0,
    ceiling_height_mm: float = 3000.0,
) -> dict:
    data = {
        "project_id": str(project_id),
        "floor_number": "1",
        "name": "Floor 1",
        "scale_factor": str(scale_factor),
        "ceiling_height_mm": str(ceiling_height_mm),
    }
    if image_path is None:
        response = requests.post(f"{base_url}/api/floor-plans", data=data, timeout=10)
    else:
        with image_path.open("rb") as file:
            response = requests.post(
                f"{base_url}/api/floor-plans",
                data=data,
                files={"file": ("floor.png", file, "image/png")},
                timeout=10,
            )
    assert response.status_code == 200
    return response.json()


def test_project_and_floor_plan_crud(api_server: str, tmp_path: Path):
    image_path = tmp_path / "floor.png"
    Image.new("RGB", (240, 240), color="white").save(image_path)

    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"], image_path=image_path)

    get_response = requests.get(f"{api_server}/api/projects/{project['id']}", timeout=10)
    assert get_response.status_code == 200
    assert get_response.json()["code"].startswith("РП-ЗК-")

    list_response = requests.get(
        f"{api_server}/api/projects/{project['id']}/floor-plans",
        timeout=10,
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    delete_response = requests.delete(f"{api_server}/api/floor-plans/{floor_plan['id']}", timeout=10)
    assert delete_response.status_code == 200


def test_project_filters_and_empty_pdf_versions(api_server: str):
    alpha = requests.post(
        f"{api_server}/api/projects",
        json={
            "name": "Alpha Project",
            "project_type": "PS",
            "contractor": "Test Contractor",
            "engineer": "Test Engineer",
            "cpe": "Test CPE",
            "checker": "Test Checker",
            "facility": "Alpha Facility",
            "facility_address": "Test Address",
            "project_description": "Test Description",
            "stage": "R",
            "number_of_floors": 1,
        },
        timeout=10,
    )
    assert alpha.status_code == 200
    beta = requests.post(
        f"{api_server}/api/projects",
        json={
            "name": "Beta Project",
            "project_type": "PS",
            "contractor": "Test Contractor",
            "engineer": "Test Engineer",
            "cpe": "Test CPE",
            "checker": "Test Checker",
            "facility": "Beta Facility",
            "facility_address": "Test Address",
            "project_description": "Test Description",
            "stage": "R",
            "number_of_floors": 1,
        },
        timeout=10,
    )
    assert beta.status_code == 200

    filtered = requests.get(f"{api_server}/api/projects", params={"facility": "Alpha"}, timeout=10)
    assert filtered.status_code == 200
    facilities = {item["facility"] for item in filtered.json()}
    assert "Alpha Facility" in facilities
    assert "Beta Facility" not in facilities

    versions = requests.get(f"{api_server}/api/projects/{alpha.json()['id']}/pdf-versions", timeout=10)
    assert versions.status_code == 200
    assert versions.json() == []


def test_audit_log_filters_and_exports(api_server: str):
    list_response = requests.get(
        f"{api_server}/api/audit",
        params={"event_name": "auth_login_succeeded", "limit": 10},
        timeout=10,
    )
    assert list_response.status_code == 200
    events = list_response.json()
    assert events
    assert all(event["event_name"] == "auth_login_succeeded" for event in events)
    assert any(event["user_id"] is not None for event in events)

    json_export = requests.get(
        f"{api_server}/api/audit/export",
        params={"format": "json", "event_name": "auth_login_succeeded"},
        timeout=10,
    )
    assert json_export.status_code == 200
    assert "audit-log.json" in json_export.headers["Content-Disposition"]
    assert isinstance(json_export.json(), list)

    csv_export = requests.get(
        f"{api_server}/api/audit/export",
        params={"format": "csv", "event_name": "auth_login_succeeded"},
        timeout=10,
    )
    assert csv_export.status_code == 200
    assert "audit-log.csv" in csv_export.headers["Content-Disposition"]
    assert "event_name" in csv_export.text
    assert "auth_login_succeeded" in csv_export.text


def test_project_update_recalculates_code_when_year_changes(api_server: str):
    create_response = requests.post(
        f"{api_server}/api/projects",
        json={
            "name": "Editable Project",
            "project_type": "PS",
            "year": 2024,
            "contractor": "Original Contractor",
            "engineer": "Original Engineer",
            "cpe": "Test CPE",
            "checker": "Test Checker",
            "facility": "Editable Facility",
            "facility_address": "Original Address",
            "project_description": "Original Description",
            "stage": "R",
            "number_of_floors": 1,
        },
        timeout=10,
    )
    assert create_response.status_code == 200
    project = create_response.json()
    assert project["year"] == 2024
    assert project["number"] == 1
    assert project["code"].startswith("РП-ЗК-")
    assert project["code"].endswith("-PS")

    update_response = requests.patch(
        f"{api_server}/api/projects/{project['id']}",
        json={
            "project_type": "APS",
            "year": 2025,
            "contractor": "Updated Contractor",
            "engineer": "Updated Engineer",
            "facility_address": "Updated Address",
            "project_description": "Updated Description",
        },
        timeout=10,
    )
    assert update_response.status_code == 200
    updated = update_response.json()

    assert updated["year"] == 2025
    assert updated["number"] == 1
    assert updated["project_type"] == "APS"
    assert updated["contractor"] == "Updated Contractor"
    assert updated["engineer"] == "Updated Engineer"
    assert updated["facility_address"] == "Updated Address"
    assert updated["project_description"] == "Updated Description"
    assert updated["code"].endswith("-APS")
    assert "/25-" in updated["code"]


def test_project_case_fields_round_trip(api_server: str):
    create_response = requests.post(
        f"{api_server}/api/projects",
        json={
            "name": "Case Project",
            "project_type": "PS",
            "year": 2026,
            "contractor": "Contractor",
            "engineer": "Engineer",
            "cpe": "CPE",
            "checker": "Checker",
            "facility": "Административное здание",
            "facility_genitive": "Административного здания",
            "facility_instrumental": "Административным зданием",
            "facility_address": "Address",
            "project_description": "Description",
            "stage": "R",
            "number_of_floors": 1,
        },
        timeout=10,
    )
    assert create_response.status_code == 200
    project = create_response.json()
    assert project["facility_genitive"] == "Административного здания"
    assert project["facility_instrumental"] == "Административным зданием"

    get_response = requests.get(f"{api_server}/api/projects/{project['id']}", timeout=10)
    assert get_response.status_code == 200
    fetched = get_response.json()
    assert fetched["facility_genitive"] == "Административного здания"
    assert fetched["facility_instrumental"] == "Административным зданием"

    update_response = requests.patch(
        f"{api_server}/api/projects/{project['id']}",
        json={
            "facility_genitive": "Нового административного здания",
            "facility_instrumental": "Новым административным зданием",
        },
        timeout=10,
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["facility_genitive"] == "Нового административного здания"
    assert updated["facility_instrumental"] == "Новым административным зданием"


def test_project_numbers_are_counted_separately_per_year_and_reuse_smallest_free_on_year_change(api_server: str):
    payload = {
        "name": "Project",
        "project_type": "ПС",
        "contractor": "Contractor",
        "engineer": "Engineer",
        "cpe": "CPE",
        "checker": "Checker",
        "facility": "Facility",
        "facility_address": "Address",
        "project_description": "Description",
        "stage": "Р",
        "number_of_floors": 1,
    }

    project_2024_a = requests.post(
        f"{api_server}/api/projects",
        json={**payload, "name": "2024-A", "facility": "2024-A", "year": 2024},
        timeout=10,
    ).json()
    project_2024_b = requests.post(
        f"{api_server}/api/projects",
        json={**payload, "name": "2024-B", "facility": "2024-B", "year": 2024},
        timeout=10,
    ).json()
    project_2025_a = requests.post(
        f"{api_server}/api/projects",
        json={**payload, "name": "2025-A", "facility": "2025-A", "year": 2025},
        timeout=10,
    ).json()
    project_2025_b = requests.post(
        f"{api_server}/api/projects",
        json={**payload, "name": "2025-B", "facility": "2025-B", "year": 2025},
        timeout=10,
    ).json()

    assert project_2024_a["number"] == 1
    assert project_2024_b["number"] == 2
    assert project_2025_a["number"] == 1
    assert project_2025_b["number"] == 2

    delete_response = requests.delete(f"{api_server}/api/projects/{project_2025_a['id']}", timeout=10)
    assert delete_response.status_code == 200
    assert delete_response.json()["message"] == "Project moved to trash"

    hidden_response = requests.get(f"{api_server}/api/projects/{project_2025_a['id']}", timeout=10)
    assert hidden_response.status_code == 404

    trash_response = requests.get(f"{api_server}/api/projects/trash", timeout=10)
    assert trash_response.status_code == 200
    assert project_2025_a["id"] in [item["id"] for item in trash_response.json()]

    permanent_delete_response = requests.delete(
        f"{api_server}/api/projects/{project_2025_a['id']}/permanent",
        timeout=10,
    )
    assert permanent_delete_response.status_code == 200

    move_response = requests.patch(
        f"{api_server}/api/projects/{project_2024_b['id']}",
        json={"year": 2025},
        timeout=10,
    )
    assert move_response.status_code == 200
    moved = move_response.json()

    assert moved["year"] == 2025
    assert moved["number"] == 1
    assert moved["code"].startswith("РП-ЗК-1/25-")


def test_element_patch_routes_and_batch_save(api_server: str):
    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"])

    wall = requests.post(
        f"{api_server}/api/walls",
        json={
            "floor_plan_id": floor_plan["id"],
            "x1": 0,
            "y1": 0,
            "x2": 100,
            "y2": 0,
            "thickness": 200,
            "is_load_bearing": False,
            "length_m": 1.0,
            "length_source": "manual",
        },
        timeout=10,
    ).json()

    door = requests.post(
        f"{api_server}/api/doors",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 10,
            "y": -5,
            "width": 30,
            "height": 10,
            "wall_id": wall["id"],
        },
        timeout=10,
    ).json()
    window = requests.post(
        f"{api_server}/api/windows",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 15,
            "y": -5,
            "width": 35,
            "height": 10,
            "wall_id": wall["id"],
        },
        timeout=10,
    ).json()
    fire_alarm = requests.post(
        f"{api_server}/api/fire-alarms",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 5,
            "y": 6,
            "device_type": "smoke_detector",
        },
        timeout=10,
    ).json()

    assert requests.patch(
        f"{api_server}/api/doors/{door['id']}",
        json={"x": 25, "y": -5},
        timeout=10,
    ).status_code == 200
    assert requests.patch(
        f"{api_server}/api/windows/{window['id']}",
        json={"x": 30, "y": -5},
        timeout=10,
    ).status_code == 200
    assert requests.patch(
        f"{api_server}/api/fire-alarms/{fire_alarm['id']}",
        json={"x": 7, "y": 8},
        timeout=10,
    ).status_code == 200

    batch_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/batch-save",
        json={
            "deleted": [{"element_type": "doors", "id": door["id"]}],
            "create_walls": [
                {
                    "floor_plan_id": floor_plan["id"],
                    "x1": 0,
                    "y1": 0,
                    "x2": 10,
                    "y2": 10,
                    "thickness": 200,
                    "is_load_bearing": False,
                    "material": None,
                }
            ],
            "update_windows": [{"id": window["id"], "data": {"x": 35, "y": -5}}],
            "update_fire_alarms": [{"id": fire_alarm["id"], "data": {"y": 9}}],
        },
        timeout=10,
    )
    assert batch_response.status_code == 200
    payload = batch_response.json()
    assert payload["message"] == "Changes saved successfully"
    assert len(payload["floor_plan"]["walls"]) == 2
    assert len(payload["floor_plan"]["doors"]) == 0


def test_floor_plan_patch_updates_scale_factor_and_ceiling_height(api_server: str):
    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"], scale_factor=10.0, ceiling_height_mm=2800.0)

    response = requests.patch(
        f"{api_server}/api/floor-plans/{floor_plan['id']}",
        json={"scale_factor": 25.5, "ceiling_height_mm": 3400.0},
        timeout=10,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["scale_factor"] == 25.5
    assert payload["ceiling_height_mm"] == 3400.0


def test_fire_alarm_auto_layout_preview_and_batch_create(api_server: str):
    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"], scale_factor=100.0, ceiling_height_mm=2700.0)

    requests.post(
        f"{api_server}/api/rooms",
        json={
            "floor_plan_id": floor_plan["id"],
            "name": "Hall",
            "room_type": "general",
            "boundary_points": [[0, 0], [100, 0], [100, 100], [0, 100]],
        },
        timeout=10,
    ).raise_for_status()
    wall = requests.post(
        f"{api_server}/api/walls",
        json={
            "floor_plan_id": floor_plan["id"],
            "x1": 0,
            "y1": 0,
            "x2": 100,
            "y2": 0,
            "thickness": 200,
            "is_load_bearing": False,
            "length_m": 10.0,
            "length_source": "manual",
        },
        timeout=10,
    )
    wall.raise_for_status()
    wall_payload = wall.json()
    requests.post(
        f"{api_server}/api/doors",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 40,
            "y": -5,
            "width": 20,
            "height": 10,
            "wall_id": wall_payload["id"],
            "rotation_deg": 0,
        },
        timeout=10,
    ).raise_for_status()

    preview_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/fire-alarms/auto-layout",
        timeout=10,
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["summary"]["smoke_detectors"] >= 2
    assert preview["summary"]["manual_call_points"] >= 1
    assert any(device["room_id"] is not None for device in preview["devices"])

    save_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/batch-save",
        json={
            "create_fire_alarms": [
                {
                    "floor_plan_id": floor_plan["id"],
                    "x": 20,
                    "y": 30,
                    "device_type": "smoke_detector",
                    "coverage_radius": 4500,
                }
            ]
        },
        timeout=10,
    )
    assert save_response.status_code == 200
    fire_alarm = save_response.json()["floor_plan"]["fire_alarms"][0]
    assert fire_alarm["room_id"] is not None
    assert fire_alarm["offset_left_m"] == 2.0
    assert fire_alarm["offset_top_m"] == 3.0


def test_doors_auto_fill_evacuation_exit_and_keep_manual_override(api_server: str):
    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"], scale_factor=100.0)

    requests.post(
        f"{api_server}/api/rooms",
        json={
            "floor_plan_id": floor_plan["id"],
            "name": "Hall",
            "room_type": "general",
            "boundary_points": [[0, 0], [100, 0], [100, 100], [0, 100]],
            "max_occupancy": 60,
        },
        timeout=10,
    ).raise_for_status()
    wall = requests.post(
        f"{api_server}/api/walls",
        json={
            "floor_plan_id": floor_plan["id"],
            "x1": 0,
            "y1": 0,
            "x2": 100,
            "y2": 0,
            "thickness": 200,
            "is_load_bearing": False,
            "length_m": 10.0,
            "length_source": "manual",
        },
        timeout=10,
    ).json()

    auto_response = requests.post(
        f"{api_server}/api/doors",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 20,
            "y": -5,
            "width": 20,
            "height": 10,
            "wall_id": wall["id"],
            "rotation_deg": 0,
        },
        timeout=10,
    )
    assert auto_response.status_code == 200
    auto_door = auto_response.json()
    assert auto_door["is_evacuation_exit"] is True

    manual_response = requests.post(
        f"{api_server}/api/doors",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 50,
            "y": -5,
            "width": 20,
            "height": 10,
            "wall_id": wall["id"],
            "rotation_deg": 0,
            "is_evacuation_exit": False,
        },
        timeout=10,
    )
    assert manual_response.status_code == 200
    manual_door = manual_response.json()
    assert manual_door["is_evacuation_exit"] is False

    batch_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/batch-save",
        json={
            "create_doors": [
                {
                    "floor_plan_id": floor_plan["id"],
                    "x": 80,
                    "y": -5,
                    "width": 20,
                    "height": 10,
                    "wall_id": wall["id"],
                    "rotation_deg": 0,
                }
            ]
        },
        timeout=10,
    )
    assert batch_response.status_code == 200
    created_doors = batch_response.json()["floor_plan"]["doors"]
    assert any(door["id"] != manual_door["id"] and door["id"] != auto_door["id"] and door["is_evacuation_exit"] is True for door in created_doors)


def test_soue_auto_layout_preview_returns_draft_devices(api_server: str):
    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"], scale_factor=100.0, ceiling_height_mm=2700.0)

    requests.post(
        f"{api_server}/api/rooms",
        json={
            "floor_plan_id": floor_plan["id"],
            "name": "Hall",
            "room_type": "general",
            "boundary_points": [[0, 0], [120, 0], [120, 120], [0, 120]],
            "max_occupancy": 60,
        },
        timeout=10,
    ).raise_for_status()
    wall = requests.post(
        f"{api_server}/api/walls",
        json={
            "floor_plan_id": floor_plan["id"],
            "x1": 0,
            "y1": 0,
            "x2": 120,
            "y2": 0,
            "thickness": 200,
            "is_load_bearing": False,
            "length_m": 12.0,
            "length_source": "manual",
        },
        timeout=10,
    ).json()
    requests.post(
        f"{api_server}/api/doors",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 45,
            "y": -5,
            "width": 30,
            "height": 10,
            "wall_id": wall["id"],
            "rotation_deg": 0,
        },
        timeout=10,
    ).raise_for_status()

    preview_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/soue-devices/auto-layout?system_type=non_addressable",
        timeout=10,
    )
    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["devices"]
    assert all("id" not in device for device in preview["devices"])
    assert all("floor_plan_id" not in device for device in preview["devices"])
    assert any(device["device_type"] == "exit_sign" for device in preview["devices"])


def test_stair_crud_and_batch_update(api_server: str):
    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"])

    create_response = requests.post(
        f"{api_server}/api/stairs",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 50,
            "y": 60,
            "width": 120,
            "height": 40,
            "rotation_deg": 0,
            "step_count": 6,
            "step_axis": "horizontal",
        },
        timeout=10,
    )
    assert create_response.status_code == 200
    stair = create_response.json()
    assert stair["step_count"] == 6
    assert stair["step_axis"] == "horizontal"

    update_response = requests.patch(
        f"{api_server}/api/stairs/{stair['id']}",
        json={"width": 90, "height": 150},
        timeout=10,
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["width"] == 90
    assert updated["height"] == 150
    assert updated["step_axis"] == "vertical"

    batch_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/batch-save",
        json={
            "update_stairs": [
                {
                    "id": stair["id"],
                    "data": {
                        "x": 80,
                        "y": 95,
                        "step_count": 7,
                    },
                }
            ]
        },
        timeout=10,
    )
    assert batch_response.status_code == 200
    payload = batch_response.json()["floor_plan"]
    saved_stair = next(item for item in payload["stairs"] if item["id"] == stair["id"])
    assert saved_stair["x"] == 80
    assert saved_stair["y"] == 95
    assert saved_stair["step_count"] == 7


def test_openings_snap_to_wall_and_stay_inside_bounds(api_server: str):
    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"], scale_factor=10.0)

    wall = requests.post(
        f"{api_server}/api/walls",
        json={
            "floor_plan_id": floor_plan["id"],
            "x1": 0,
            "y1": 0,
            "x2": 100,
            "y2": 0,
            "thickness": 200,
            "is_load_bearing": False,
            "length_m": 1.0,
            "length_source": "manual",
        },
        timeout=10,
    ).json()

    create_response = requests.post(
        f"{api_server}/api/doors",
        json={
            "floor_plan_id": floor_plan["id"],
            "x": 85,
            "y": 25,
            "width": 40,
            "height": 10,
        },
        timeout=10,
    )
    assert create_response.status_code == 200
    door = create_response.json()
    assert door["wall_id"] == wall["id"]
    assert door["rotation_deg"] == 0
    assert door["height"] == 20
    assert door["x"] == 60
    assert door["y"] == -10

    update_wall = requests.patch(
        f"{api_server}/api/walls/{wall['id']}",
        json={"thickness": 300},
        timeout=10,
    )
    assert update_wall.status_code == 200

    updated_plan = requests.get(
        f"{api_server}/api/floor-plans/{floor_plan['id']}?include_elements=true",
        timeout=10,
    ).json()
    updated_door = next(item for item in updated_plan["doors"] if item["id"] == door["id"])
    assert updated_door["height"] == 30
    assert updated_door["y"] == -15


def test_batch_save_creates_openings_and_handles_stale_opening_updates(api_server: str):
    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"], scale_factor=10.0)

    wall = requests.post(
        f"{api_server}/api/walls",
        json={
            "floor_plan_id": floor_plan["id"],
            "x1": 0,
            "y1": 0,
            "x2": 100,
            "y2": 0,
            "thickness": 200,
            "is_load_bearing": False,
            "length_m": 1.0,
            "length_source": "manual",
        },
        timeout=10,
    ).json()

    create_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/batch-save",
        json={
            "create_doors": [
                {
                    "floor_plan_id": floor_plan["id"],
                    "x": 20,
                    "y": -5,
                    "width": 20,
                    "height": 10,
                    "wall_id": wall["id"],
                }
            ],
            "create_windows": [
                {
                    "floor_plan_id": floor_plan["id"],
                    "x": 50,
                    "y": -5,
                    "width": 25,
                    "height": 10,
                    "wall_id": wall["id"],
                }
            ],
        },
        timeout=10,
    )
    assert create_response.status_code == 200
    created_plan = create_response.json()["floor_plan"]
    assert len(created_plan["doors"]) == 1
    assert len(created_plan["windows"]) == 1
    created_door = created_plan["doors"][0]

    delete_missing_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/batch-save",
        json={
            "deleted": [
                {"element_type": "windows", "id": 999999},
            ],
        },
        timeout=10,
    )
    assert delete_missing_response.status_code == 200
    assert len(delete_missing_response.json()["floor_plan"]["windows"]) == 1

    stale_update_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/batch-save",
        json={
            "update_doors": [
                {
                    "id": created_door["id"] + 999999,
                    "data": {"x": 30},
                }
            ]
        },
        timeout=10,
    )
    assert stale_update_response.status_code == 409
    payload = stale_update_response.json()
    assert payload["code"] == "stale_editor_state"
