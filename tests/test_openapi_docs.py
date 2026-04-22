from __future__ import annotations

import re

from backend.app import API_DESCRIPTION, API_SUMMARY, API_TITLE, OPENAPI_TAGS, create_app


CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")


def _public_operations(schema: dict) -> list[tuple[str, str, dict]]:
    operations: list[tuple[str, str, dict]] = []
    for path, path_item in schema["paths"].items():
        for method, operation in path_item.items():
            if not isinstance(operation, dict):
                continue
            if path == "/" or path.startswith("/health") or path.startswith("/api/"):
                operations.append((path, method, operation))
    return operations


def test_openapi_info_and_tags_are_documented_in_russian():
    schema = create_app().openapi()

    assert schema["info"]["title"] == API_TITLE
    assert schema["info"]["summary"] == API_SUMMARY
    assert schema["info"]["description"] == API_DESCRIPTION
    assert CYRILLIC_RE.search(schema["info"]["description"])

    documented_tags = {item["name"]: item.get("description", "") for item in schema["tags"]}
    assert set(documented_tags) >= {item["name"] for item in OPENAPI_TAGS}
    for name, description in documented_tags.items():
        assert description, f"Тег {name} должен иметь описание"
        assert CYRILLIC_RE.search(description), f"Описание тега {name} должно быть на русском языке"


def test_every_public_operation_has_summary_description_and_response_descriptions():
    schema = create_app().openapi()

    for path, method, operation in _public_operations(schema):
        assert operation.get("summary"), f"{method.upper()} {path}: отсутствует summary"
        assert operation.get("description"), f"{method.upper()} {path}: отсутствует description"
        assert CYRILLIC_RE.search(operation["summary"]), f"{method.upper()} {path}: summary должен быть на русском"
        assert CYRILLIC_RE.search(operation["description"]), f"{method.upper()} {path}: description должен быть на русском"

        for response_code, response in operation.get("responses", {}).items():
            assert response.get("description"), f"{method.upper()} {path}: response {response_code} без описания"

        for parameter in operation.get("parameters", []):
            assert parameter.get("description"), (
                f"{method.upper()} {path}: параметр {parameter.get('name')} должен иметь описание"
            )


def test_key_public_schemas_have_descriptions_and_examples():
    schema = create_app().openapi()
    components = schema["components"]["schemas"]

    key_schemas = [
        "ProjectCreate",
        "ProjectRead",
        "EquipmentItemCreate",
        "EquipmentSpecificationRead",
        "PowerConsumptionCalculationRead",
        "GeneralInstructionsRead",
        "GeneralDataRead",
        "AdditionalInfoRead",
        "FloorPlanRead",
        "RecognitionTrainingRunCreateRequest",
    ]
    for schema_name in key_schemas:
        definition = components[schema_name]
        assert definition.get("description"), f"Схема {schema_name} должна иметь описание"

    assert components["ProjectCreate"].get("example")
    assert components["EquipmentItemCreate"].get("example")
    assert components["GeneralDataRead"].get("example")
    assert components["RecognitionTrainingRunCreateRequest"].get("example")

    assert components["ProjectCreate"]["properties"]["facility"]["description"]
    assert components["ProjectCreate"]["properties"]["facility_address"]["description"]
    assert components["FloorPlanRead"]["properties"]["scale_factor"]["description"]
    assert components["PowerConsumptionCalculationRead"]["properties"]["final_text"]["description"]
    assert components["GeneralDataRead"]["properties"]["statement_text"]["description"]
    assert components["AdditionalInfoRead"]["properties"]["text"]["description"]


def test_openapi_contains_expected_router_paths():
    schema = create_app().openapi()
    paths = set(schema["paths"])

    expected_paths = {
        "/",
        "/health/live",
        "/health/ready",
        "/api/projects",
        "/api/projects/{project_id}",
        "/api/floor-plans/{floor_plan_id}",
        "/api/equipment",
        "/api/floor-plans/{floor_plan_id}/pipeline-state",
        "/api/floor-plans/{floor_plan_id}/process",
        "/api/projects/{project_id}/generate-pdf",
    }
    assert expected_paths.issubset(paths)
