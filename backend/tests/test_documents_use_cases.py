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
        self.saved_general_data_payload = None
        self.saved_general_instructions_payload = None
        self.saved_power_payload = None
        self.saved_additional_info_payload = None

    def get_project(self, project_id: int):
        return _FakeProject({"id": project_id, "name": "Demo"})

    def list_project_floor_plans(self, project_id: int):
        _ = project_id
        return [_FakeFloorPlan(payload) for payload in self.floor_plans]

    def get_project_equipment_specification(self, project_id: int):
        return {
            "project_id": project_id,
            "page_title": "Spec",
            "column_headers": ["A", "B", "C", "D", "E", "F", "G", "H", "I"],
            "sections": [],
            "warnings": [],
        }

    def get_project_general_data(self, project_id: int):
        return {
            "project_id": project_id,
            "page_title": "Общие данные",
            "left_table_title": "ВЕДОМОСТЬ ССЫЛОЧНЫХ И ПРИЛАГАЕМЫХ ДОКУМЕНТОВ",
            "right_table_title": "ВЕДОМОСТЬ РАБОЧИХ ЧЕРТЕЖЕЙ ОСНОВНОГО КОМПЛЕКТА",
            "reference_category_title": "Ссылочные документы",
            "attached_category_title": "Прилагаемые документы",
            "reference_documents": [],
            "attached_documents": [],
            "drawing_manifest_rows": [],
            "statement_text": "Statement",
            "gip_name": "Иванов И.И.",
        }

    def get_project_general_instructions(self, project_id: int):
        return {
            "project_id": project_id,
            "page_title": "Общие указания",
            "heading": "ОБЩИЕ УКАЗАНИЯ.",
            "local_sheet_title": "Общие указания",
            "blocks": [{"key": "block_1", "kind": "paragraph", "text": "Текст"}],
        }

    def get_project_conventional_symbols(self, project_id: int):
        return {
            "project_id": project_id,
            "page_title": "Условные графические обозначения",
            "heading": "УСЛОВНЫЕ ГРАФИЧЕСКИЕ ОБОЗНАЧЕНИЯ",
            "rows": [],
            "decode_lines": [],
        }

    def get_project_structural_scheme(self, project_id: int):
        return {
            "project_id": project_id,
            "page_title": "Структурная схема СПС и СОУЭ",
            "floors": [],
            "instruments": [],
            "equipment_totals": [],
        }

    def get_project_power_consumption_calculation(self, project_id: int):
        return {
            "project_id": project_id,
            "page_title": "Power",
            "categories": [],
            "summary_rows": [],
            "final_text": "Battery text",
        }

    def get_project_additional_info(self, project_id: int):
        return {
            "project_id": project_id,
            "page_title": "Доп. сведения",
            "heading": "ДОП. СВЕДЕНИЯ",
            "local_sheet_title": "Доп. сведения",
            "text": "",
            "is_empty": True,
            "blocks": [],
        }

    def get_project_connection_diagrams(self, project_id: int):
        return [
            {
                "equipment_id": 101,
                "name": "Smoke A",
                "connection_diagram_path": "equipment/101/connection_diagram.png",
            }
        ]

    def update_project_equipment_specification(self, project_id: int, payload):
        _ = payload
        return self.get_project_equipment_specification(project_id)

    def update_project_general_data(self, project_id: int, payload):
        self.saved_general_data_payload = payload
        return {
            **self.get_project_general_data(project_id),
            **payload,
        }

    def update_project_general_instructions(self, project_id: int, payload):
        self.saved_general_instructions_payload = payload
        return {
            **self.get_project_general_instructions(project_id),
            **payload,
        }

    def update_project_power_consumption_calculation(self, project_id: int, payload):
        self.saved_power_payload = payload
        return self.get_project_power_consumption_calculation(project_id)

    def update_project_additional_info(self, project_id: int, payload):
        self.saved_additional_info_payload = payload
        return {
            **self.get_project_additional_info(project_id),
            "text": payload.get("text", ""),
            "is_empty": not bool(str(payload.get("text", "")).strip()),
        }


class _FakeUnitOfWork:
    def commit(self):
        return None

    def rollback(self):
        return None


