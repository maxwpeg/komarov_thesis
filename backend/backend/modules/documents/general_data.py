"""General data payload builder and override helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from pdf_documents.GeneralDataPage import DEFAULT_GENERAL_DATA_REFERENCE_DOCUMENTS, DEFAULT_GENERAL_DATA_STATEMENT, GeneralDataPage


DEFAULT_GENERAL_DATA_PAGE_TITLE = "Общие данные"
DEFAULT_REFERENCE_CATEGORY_TITLE = "Ссылочные документы"
DEFAULT_ATTACHED_CATEGORY_TITLE = "Прилагаемые документы"
DEFAULT_LEFT_TABLE_TITLE = GeneralDataPage.LEFT_TABLE_TITLE
DEFAULT_RIGHT_TABLE_TITLE = GeneralDataPage.RIGHT_TABLE_TITLE

GENERAL_DATA_EDITABLE_TOP_LEVEL_FIELDS = (
    "page_title",
    "left_table_title",
    "right_table_title",
    "reference_category_title",
    "attached_category_title",
    "statement_text",
    "gip_name",
)

GENERAL_DATA_DOCUMENT_ROW_EDITABLE_FIELDS = ("designation", "name", "note")
GENERAL_DATA_MANIFEST_ROW_EDITABLE_FIELDS = ("name",)

GENERAL_DATA_MANIFEST_DEFINITIONS = (
    ("general_data", "Общие данные"),
    ("general_instructions", "Общие указания"),
    ("conventional_symbols", "Условные графические обозначения"),
    ("structural_scheme", "Структурная схема СПС и СОУЭ"),
    ("zkspc_plan", "План зон контроля сетей пожарной сигнализации"),
    ("sps_plan", "План сетей системы пожарной сигнализации"),
    ("soue_plan", "План сетей системы оповещения и управления эвакуацией людей при пожаре"),
    ("connection_schemes", "Схемы подключения оборудования"),
    ("equipment_specification", "Спецификация оборудования и материалов"),
    ("power_consumption", "Расчет токопотребления системы"),
    ("additional_info", "Доп. сведения"),
)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _manifest_note(sheet_count: int) -> str:
    return f"на {sheet_count}-х листах" if sheet_count > 1 else ""


def _floor_count(project: Any, floor_plans: list[Any]) -> int:
    declared = int(getattr(project, "number_of_floors", 0) or 0)
    actual = len(floor_plans)
    return declared if declared > 0 else max(actual, 1)


def build_project_general_data(
    project: Any,
    floor_plans: list[Any],
    *,
    general_instructions_sheet_count: int = 1,
    conventional_symbols_sheet_count: int = 1,
    equipment_specification_included: bool = True,
    power_consumption_sheet_count: int = 1,
    additional_info_sheet_count: int = 0,
    connection_diagrams_sheet_count: int = 1,
) -> dict[str, Any]:
    floor_count = _floor_count(project, floor_plans)
    project_code = _normalize_text(getattr(project, "code", None))
    gip_name = _normalize_text(getattr(project, "cpe", None))

    manifest_counts = {
        "general_data": 1,
        "general_instructions": max(1, int(general_instructions_sheet_count or 1)),
        "conventional_symbols": max(1, int(conventional_symbols_sheet_count or 1)),
        "structural_scheme": 1,
        "zkspc_plan": floor_count,
        "sps_plan": floor_count,
        "soue_plan": floor_count,
        "equipment_specification": 1,
        "power_consumption": max(1, int(power_consumption_sheet_count or 1)),
        "additional_info": max(0, int(additional_info_sheet_count or 0)),
        "connection_schemes": max(1, int(connection_diagrams_sheet_count or 1)),
    }

    manifest_rows: list[dict[str, Any]] = []
    for key, name in GENERAL_DATA_MANIFEST_DEFINITIONS:
        if key == "equipment_specification" and not equipment_specification_included:
            continue
        if key == "additional_info" and manifest_counts[key] < 1:
            continue
        sheet_count = manifest_counts[key]
        manifest_rows.append(
            {
                "key": key,
                "name": name,
                "sheet_count": sheet_count,
                "note": _manifest_note(sheet_count),
            }
        )

    return {
        "project_id": int(getattr(project, "id", 0) or 0),
        "page_title": DEFAULT_GENERAL_DATA_PAGE_TITLE,
        "left_table_title": DEFAULT_LEFT_TABLE_TITLE,
        "right_table_title": DEFAULT_RIGHT_TABLE_TITLE,
        "reference_category_title": DEFAULT_REFERENCE_CATEGORY_TITLE,
        "attached_category_title": DEFAULT_ATTACHED_CATEGORY_TITLE,
        "reference_documents": [
            {
                "key": f"reference_document_{index}",
                "designation": _normalize_text(row.get("designation")),
                "name": _normalize_text(row.get("name")),
                "note": _normalize_text(row.get("note")),
            }
            for index, row in enumerate(DEFAULT_GENERAL_DATA_REFERENCE_DOCUMENTS, start=1)
        ],
        "attached_documents": [
            {
                "key": "attached_document_specification",
                "designation": project_code,
                "name": "Спецификация оборудования и материалов",
                "note": "",
            }
        ],
        "drawing_manifest_rows": manifest_rows,
        "statement_text": DEFAULT_GENERAL_DATA_STATEMENT,
        "gip_name": gip_name,
    }


def apply_general_data_overrides(payload: dict[str, Any], overrides: dict[str, Any] | None) -> dict[str, Any]:
    result = deepcopy(payload)
    if not isinstance(overrides, dict):
        return result

    for field_name in GENERAL_DATA_EDITABLE_TOP_LEVEL_FIELDS:
        if isinstance(overrides.get(field_name), str):
            result[field_name] = _normalize_text(overrides[field_name])

    document_overrides = overrides.get("document_rows") if isinstance(overrides.get("document_rows"), dict) else {}
    manifest_overrides = overrides.get("manifest_rows") if isinstance(overrides.get("manifest_rows"), dict) else {}

    for section_key in ("reference_documents", "attached_documents"):
        for row in result.get(section_key) or []:
            row_override = document_overrides.get(row.get("key"))
            if not isinstance(row_override, dict):
                continue
            for field_name in GENERAL_DATA_DOCUMENT_ROW_EDITABLE_FIELDS:
                if field_name in row_override and row_override[field_name] is not None:
                    row[field_name] = _normalize_text(row_override[field_name])

    for row in result.get("drawing_manifest_rows") or []:
        row_override = manifest_overrides.get(row.get("key"))
        if not isinstance(row_override, dict):
            continue
        for field_name in GENERAL_DATA_MANIFEST_ROW_EDITABLE_FIELDS:
            if field_name in row_override and row_override[field_name] is not None:
                row[field_name] = _normalize_text(row_override[field_name])

    return result


def extract_general_data_overrides(base_payload: dict[str, Any], updated_payload: dict[str, Any]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}

    for field_name in GENERAL_DATA_EDITABLE_TOP_LEVEL_FIELDS:
        if _normalize_text(updated_payload.get(field_name)) != _normalize_text(base_payload.get(field_name)):
            overrides[field_name] = _normalize_text(updated_payload.get(field_name))

    document_row_overrides: dict[str, dict[str, str]] = {}
    manifest_row_overrides: dict[str, dict[str, str]] = {}

    updated_document_rows = {
        row.get("key"): row
        for section_key in ("reference_documents", "attached_documents")
        for row in (updated_payload.get(section_key) or [])
        if isinstance(row, dict) and row.get("key")
    }
    for section_key in ("reference_documents", "attached_documents"):
        for base_row in base_payload.get(section_key) or []:
            row_key = base_row.get("key")
            updated_row = updated_document_rows.get(row_key)
            if not isinstance(updated_row, dict):
                continue
            changed_fields: dict[str, str] = {}
            for field_name in GENERAL_DATA_DOCUMENT_ROW_EDITABLE_FIELDS:
                if _normalize_text(updated_row.get(field_name)) != _normalize_text(base_row.get(field_name)):
                    changed_fields[field_name] = _normalize_text(updated_row.get(field_name))
            if changed_fields:
                document_row_overrides[row_key] = changed_fields

    updated_manifest_rows = {
        row.get("key"): row
        for row in (updated_payload.get("drawing_manifest_rows") or [])
        if isinstance(row, dict) and row.get("key")
    }
    for base_row in base_payload.get("drawing_manifest_rows") or []:
        row_key = base_row.get("key")
        updated_row = updated_manifest_rows.get(row_key)
        if not isinstance(updated_row, dict):
            continue
        changed_fields: dict[str, str] = {}
        for field_name in GENERAL_DATA_MANIFEST_ROW_EDITABLE_FIELDS:
            if _normalize_text(updated_row.get(field_name)) != _normalize_text(base_row.get(field_name)):
                changed_fields[field_name] = _normalize_text(updated_row.get(field_name))
        if changed_fields:
            manifest_row_overrides[row_key] = changed_fields

    if document_row_overrides:
        overrides["document_rows"] = document_row_overrides
    if manifest_row_overrides:
        overrides["manifest_rows"] = manifest_row_overrides

    return overrides
