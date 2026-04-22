from __future__ import annotations

import io
from types import SimpleNamespace

from reportlab.pdfgen import canvas

from ConventionalSymbolsPage import ConventionalSymbolsPage
from backend.bootstrap import register_pdf_fonts
from backend.modules.documents.conventional_symbols import build_project_conventional_symbols


def _selection(role_key: str, equipment):
    return SimpleNamespace(role_key=role_key, equipment=equipment)


def test_build_project_conventional_symbols_uses_only_symbol_bearing_elements_and_deduplicates():
    register_pdf_fonts()
    panel = SimpleNamespace(id=10, name="С2000М", category="instrument")
    smoke = SimpleNamespace(id=11, name="ДИП-34А", category="smoke")
    manual = SimpleNamespace(id=12, name="ИПР 513-3АМ", category="manual")
    siren = SimpleNamespace(id=13, name="ПКИ-1 Иволга", category="siren")
    speech = SimpleNamespace(id=14, name="Орфей-1", category="speech")
    cable = SimpleNamespace(id=15, name="КПСнг(А)-FRLS 1x2x0,75", category="cable")

    project = SimpleNamespace(
        equipment_selections=[
            _selection("common_instrument", panel),
            _selection("sps_smoke_detector", smoke),
            _selection("sps_manual_call_point", manual),
            _selection("soue_siren", siren),
            _selection("soue_speech_device", speech),
            _selection("sps_cable", cable),
        ]
    )
    floor_plan = SimpleNamespace(
        signal_instruments=[
            SimpleNamespace(id=101, instrument_type="control_panel", equipment=None, name=None),
            SimpleNamespace(id=102, instrument_type="control_panel", equipment=None, name=None),
        ],
        fire_alarms=[
            SimpleNamespace(id=201, equipment=None, device_type="smoke_detector", device_model=None),
            SimpleNamespace(id=202, equipment=None, device_type="smoke_detector", device_model=None),
            SimpleNamespace(id=203, equipment=None, device_type="manual_call_point", device_model=None),
        ],
        soue_devices=[
            SimpleNamespace(id=301, equipment=None, device_type="siren", device_model=None),
            SimpleNamespace(id=302, equipment=None, device_type="speech_device", device_model=None),
        ],
        cable_routes=[SimpleNamespace(id=401)],
    )

    payload = build_project_conventional_symbols(project, [floor_plan])

    assert [row["designation"] for row in payload["rows"]] == [
        "ARK",
        "[этаж]BTH[шлейф].[адрес]",
        "[этаж]BTM[шлейф].[адрес]",
        "[этаж]BIAS1.[номер]",
        "[этаж]BIAL2.[номер]",
    ]
    assert [row["name"] for row in payload["rows"]] == [
        "С2000М",
        "ДИП-34А",
        "ИПР 513-3АМ",
        "ПКИ-1 Иволга",
        "Орфей-1",
    ]
    assert "ARK - прибор контроля и управления." in payload["decode_lines"]
    assert "BIAL2 - световой или речевой оповещатель." in payload["decode_lines"]
    assert all("КПС" not in row["name"] for row in payload["rows"])


def test_conventional_symbols_paginate_uses_short_stamp_for_continuations():
    register_pdf_fonts()
    payload = {
        "page_title": "Условные графические обозначения",
        "heading": "УСЛОВНЫЕ ГРАФИЧЕСКИЕ ОБОЗНАЧЕНИЯ",
        "rows": [
            {
                "designation": f"[этаж]BTH[шлейф].[адрес] {index}",
                "symbol_kind": "fire_alarm",
                "symbol_type": "smoke_detector",
                "name": "Извещатель пожарный дымовой адресный очень длинного исполнения",
            }
            for index in range(40)
        ],
        "decode_lines": [
            "[этаж] - номер этажа, на котором установлен элемент.",
            "[шлейф] - номер шлейфа (линии) пожарной сигнализации.",
            "[адрес] - адрес извещателя в шлейфе.",
            "BTH - автоматический пожарный извещатель.",
        ],
    }

    segments = ConventionalSymbolsPage.paginate(payload)

    assert len(segments) > 1
    assert segments[0]["main_title_box_type"] == "1"
    assert all(segment["main_title_box_type"] == "2" for segment in segments[1:])
    assert segments[-1]["show_decode"] is True


def test_conventional_symbols_page_draw_uses_matching_symbol_drawers(monkeypatch):
    register_pdf_fonts()
    calls: list[tuple[str, str]] = []
    page = ConventionalSymbolsPage(
        conventional_symbols={
            "page_title": "Условные графические обозначения",
            "heading": "УСЛОВНЫЕ ГРАФИЧЕСКИЕ ОБОЗНАЧЕНИЯ",
            "rows": [],
            "decode_lines": [],
        },
        page_rows=[
            {"designation": "ARK", "symbol_kind": "instrument", "symbol_type": "control_panel", "name": "С2000М"},
            {
                "designation": "[этаж]BTH[шлейф].[адрес]",
                "symbol_kind": "fire_alarm",
                "symbol_type": "smoke_detector",
                "name": "ДИП-34А",
            },
            {
                "designation": "[этаж]BIAS1.[номер]",
                "symbol_kind": "soue_device",
                "symbol_type": "siren",
                "name": "ПКИ-1 Иволга",
            },
        ],
    )

    monkeypatch.setattr(
        "ConventionalSymbolsPage.draw_signal_instrument_symbol",
        lambda _c, _x, _y, instrument_type, size=0: calls.append(("instrument", instrument_type)),
    )
    monkeypatch.setattr(
        "ConventionalSymbolsPage.draw_fire_alarm_symbol",
        lambda _c, _x, _y, device_type, size=0: calls.append(("fire_alarm", device_type)),
    )
    monkeypatch.setattr(
        "ConventionalSymbolsPage.draw_soue_device_symbol",
        lambda _c, _x, _y, device_type, size=0: calls.append(("soue_device", device_type)),
    )

    page.draw(canvas.Canvas(io.BytesIO()))

    assert calls == [
        ("instrument", "control_panel"),
        ("fire_alarm", "smoke_detector"),
        ("soue_device", "siren"),
    ]