class _FakePdfPort:
    def __init__(self):
        self.calls = []

    def generate(
        self,
        *,
        project_data: dict,
        floor_plans_data: list[dict],
        general_data: dict | None,
        general_instructions: dict | None,
        conventional_symbols: dict | None,
        equipment_specification: dict | None,
        power_consumption_calculation: dict | None,
        additional_info: dict | None,
        structural_scheme: dict | None,
        connection_diagrams: list[dict] | None,
        output_dir: str,
    ) -> str:
        self.calls.append(
            {
                "project_data": project_data,
                "floor_plans_data": floor_plans_data,
                "general_data": general_data,
                "general_instructions": general_instructions,
                "conventional_symbols": conventional_symbols,
                "equipment_specification": equipment_specification,
                "power_consumption_calculation": power_consumption_calculation,
                "additional_info": additional_info,
                "structural_scheme": structural_scheme,
                "connection_diagrams": connection_diagrams,
                "output_dir": output_dir,
            }
        )
        return "outputs/project.pdf"


def test_generate_project_pdf_uses_read_repository_and_pdf_port():
    pdf_port = _FakePdfPort()
    use_cases = DocumentsUseCases(
        repository=_FakeRepository(floor_plans=[{"id": 10, "name": "Floor 1"}]),
        uow=_FakeUnitOfWork(),
        pdf_port=pdf_port,
    )

    result = use_cases.generate_project_pdf(7)

    assert result == "outputs/project.pdf"
    assert pdf_port.calls[0]["project_data"]["id"] == 7
    assert pdf_port.calls[0]["floor_plans_data"][0]["id"] == 10
    assert pdf_port.calls[0]["general_data"]["page_title"] == "Общие данные"
    assert pdf_port.calls[0]["general_instructions"]["page_title"] == "Общие указания"
    assert pdf_port.calls[0]["conventional_symbols"]["page_title"] == "Условные графические обозначения"
    assert pdf_port.calls[0]["equipment_specification"]["project_id"] == 7
    assert pdf_port.calls[0]["power_consumption_calculation"]["page_title"] == "Power"
    assert pdf_port.calls[0]["additional_info"]["page_title"] == "Доп. сведения"
    assert pdf_port.calls[0]["structural_scheme"]["page_title"] == "Структурная схема СПС и СОУЭ"
    assert pdf_port.calls[0]["connection_diagrams"][0]["equipment_id"] == 101


def test_generate_project_pdf_requires_at_least_one_floor_plan():
    use_cases = DocumentsUseCases(
        repository=_FakeRepository(floor_plans=[]),
        uow=_FakeUnitOfWork(),
        pdf_port=_FakePdfPort(),
    )

    try:
        use_cases.generate_project_pdf(1)
    except AppError as exc:
        assert exc.status_code == 400
        assert exc.code == "floor_plans_missing"
    else:
        raise AssertionError("Expected AppError when no floor plans are available")


def test_update_project_general_data_delegates_to_repository():
    repository = _FakeRepository(floor_plans=[{"id": 10, "name": "Floor 1"}])
    use_cases = DocumentsUseCases(
        repository=repository,
        uow=_FakeUnitOfWork(),
        pdf_port=_FakePdfPort(),
    )

    result = use_cases.update_project_general_data(7, {"page_title": "Общие данные проекта"})

    assert result["page_title"] == "Общие данные проекта"
    assert repository.saved_general_data_payload == {"page_title": "Общие данные проекта"}


def test_update_project_general_instructions_delegates_to_repository():
    repository = _FakeRepository(floor_plans=[{"id": 10, "name": "Floor 1"}])
    use_cases = DocumentsUseCases(
        repository=repository,
        uow=_FakeUnitOfWork(),
        pdf_port=_FakePdfPort(),
    )

    result = use_cases.update_project_general_instructions(7, {"page_title": "Общие указания проекта"})

    assert result["page_title"] == "Общие указания проекта"
    assert repository.saved_general_instructions_payload == {"page_title": "Общие указания проекта"}


def test_update_project_power_consumption_calculation_delegates_to_repository():
    repository = _FakeRepository(floor_plans=[{"id": 10, "name": "Floor 1"}])
    use_cases = DocumentsUseCases(
        repository=repository,
        uow=_FakeUnitOfWork(),
        pdf_port=_FakePdfPort(),
    )

    result = use_cases.update_project_power_consumption_calculation(7, {"page_title": "Power"})

    assert result["page_title"] == "Power"
    assert repository.saved_power_payload == {"page_title": "Power"}


def test_update_project_additional_info_delegates_to_repository():
    repository = _FakeRepository(floor_plans=[{"id": 10, "name": "Floor 1"}])
    use_cases = DocumentsUseCases(
        repository=repository,
        uow=_FakeUnitOfWork(),
        pdf_port=_FakePdfPort(),
    )

    result = use_cases.update_project_additional_info(7, {"text": "Примечание"})

    assert result["text"] == "Примечание"
    assert repository.saved_additional_info_payload == {"text": "Примечание"}
