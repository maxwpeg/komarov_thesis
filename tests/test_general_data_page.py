from __future__ import annotations

from reportlab.lib.units import mm

from GeneralDataPage import DEFAULT_GENERAL_DATA_REFERENCE_DOCUMENTS, GeneralDataPage
from Project import Project
from backend.bootstrap import register_pdf_fonts


def test_build_general_data_payload_uses_project_code_cpe_and_sheet_notes(monkeypatch):
    project = Project(
        project_type="PS",
        number=12,
        year=2026,
        creds={"Facility": "Facility", "CPE": "Иванов И.И."},
        number_of_floors=2,
        floor_plans_data=[{"id": 1}, {"id": 2}],
        conventional_symbols={"page_title": "Условные графические обозначения", "rows": [], "decode_lines": []},
        equipment_specification={"project_id": 1, "sections": []},
        power_consumption_calculation={"project_id": 1, "categories": [], "summary_rows": [], "final_text": "Battery"},
    )

    monkeypatch.setattr(
        "Project.ConventionalSymbolsPage.paginate",
        lambda *args, **kwargs: [{"page_rows": []}, {"page_rows": []}],
    )
    monkeypatch.setattr(
        "Project.PowerConsumptionCalculationPage.paginate",
        lambda *args, **kwargs: [{"page_rows": []}, {"page_rows": []}, {"page_rows": []}],
    )

    payload = project._build_general_data_payload()

    assert payload["attached_documents"][0]["designation"] == project.code
    assert payload["gip_name"] == "Иванов И.И."
    assert [row["name"] for row in payload["drawing_manifest_rows"]] == [
        "Общие данные",
        "Общие указания",
        "Условные графические обозначения",
        "Структурная схема пожарной сигнализации",
        "План зон контроля сетей пожарной сигнализации",
        "План сетей системы пожарной сигнализации",
        "План сетей системы оповещения и управления эвакуацией людей при пожаре",
        "Электрические схемы соединений",
        "Спецификация оборудования и материалов",
        "Расчет токопотребления системы",
    ]
    assert payload["drawing_manifest_rows"][2]["note"] == "на 2-х листах"
    assert payload["drawing_manifest_rows"][4]["note"] == "на 2-х листах"
    assert payload["drawing_manifest_rows"][5]["note"] == "на 2-х листах"
    assert payload["drawing_manifest_rows"][6]["note"] == "на 2-х листах"
    assert payload["drawing_manifest_rows"][9]["note"] == "на 3-х листах"


def test_build_general_data_payload_omits_optional_rows_without_specification_and_power():
    project = Project(
        project_type="PS",
        number=3,
        year=2026,
        creds={"Facility": "Facility", "CPE": "Петров П.П."},
        number_of_floors=1,
        floor_plans_data=[{"id": 1}],
        conventional_symbols={"page_title": "Условные графические обозначения", "rows": [], "decode_lines": []},
        equipment_specification=None,
        power_consumption_calculation=None,
    )

    payload = project._build_general_data_payload()

    assert [row["name"] for row in payload["drawing_manifest_rows"]] == [
        "Общие данные",
        "Общие указания",
        "Условные графические обозначения",
        "Структурная схема пожарной сигнализации",
        "План зон контроля сетей пожарной сигнализации",
        "План сетей системы пожарной сигнализации",
        "План сетей системы оповещения и управления эвакуацией людей при пожаре",
        "Электрические схемы соединений",
    ]


def test_build_general_data_payload_uses_general_instructions_and_symbols_page_count(monkeypatch):
    project = Project(
        project_type="PS",
        number=4,
        year=2026,
        creds={"Facility": "Facility", "CPE": "Сидоров С.С."},
        number_of_floors=1,
        floor_plans_data=[{"id": 1}],
        general_instructions={
            "page_title": "Общие указания",
            "heading": "ОБЩИЕ УКАЗАНИЯ.",
            "local_sheet_title": "Общие указания",
            "blocks": [],
        },
        conventional_symbols={"page_title": "Условные графические обозначения", "rows": [], "decode_lines": []},
    )

    monkeypatch.setattr("Project.GeneralInstructionsPage.paginate", lambda *args, **kwargs: [{}, {}, {}])
    monkeypatch.setattr("Project.ConventionalSymbolsPage.paginate", lambda *args, **kwargs: [{}, {}])

    payload = project._build_general_data_payload()

    assert payload["drawing_manifest_rows"][1]["sheet_count"] == 3
    assert payload["drawing_manifest_rows"][1]["note"] == "на 3-х листах"
    assert payload["drawing_manifest_rows"][2]["sheet_count"] == 2
    assert payload["drawing_manifest_rows"][2]["note"] == "на 2-х листах"


def test_general_data_left_table_preparation_splits_long_cells_and_marks_categories():
    register_pdf_fonts()
    page = GeneralDataPage(
        general_data={
            "reference_documents": [
                {
                    "designation": "СП 1.1",
                    "name": "Очень длинное наименование документа для проверки переноса текста по строкам внутри левой таблицы",
                    "note": "",
                }
            ],
            "attached_documents": [
                {
                    "designation": "CODE-1",
                    "name": "Спецификация оборудования и материалов",
                    "note": "",
                }
            ],
            "drawing_manifest_rows": [],
            "statement_text": "",
            "gip_name": "",
        }
    )

    table = page._prepare_left_table(140 * mm)

    assert table["title"] == "ВЕДОМОСТЬ ССЫЛОЧНЫХ И ПРИЛАГАЕМЫХ ДОКУМЕНТОВ"
    assert page.HEADER_ROW_HEIGHT == page.BASE_ROW_HEIGHT * 2
    assert table["rows"][1]["cells"][1] == "Ссылочные документы"
    assert table["rows"][1]["underline_columns"] == {1}
    assert page._resolve_cell_alignment(table["table_key"], table["rows"][1], 1) == "center"
    assert any(row["cells"][1] == "Прилагаемые документы" for row in table["rows"])
    assert table["widths"][0] < table["widths"][1]

    continuation_rows = [
        row for row in table["rows"] if row.get("kind") == "data" and row.get("is_continuation")
    ]
    assert continuation_rows
    assert continuation_rows[0]["cells"][0] == ""
    assert continuation_rows[0]["cells"][1] != ""


def test_general_data_reference_documents_keep_last_designation_split_into_two_lines():
    register_pdf_fonts()
    page = GeneralDataPage(
        general_data={
            "reference_documents": [dict(row) for row in DEFAULT_GENERAL_DATA_REFERENCE_DOCUMENTS],
            "attached_documents": [],
            "drawing_manifest_rows": [],
        }
    )

    left_rows = page._build_left_table_logical_rows()

    assert left_rows[13]["cells"][0] == "Постановление Правительства\nРФ от 6.09.2020 № 1479"


def test_project_normalizes_stage_to_displayed_r_with_quotes():
    project = Project(
        project_type="PS",
        number=5,
        year=2026,
        creds={"Facility": "Facility", "Stage": "R"},
        number_of_floors=1,
        floor_plans_data=[],
    )

    assert project.creds["Stage"] == "«Р»"
