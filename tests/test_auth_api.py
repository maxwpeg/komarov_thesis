"""Authentication and authorization integration tests."""

from __future__ import annotations

import os

import requests


SKIP_AUTH = {"X-Skip-Test-Auth": "1"}


def _bootstrap_credentials() -> dict[str, str]:
    return {
        "username": os.environ["BOOTSTRAP_DEVELOPER_USERNAME"],
        "password": os.environ["BOOTSTRAP_DEVELOPER_PASSWORD"],
    }


def _create_project(base_url: str, **overrides) -> dict:
    payload = {
        "name": "Scoped Project",
        "project_type": "PS",
        "contractor": "Contractor",
        "engineer": "Engineer",
        "cpe": "CPE",
        "checker": "Checker",
        "facility": "Facility",
        "facility_address": "Address",
        "project_description": "Description",
        "stage": "R",
        "number_of_floors": 1,
    }
    payload.update(overrides)
    response = requests.post(f"{base_url}/api/projects", json=payload, timeout=10)
    response.raise_for_status()
    return response.json()


def test_business_endpoints_require_auth(api_server: str):
    response = requests.get(f"{api_server}/api/projects", headers=SKIP_AUTH, timeout=10)
    assert response.status_code == 401
    assert response.json()["code"] == "auth_required"

    root_response = requests.get(f"{api_server}/", headers=SKIP_AUTH, timeout=10)
    assert root_response.status_code == 200


def test_login_me_logout_flow(api_server: str):
    wrong_password = requests.post(
        f"{api_server}/api/auth/login",
        json={"username": _bootstrap_credentials()["username"], "password": "wrong-password"},
        headers=SKIP_AUTH,
        timeout=10,
    )
    assert wrong_password.status_code == 401
    assert wrong_password.json()["code"] == "invalid_credentials"

    session = requests.Session()
    login_response = session.post(
        f"{api_server}/api/auth/login",
        json=_bootstrap_credentials(),
        headers=SKIP_AUTH,
        timeout=10,
    )
    assert login_response.status_code == 200
    assert login_response.json()["role"] == "developer"

    me_response = session.get(f"{api_server}/api/auth/me", timeout=10)
    assert me_response.status_code == 200
    assert me_response.json()["username"] == _bootstrap_credentials()["username"]

    logout_response = session.post(f"{api_server}/api/auth/logout", timeout=10)
    assert logout_response.status_code == 200

    logged_out_me = session.get(f"{api_server}/api/auth/me", headers=SKIP_AUTH, timeout=10)
    assert logged_out_me.status_code == 401


def test_engineer_only_sees_owned_projects_and_auto_owns_new_ones(api_server: str):
    create_user_response = requests.post(
        f"{api_server}/api/users",
        json={
            "username": "engineer1",
            "full_name": "Engineer One",
            "role": "engineer",
            "password": "engineer-pass",
            "is_active": True,
        },
        timeout=10,
    )
    assert create_user_response.status_code == 200
    engineer = create_user_response.json()

    unassigned_project = _create_project(api_server, name="Unassigned", facility="Unassigned")
    assigned_project = _create_project(
        api_server,
        name="Assigned",
        facility="Assigned",
        owner_user_id=engineer["id"],
    )

    engineer_session = requests.Session()
    login_response = engineer_session.post(
        f"{api_server}/api/auth/login",
        json={"username": "engineer1", "password": "engineer-pass"},
        headers=SKIP_AUTH,
        timeout=10,
    )
    assert login_response.status_code == 200
    assert login_response.json()["role"] == "engineer"

    list_response = engineer_session.get(f"{api_server}/api/projects", timeout=10)
    assert list_response.status_code == 200
    assert [item["id"] for item in list_response.json()] == [assigned_project["id"]]

    foreign_project_response = engineer_session.get(
        f"{api_server}/api/projects/{unassigned_project['id']}",
        timeout=10,
    )
    assert foreign_project_response.status_code == 403
    assert foreign_project_response.json()["code"] == "project_access_denied"

    own_project_response = engineer_session.post(
        f"{api_server}/api/projects",
        json={
            "name": "Engineer-owned",
            "project_type": "PS",
            "contractor": "Contractor",
            "engineer": "Engineer One",
            "cpe": "CPE",
            "checker": "Checker",
            "facility": "Engineer Facility",
            "facility_address": "Address",
            "project_description": "Description",
            "stage": "R",
            "number_of_floors": 1,
        },
        timeout=10,
    )
    assert own_project_response.status_code == 200
    assert own_project_response.json()["owner_user_id"] == engineer["id"]


def test_last_active_developer_cannot_be_demoted_or_deactivated(api_server: str):
    me_response = requests.get(f"{api_server}/api/auth/me", timeout=10)
    developer_id = me_response.json()["id"]

    demote_response = requests.patch(
        f"{api_server}/api/users/{developer_id}",
        json={"role": "engineer"},
        timeout=10,
    )
    assert demote_response.status_code == 409
    assert demote_response.json()["code"] == "last_active_developer_required"

    deactivate_response = requests.patch(
        f"{api_server}/api/users/{developer_id}",
        json={"is_active": False},
        timeout=10,
    )
    assert deactivate_response.status_code == 409
    assert deactivate_response.json()["code"] == "last_active_developer_required"
