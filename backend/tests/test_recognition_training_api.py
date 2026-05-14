"""Recognition training API integration tests."""

from __future__ import annotations

from pathlib import Path
import time

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


def create_floor_plan(base_url: str, project_id: int, scale_factor: float, image_path: Path) -> dict:
    with image_path.open("rb") as image_file:
        response = requests.post(
            f"{base_url}/api/floor-plans",
            data={
                "project_id": str(project_id),
                "floor_number": "1",
                "name": "Floor 1",
                "scale_factor": str(scale_factor),
            },
            files={"file": ("floor.png", image_file, "image/png")},
            timeout=10,
        )
    assert response.status_code == 200
    return response.json()


def wait_background_task(base_url: str, task: dict, timeout_seconds: float = 15.0) -> dict:
    deadline = time.monotonic() + timeout_seconds
    current = task
    while time.monotonic() < deadline:
        if current["status"] in {"succeeded", "failed", "canceled"}:
            break
        time.sleep(0.2)
        response = requests.get(f"{base_url}/api/background-tasks/{task['id']}", timeout=10)
        assert response.status_code == 200
        current = response.json()
    assert current["status"] == "succeeded", current
    return current


def test_recognition_training_examples_overview_and_curation(api_server: str, tmp_path: Path):
    image_path = tmp_path / "recognition-training-api.png"
    Image.new("RGB", (240, 240), color="white").save(image_path)

    project = create_project(api_server)
    floor_plan = create_floor_plan(api_server, project["id"], scale_factor=10.0, image_path=image_path)

    detect_response = requests.post(f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/walls/detect", timeout=10)
    assert detect_response.status_code == 202
    wait_background_task(api_server, detect_response.json())

    commit_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/walls/commit",
        json={
            "changes": {
                "create_walls": [
                    {
                        "floor_plan_id": floor_plan["id"],
                        "x1": 20,
                        "y1": 60,
                        "x2": 180,
                        "y2": 60,
                        "thickness": 200,
                        "length_m": 1.6,
                        "length_source": "manual",
                    }
                ],
            },
            "wall_lengths": [],
        },
        timeout=10,
    )
    assert commit_response.status_code == 200

    feedback_response = requests.post(
        f"{api_server}/api/floor-plans/{floor_plan['id']}/pipeline/walls/feedback",
        json={"step_revision": 1, "issue_tags": ["missed"], "notes": "wall restored manually"},
        timeout=10,
    )
    assert feedback_response.status_code == 200

    overview_response = requests.get(f"{api_server}/api/recognition-training/overview", timeout=10)
    assert overview_response.status_code == 200
    walls_overview = next(item for item in overview_response.json()["steps"] if item["step"] == "walls")
    assert walls_overview["approved_examples"] == 1
    assert walls_overview["excluded_examples"] == 0
    assert walls_overview["recommended_batch_size"] == 50
    assert walls_overview["thresholds"]["approved_examples"] == 50

    examples_response = requests.get(f"{api_server}/api/recognition-training/examples", timeout=10)
    assert examples_response.status_code == 200
    examples = examples_response.json()
    assert len(examples) == 1
    example_id = examples[0]["id"]
    assert examples[0]["curation_status"] == "approved"
    assert examples[0]["changed"] is True

    detail_response = requests.get(f"{api_server}/api/recognition-training/examples/{example_id}", timeout=10)
    assert detail_response.status_code == 200
    assert detail_response.json()["source_snapshot"]["step"] == "walls"

    patch_response = requests.patch(
        f"{api_server}/api/recognition-training/examples/{example_id}",
        json={"curation_status": "excluded", "issue_tags": ["noise"], "notes": "exclude this sample"},
        timeout=10,
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["curation_status"] == "excluded"
    assert patch_response.json()["issue_tags"] == ["noise"]

    bulk_response = requests.post(
        f"{api_server}/api/recognition-training/examples/bulk-curate",
        json={"example_ids": [example_id], "curation_status": "approved"},
        timeout=10,
    )
    assert bulk_response.status_code == 200
    assert bulk_response.json()["updated_count"] == 1

    restored_detail = requests.get(f"{api_server}/api/recognition-training/examples/{example_id}", timeout=10)
    assert restored_detail.status_code == 200
    assert restored_detail.json()["curation_status"] == "approved"
