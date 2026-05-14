from __future__ import annotations

from types import SimpleNamespace

from GeneralInstructionsPage import GeneralInstructionsPage
from backend.bootstrap import register_pdf_fonts
from backend.modules.documents.general_instructions import build_project_general_instructions


def _selection(role_key: str, equipment) -> SimpleNamespace:
    return SimpleNamespace(role_key=role_key, equipment=equipment)


def test_build_general_instructions_uses_project_cases_and_selected_equipment():
    panel = SimpleNamespace(
        id=10,
        name="С2000-КДЛ",
        category="instrument",
        manufacturer="Болид",
        specs={"instrument_subtype": "security_fire_control_panel"},
    )
    smoke = SimpleNamespace(id=11, name="ДИП-34А", category="smoke")
    manual = SimpleNamespace(id=12, name="ИПР 513-3АМ", category="manual")
    siren = SimpleNamespace(id=13, name="ПКИ-1 Иволга", category="siren")
    exit_sign = SimpleNamespace(id=14, name="Молния-12 \"Выход\"", category="exit_sign")
    sps_cable = SimpleNamespace(id=15, name="КПСнг(A)-FRLS 1x2x0,75", category="cable")
    soue_cable = SimpleNamespace(id=16, name="КПСнг(A)-FRLS 1x2x1,5", category="cable")

    project = SimpleNamespace(
        id=1,
        facility="Магазин",
        facility_genitive="Магазина",
        facility_instrumental="Магазином",
        facility_address="г. Москва, ул. Примерная, д. 1",
        number_of_floors=2,
        equipment_selections=[
            _selection("common_instrument", panel),
            _selection("sps_smoke_detector", smoke),
            _selection("sps_manual_call_point", manual),
            _selection("soue_siren", siren),
            _selection("soue_exit_sign", exit_sign),
            _selection("sps_cable", sps_cable),
            _selection("soue_cable", soue_cable),
        ],
    )
    floor_plan = SimpleNamespace(
        active_signal_system_type="addressable",
        ceiling_height_mm=3200,
        zkspc_zones=[SimpleNamespace(id=1), SimpleNamespace(id=2)],
        signal_instruments=[SimpleNamespace(id=100, equipment=None)],
        fire_alarms=[
            SimpleNamespace(id=101, equipment=None, device_type="smoke_detector"),
            SimpleNamespace(id=102, equipment=None, device_type="manual_call_point"),
        ],
        soue_devices=[
            SimpleNamespace(id=103, equipment=None, device_type="siren"),
            SimpleNamespace(id=104, equipment=None, device_type="exit_sign"),
        ],
    )

    payload = build_project_general_instructions(project, [floor_plan])
    paragraph_texts = [block["text"] for block in payload["blocks"] if block.get("kind") == "paragraph"]
    bullet_lists = [block["items"] for block in payload["blocks"] if block.get("kind") == "bullet_list"]

    assert payload["page_title"] == "Общие указания"
    assert "Магазина" in paragraph_texts[0]
    assert "Магазином" in paragraph_texts[2]
    assert any("Болид" in text for text in paragraph_texts)
    assert any("С2000-КДЛ" in text for text in paragraph_texts)
    assert any("2 ЗКСПС" in text for text in paragraph_texts)
    assert any("КПСнг(A)-FRLS 1x2x0,75, КПСнг(A)-FRLS 1x2x1,5" in text for text in paragraph_texts)
    assert any(items == ["С2000-КДЛ", "ДИП-34А", "ИПР 513-3АМ", "ПКИ-1 Иволга", "Молния-12 \"Выход\""] for items in bullet_lists)


def test_build_general_instructions_falls_back_to_facility_when_cases_missing():
    project = SimpleNamespace(
        id=2,
        facility="Офис",
        facility_genitive=None,
        facility_instrumental=None,
        facility_address="",
        number_of_floors=1,
        equipment_selections=[],
    )
    floor_plan = SimpleNamespace(
        active_signal_system_type="non_addressable",
        ceiling_height_mm=3000,
        zkspc_zones=[],
        signal_instruments=[],
        fire_alarms=[],
        soue_devices=[],
    )

    payload = build_project_general_instructions(project, [floor_plan])
    paragraph_texts = [block["text"] for block in payload["blocks"] if block.get("kind") == "paragraph"]

    assert "Офис" in paragraph_texts[0]
    assert "Офис" in paragraph_texts[2]


def test_general_instructions_paginate_uses_short_stamp_for_continuations():
    register_pdf_fonts()
    instructions = {
        "page_title": "Общие указания",
        "heading": "ОБЩИЕ УКАЗАНИЯ.",
        "local_sheet_title": "Общие указания",
        "blocks": [
            {
                "kind": "paragraph",
                "text": " ".join(["Текст"] * 1400),
            }
        ],
    }

    segments = GeneralInstructionsPage.paginate(instructions)

    assert len(segments) > 1
    assert segments[0]["main_title_box_type"] == "1"
    assert segments[0]["show_heading"] is True
    assert all(segment["main_title_box_type"] == "2" for segment in segments[1:])
    assert all(segment["show_heading"] is False for segment in segments[1:])

    page = GeneralInstructionsPage(
        instructions=instructions,
        page_lines=segments[1]["page_lines"],
        show_heading=False,
        is_continuation=True,
        local_sheet_number=2,
        local_total_sheets=5,
        main_title_box_type="2",
    )
    assert page.creds["Sheet Number"] == "2"
    assert page.creds["Total Sheets"] == "5"
