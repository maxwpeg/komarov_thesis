"""Application-level tests for document generation use cases."""

from __future__ import annotations

from backend.errors import AppError
from backend.modules.documents.application.use_cases import DocumentsUseCases


class _FakeProject:
    def __init__(self, payload: dict):
        self._payload = payload

    def to_dict(self):
        return dict(self._payload)


class _FakeFloorPlan:
    def __init__(self, payload: dict):
        self._payload = payload

    def to_dict(self, include_elements: bool = True):
        _ = include_elements
        return dict(self._payload)


class _FakeRepository:
    def __init__(self, *, floor_plans: list[dict]):
        self.floor_plans = floor_plans

    def get_project(self, project_id: int):
        return _FakeProject({"id": project_id, "name": "Demo"})

    def list_project_floor_plans(self, project_id: int):
        _ = project_id
        return [_FakeFloorPlan(payload) for payload in self.floor_plans]


class _FakePdfPort:
    def __init__(self):
        self.calls = []

    def generate(self, *, project_data: dict, floor_plans_data: list[dict], output_dir: str) -> str:
        self.calls.append(
            {
                "project_data": project_data,
                "floor_plans_data": floor_plans_data,
                "output_dir": output_dir,
            }
        )
        return "outputs/project.pdf"


def test_generate_project_pdf_uses_read_repository_and_pdf_port():
    pdf_port = _FakePdfPort()
    use_cases = DocumentsUseCases(
        repository=_FakeRepository(floor_plans=[{"id": 10, "name": "Floor 1"}]),
        pdf_port=pdf_port,
    )

    result = use_cases.generate_project_pdf(7)

    assert result == "outputs/project.pdf"
    assert pdf_port.calls[0]["project_data"]["id"] == 7
    assert pdf_port.calls[0]["floor_plans_data"][0]["id"] == 10


def test_generate_project_pdf_requires_at_least_one_floor_plan():
    use_cases = DocumentsUseCases(
        repository=_FakeRepository(floor_plans=[]),
        pdf_port=_FakePdfPort(),
    )

    try:
        use_cases.generate_project_pdf(1)
    except AppError as exc:
        assert exc.status_code == 400
        assert exc.code == "floor_plans_missing"
    else:
        raise AssertionError("Expected AppError when no floor plans are available")
