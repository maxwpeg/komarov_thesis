from __future__ import annotations

import io

import requests
from PIL import Image


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (24, 24), color="white").save(buffer, format="PNG")
    return buffer.getvalue()


def _create_engineer(base_url: str, username: str, full_name: str) -> dict:
    response = requests.post(
        f"{base_url}/api/users",
        json={
            "username": username,
            "full_name": full_name,
            "role": "engineer",
            "password": "engineer-pass",
            "is_active": True,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def _engineer_session(base_url: str, username: str) -> requests.Session:
    session = requests.Session()
    response = session.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": "engineer-pass"},
        headers={"X-Skip-Test-Auth": "1"},
        timeout=10,
    )
    response.raise_for_status()
    return session


def _create_project(base_url: str, *, owner_user_id: int) -> dict:
    response = requests.post(
        f"{base_url}/api/projects",
        json={
            "name": f"Project {owner_user_id}",
            "project_type": "PS",
            "year": 2026,
            "contractor": "Contractor",
            "engineer": "Engineer",
            "cpe": "CPE",
            "checker": "Checker",
            "facility": f"Facility {owner_user_id}",
            "facility_address": "Address",
            "project_description": "Description",
            "stage": "R",
            "number_of_floors": 1,
            "owner_user_id": owner_user_id,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def _create_floor_plan_with_image(base_url: str, project_id: int) -> dict:
    response = requests.post(
        f"{base_url}/api/floor-plans",
        data={
            "project_id": str(project_id),
            "floor_number": "1",
            "name": "Floor 1",
            "scale_factor": "10",
        },
        files={"file": ("floor.png", _png_bytes(), "image/png")},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()


def test_asset_route_rejects_path_traversal(api_server: str):
    traversal_response = requests.get(f"{api_server}/api/assets/%2e%2e/floor_plans.db", timeout=10)
    assert traversal_response.status_code == 404
    assert traversal_response.json()["code"] == "asset_not_found"

    prefixed_traversal_response = requests.get(
        f"{api_server}/api/assets/uploads/%2e%2e/floor_plans.db",
        timeout=10,
    )
    assert prefixed_traversal_response.status_code == 404
    assert prefixed_traversal_response.json()["code"] == "asset_not_found"


def test_engineer_cannot_read_another_engineers_floor_plan_asset(api_server: str):
    engineer_one = _create_engineer(api_server, "asset-engineer-one", "Asset Engineer One")
    engineer_two = _create_engineer(api_server, "asset-engineer-two", "Asset Engineer Two")
    project_one = _create_project(api_server, owner_user_id=engineer_one["id"])
    project_two = _create_project(api_server, owner_user_id=engineer_two["id"])
    floor_one = _create_floor_plan_with_image(api_server, project_one["id"])
    floor_two = _create_floor_plan_with_image(api_server, project_two["id"])

    engineer_session = _engineer_session(api_server, "asset-engineer-one")

    own_response = engineer_session.get(f"{api_server}{floor_one['original_image_url']}", timeout=10)
    assert own_response.status_code == 200

    foreign_response = engineer_session.get(f"{api_server}{floor_two['original_image_url']}", timeout=10)
    assert foreign_response.status_code == 403
    assert foreign_response.json()["code"] == "project_access_denied"


def test_upload_validation_rejects_wrong_extension_and_fake_image(api_server: str):
    engineer = _create_engineer(api_server, "upload-owner", "Upload Owner")
    project = _create_project(api_server, owner_user_id=engineer["id"])

    wrong_extension = requests.post(
        f"{api_server}/api/floor-plans",
        data={"project_id": str(project["id"]), "floor_number": "1"},
        files={"file": ("floor.txt", b"not an image", "text/plain")},
        timeout=10,
    )
    assert wrong_extension.status_code == 400
    assert wrong_extension.json()["code"] == "unsupported_upload_extension"

    fake_image = requests.post(
        f"{api_server}/api/floor-plans",
        data={"project_id": str(project["id"]), "floor_number": "1"},
        files={"file": ("floor.png", b"%PDF-1.7 fake", "image/png")},
        timeout=10,
    )
    assert fake_image.status_code == 400
    assert fake_image.json()["code"] == "invalid_upload_file"


def test_uploaded_floor_plan_is_registered_in_storage_integrity_report(api_server: str):
    engineer = _create_engineer(api_server, "storage-owner", "Storage Owner")
    project = _create_project(api_server, owner_user_id=engineer["id"])
    floor_plan = _create_floor_plan_with_image(api_server, project["id"])

    report_response = requests.get(f"{api_server}/api/storage/integrity", timeout=10)
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["registered_count"] >= 1
    assert report["missing_count"] == 0
    assert not any(item["path"] == floor_plan["original_image_path"] for item in report["missing"])


def test_engineer_cannot_mutate_global_equipment_catalog(api_server: str):
    engineer = _create_engineer(api_server, "catalog-engineer", "Catalog Engineer")
    engineer_session = _engineer_session(api_server, engineer["username"])
    response = engineer_session.post(
        f"{api_server}/api/equipment",
        json={
            "name": "Smoke Engineer",
            "category": "smoke",
            "description": "Should not be created by engineer",
            "price": 1000,
            "manufacturer": "Test",
            "service_life_years": 10,
            "specs": {
                "addressing_mode": "addressable",
                "loop_voltage_v": 24,
                "standby_current_a": 0.0001,
                "alarm_current_a": 0.0002,
            },
            "compatible_equipment_ids": [],
        },
        timeout=10,
    )

    assert response.status_code == 403
    assert response.json()["code"] == "developer_role_required"
