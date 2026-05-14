"""General instructions payload builder and override helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.modules.documents.specification import (
    _resolve_fire_alarm_equipment,
    _resolve_instrument_equipment,
    _resolve_soue_equipment,
)


GENERAL_INSTRUCTIONS_PAGE_TITLE = "Общие указания"
GENERAL_INSTRUCTIONS_HEADING = "ОБЩИЕ УКАЗАНИЯ."
GENERAL_INSTRUCTIONS_EDITABLE_TOP_LEVEL_FIELDS = ("page_title", "heading", "local_sheet_title")

INTRO_REFERENCE_BULLETS = (
    "ФЗ Российской Федерации от 22 июня 2008 г. № 123-ФЗ «Технический регламент о требованиях пожарной безопасности»",
    "Постановление правительства РФ от 16.02.2008 г. № 87\" О составе разделов проектной документации и требования к их содержанию»",
    "СП 484.1311500.2020 «Системы пожарной сигнализации и автоматизация систем пожарной сигнализации. Требования пожарной безопасности» (с изм. №1 от 01.09.2025)",
    "СП 486.1311500.2020. «Перечень зданий, сооружений, помещений и оборудования, подлежащих защите автоматическими установками пожаротушения и системами пожарной сигнализации. Требования пожарной безопасности»",
    "СП 3.13130.2009 «Система оповещения и управления эвакуацией людей при пожаре. Требования пожарной безопасности»",
    "СП 6.13130.2021 «Электрооборудование»",
    "СП 51.1330.2011 «Защита от шума»",
    "ГОСТ 53325-2012 «Кабельные изделия. Требования пожарной безопасности»",
    "ГОСТ Р 21.1101 «СПДС. Основные требования к рабочей и проектной документации»",
    "РД 78.145-93 «Системы и комплексы охранной, пожарной и охранно-пожарной сигнализации. Правила производства и приемки работ.",
    "ПУЭ изд.7 «Правила устройства электроустановок»",
    "Постановление правительства РФ от 16.09.2020 № 1479 «Об утверждении Правил противопожарного режима в Российской Федерации»",
)

TECHNOLOGY_BULLETS = (
    "сбор, обработку, передачу извещений о состоянии разделов пожарной сигнализации;",
    "контроль состояния неисправности пожарных извещателей, приборов, линий связи, наличии напряжения на источнике питания;",
    "автоматический запуск системы оповещения и управления эвакуацией людей при пожаре;",
    "ведение протокола событий.",
)

SOUE_TYPE_TEXT = "2-го типа"
FIRE_HAZARD_CLASS_TEXT = "Ф 4.3 и Ф5.2"
FIRE_RESISTANCE_TEXT = "III"
CONSTRUCTIVE_FIRE_HAZARD_TEXT = "C1"

DETECTOR_CATEGORY_ORDER = {
    "smoke": 10,
    "heat": 20,
    "linear": 30,
    "manual": 40,
}

DEVICE_CATEGORY_ORDER = {
    "instrument": 10,
    "keyboard": 20,
    "smoke": 30,
    "heat": 40,
    "linear": 50,
    "manual": 60,
    "siren": 70,
    "exit_sign": 80,
    "speech": 90,
}


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_item_list(items: list[Any] | None) -> list[str]:
    return [_normalize_text(item) for item in (items or [])]


def _selection_map(project: Any) -> dict[str, Any]:
    return {
        row.role_key: row.equipment
        for row in (getattr(project, "equipment_selections", None) or [])
        if getattr(row, "equipment", None) is not None
    }


def _dedupe_sorted(equipment_items: list[Any], *, category_order: dict[str, int] | None = None) -> list[Any]:
    by_id: dict[int, Any] = {}
    for item in equipment_items:
        item_id = int(getattr(item, "id", 0) or 0)
        if item_id <= 0 or item_id in by_id:
            continue
        by_id[item_id] = item
    ordered = list(by_id.values())
    ordered.sort(
        key=lambda item: (
            (category_order or {}).get(_normalize_text(getattr(item, "category", "")), 999),
            _normalize_text(getattr(item, "name", "")).lower(),
            int(getattr(item, "id", 0) or 0),
        )
    )
    return ordered


def _format_float(value: float) -> str:
    text = f"{float(value):.2f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text.replace(".", ",")


def _format_height_text(floor_plans: list[Any]) -> str:
    heights_mm = [
        float(getattr(floor_plan, "ceiling_height_mm", 0.0) or 0.0)
        for floor_plan in floor_plans
        if float(getattr(floor_plan, "ceiling_height_mm", 0.0) or 0.0) > 0
    ]
    if not heights_mm:
        return "3"
    heights_m = sorted(value / 1000.0 for value in heights_mm)
    if abs(heights_m[0] - heights_m[-1]) <= 1e-9:
        return _format_float(heights_m[0])
    return f"от {_format_float(heights_m[0])} до {_format_float(heights_m[-1])}"


def _resolve_project_system_type(floor_plans: list[Any]) -> str:
    for floor_plan in floor_plans:
        system_type = _normalize_text(getattr(floor_plan, "active_signal_system_type", ""))
        if system_type:
            return system_type
    return "non_addressable"


def _system_texts(system_type: str) -> dict[str, str]:
    if system_type == "addressable":
        return {
            "technology": "адресно-аналоговой",
            "topology": "адресная",
            "detectors": "адресные",
            "polling": "циклически опрашиваются",
        }
    return {
        "technology": "безадресной",
        "topology": "безадресная",
        "detectors": "безадресные",
        "polling": "опрашиваются по шлейфам",
    }


def _join_names(equipment_items: list[Any], *, fallback: str) -> str:
    names = [_normalize_text(getattr(item, "name", "")) for item in equipment_items if _normalize_text(getattr(item, "name", ""))]
    return ", ".join(names) if names else fallback


def _collect_resolved_equipment(project: Any, floor_plans: list[Any]) -> dict[str, list[Any]]:
    selection_map = _selection_map(project)
    instruments: list[Any] = []
    detectors: list[Any] = []
    soue_devices: list[Any] = []

    for floor_plan in floor_plans:
        for instrument in getattr(floor_plan, "signal_instruments", None) or []:
            equipment, _warning = _resolve_instrument_equipment(floor_plan, instrument, selection_map)
            if equipment is not None:
                instruments.append(equipment)
        for alarm in getattr(floor_plan, "fire_alarms", None) or []:
            equipment, _warning = _resolve_fire_alarm_equipment(floor_plan, alarm, selection_map)
            if equipment is not None:
                detectors.append(equipment)
        for device in getattr(floor_plan, "soue_devices", None) or []:
            equipment, _warning = _resolve_soue_equipment(floor_plan, device, selection_map)
            if equipment is not None:
                soue_devices.append(equipment)

    return {
        "instruments": _dedupe_sorted(instruments, category_order=DEVICE_CATEGORY_ORDER),
        "detectors": _dedupe_sorted(detectors, category_order=DETECTOR_CATEGORY_ORDER),
        "soue_devices": _dedupe_sorted(soue_devices, category_order=DEVICE_CATEGORY_ORDER),
    }


def _collect_selected_cables(project: Any) -> list[Any]:
    selection_map = _selection_map(project)
    cables = [
        selection_map.get("sps_cable"),
        selection_map.get("soue_cable"),
    ]
    return _dedupe_sorted([item for item in cables if item is not None])


def _main_panel_equipment(project: Any, resolved: dict[str, list[Any]]) -> Any | None:
    selection_map = _selection_map(project)
    preferred = selection_map.get("common_instrument")
    if preferred is not None:
        return preferred
    instruments = resolved.get("instruments") or []
    return instruments[0] if instruments else None


def _zkspc_zone_count(floor_plans: list[Any]) -> int:
    return sum(len(getattr(floor_plan, "zkspc_zones", None) or []) for floor_plan in floor_plans)


def _floor_count(project: Any, floor_plans: list[Any]) -> int:
    declared = int(getattr(project, "number_of_floors", 0) or 0)
    actual = len(floor_plans)
    return declared if declared > 0 else max(actual, 1)


def _facility_case(project: Any, attr: str) -> str:
    return _normalize_text(getattr(project, attr, None)) or _normalize_text(getattr(project, "facility", None)) or "объекта"


def _address_text(project: Any) -> str:
    return _normalize_text(getattr(project, "facility_address", None))


def build_project_general_instructions(project: Any, floor_plans: list[Any]) -> dict[str, Any]:
    resolved = _collect_resolved_equipment(project, floor_plans)
    cables = _collect_selected_cables(project)
    panel = _main_panel_equipment(project, resolved)

    facility = _normalize_text(getattr(project, "facility", None)) or "Объект"
    facility_genitive = _facility_case(project, "facility_genitive")
    facility_instrumental = _facility_case(project, "facility_instrumental")
    address = _address_text(project)
    floor_count = _floor_count(project, floor_plans)
    height_text = _format_height_text(floor_plans)
    zone_count = _zkspc_zone_count(floor_plans)
    system_type = _resolve_project_system_type(floor_plans)
    system_texts = _system_texts(system_type)

    manufacturer = _normalize_text(getattr(panel, "manufacturer", None)) or "неуказанного производителя"
    panel_name = _normalize_text(getattr(panel, "name", None)) or "ППКОП"

    all_equipment_items = (
        (resolved.get("instruments") or [])
        + (resolved.get("detectors") or [])
        + (resolved.get("soue_devices") or [])
    )
    all_equipment_items = _dedupe_sorted(all_equipment_items, category_order=DEVICE_CATEGORY_ORDER)

    manual_detectors = [
        item for item in (resolved.get("detectors") or [])
        if _normalize_text(getattr(item, "category", "")) == "manual"
    ]
    automatic_detectors = [
        item for item in (resolved.get("detectors") or [])
        if _normalize_text(getattr(item, "category", "")) in {"smoke", "heat", "linear"}
    ]
    exit_signs = [
        item for item in (resolved.get("soue_devices") or [])
        if _normalize_text(getattr(item, "category", "")) == "exit_sign"
    ]

    detector_list_text = _join_names(
        resolved.get("detectors") or [],
        fallback="пожарные извещатели, предусмотренные проектом",
    )
    manual_detector_text = _join_names(
        manual_detectors,
        fallback="предусмотренных проектом",
    )
    automatic_detector_text = _join_names(
        automatic_detectors,
        fallback="автоматических пожарных извещателей, предусмотренных проектом",
    )
    exit_sign_text = _join_names(
        exit_signs,
        fallback="«Выход»",
    )
    cable_text = _join_names(
        cables,
        fallback="кабельными изделиями, выбранными в проекте",
    )

    address_phrase = f" по адресу: {address}" if address else ""
    introduction_paragraph = (
        f"Рабочая документация по оснащению {facility_genitive}{address_phrase} системой противопожарной "
        "сигнализации (СПС) и системой оповещения и управления эвакуацией людей при пожаре (СОУЭ) "
        "разработана на основе технического задания и исходных данных, полученных от заказчика, "
        "выполнена в соответствии с требованиями действующих технических регламентов, стандартов, "
        "сводов правил и другими документами, содержащими установленные требования."
    )
    object_info_paragraph = (
        "Проектом предусматривается устройство системы пожарной сигнализации, системы оповещения и "
        f"управления эвакуацией людей при пожаре в {facility_instrumental}, "
        f"{'расположенного по адресу: ' + address if address else 'расположенного на объекте'}."
    )
    object_characteristics_paragraph = (
        f"{facility} имеет {floor_count} этаж(а/ей). Объект предназначен для круглогодичного использования. "
        "В соответствии с положениями ст. 32 Федерального закона от 22.07.2008 № 123-ФЗ «Технический регламент "
        f"о требованиях пожарной безопасности» объект относится к классу функциональной пожарной опасности зданий "
        f"{FIRE_HAZARD_CLASS_TEXT}. Степень огнестойкости – {FIRE_RESISTANCE_TEXT}. Класс конструктивной пожарной "
        f"опасности – {CONSTRUCTIVE_FIRE_HAZARD_TEXT}. Высота помещений {height_text} м. Пространства за "
        "фальшпотолками и между двойными полами отсутствуют."
    )
    technology_paragraph = (
        "Система автоматической пожарной сигнализации и система оповещения защищаемого объекта построены на "
        f"базе приборов {system_texts['technology']} системы производства {manufacturer}, которая обеспечивает:"
    )
    fire_alarm_paragraph = (
        "В соответствии с требованиями п. 4.4 СП 486.1311500.2020 все помещения здания подлежат защите "
        "системой пожарной сигнализаци, кроме: помещений с мокрыми процессами, душевых, плавательных "
        "бассейнов, санузлов, мойки; венткамер (за исключением вытяжных, обслуживающих производственные "
        "помещения категории А или Б), насосных водоснабжения, бойлерных, тепловых пунктов; категории В4 "
        "(за исключением помещений категории В4 в зданиях классов функциональной пожарной опасности Ф1.1, "
        "Ф1.2, Ф2.1, Ф4.1 и Ф4.2) и Д по пожарной опасности; лестничных клеток; тамбуров и тамбур-шлюзов; "
        "чердаков (за исключением чердаков в зданиях классов функциональной пожарной опасности Ф1.1, Ф1.2, "
        "Ф2.1, Ф4.1 и Ф4.2). Согласно требованиям СП 484.1311500.2020 п. 6.2 \"Выбор типов пожарных "
        f"извещателей\" действующего свода правил, для обнаружения возгораний выбраны {detector_list_text}."
    )
    fire_alarm_algorithm_paragraph = (
        "Принятие решение о возникновении пожара осуществляется по алгоритму А (см. п. 6.4.2 СП "
        f"484.1311500.2020.) от ручных пожарных извещателей {manual_detector_text}. Принятие решение о "
        "возникновении пожараосуществляется по алгоритму В (см. п. 6.4.3 СП 484.1311500.2020 п.6.6.1.) "
        f"от {automatic_detector_text}. При срабатывании в шлейфе одного извещателя происходит сброс "
        "состояния пожарных извещателей на 3 секунды. Если в течение 30-ти секунд не будет определено "
        f"повторного срабатывания, то ППКОП {panel_name} перейдет в режим «Норма», если будет определено "
        "повторное срабатывание извещателей в шлейфе, то в режим «Пожар». При срабатывании двух и более "
        f"дымовых извещателей, ППКОП {panel_name} также перейдет в режим «Пожар». При обрыве линий связи "
        f"или неполадках в функционировании ППКОП {panel_name} формирует сигнал «Неисправность»."
    )
    fire_alarm_network_paragraph = (
        f"Согласно п. 6.3.3. и п.6.3.4. СП 484.1311500.2020 весь объект поделен на {zone_count} ЗКСПС."
    )
    fire_alarm_topology_paragraph = (
        "В проекте выбрана "
        f"{system_texts['topology']} топология двухпроводной линии связи (ДПЛС). Подключенные по ДПЛС "
        f"{system_texts['detectors']} пожарные извещатели {system_texts['polling']} и отслеживаются на "
        f"предмет состояния ППКОП {panel_name}. На встроенных световых индикаторах контроллера "
        "отображается состояние самого прибора, обмена по ДПЛС и интерфейсу RS-485. ППКОП "
        f"{panel_name} размещены на высоте 1,5 м в пожарном шкафу ШПС-12 исп.10 - как фактор защиты "
        f"от несанкционированного доступа. ППКОП {panel_name} при отключении внешнего электропитания "
        "благодаря аккумуляторной батарее способны работать не менее 3 суток."
    )
    soue_intro_paragraph = (
        f"Согласно п. 14, табл. 2, СП 3.13130.2009 объект должен оснащаться СОУЭ {SOUE_TYPE_TEXT}. "
        "Система предназначена для оповещения работников о пожаре, управления эвакуацией с "
        "использованием звуковых оповещателей, передачи световых сигналов оповещателей «Выход»."
    )
    cable_paragraph = (
        "Тип кабельного изделия нг(A)-FRLS для прокладки в системе противопожарной защиты в здании "
        f"автостоянки выбран согласно требованиям ГОСТ 31565-2012, таблица 2. Шлейфы СПС и СОУЭ "
        f"выполнить {cable_text}. Рабочее напряжение трансляционной линии 100В допускает падение "
        "напряжения до 10В."
    )

    blocks: list[dict[str, Any]] = [
        {"kind": "section_heading", "text": "1. Введение"},
        {"kind": "paragraph", "text": introduction_paragraph},
        {"kind": "bullet_list", "items": list(INTRO_REFERENCE_BULLETS)},
        {
            "kind": "paragraph",
            "text": (
                "Данная документация допускается к производству работ после ее проверки и согласования "
                "с заказчиком. Все оборудование, заложенное в проекте на момент проектирования имеет "
                "сертификаты соответствия и СПБ, монтажная организация перед монтажом должна проверить "
                "срок действующих сертификатов."
            ),
        },
        {"kind": "section_heading", "text": "2. Сведения об объекте"},
        {"kind": "paragraph", "text": object_info_paragraph},
        {"kind": "paragraph", "text": object_characteristics_paragraph},
        {"kind": "section_heading", "text": "3. Основные технологические решения"},
        {"kind": "paragraph", "text": technology_paragraph},
        {"kind": "bullet_list", "items": list(TECHNOLOGY_BULLETS)},
        {"kind": "paragraph", "text": "В состав системы входят:"},
        {
            "kind": "bullet_list",
            "items": [
                _normalize_text(getattr(item, "name", ""))
                for item in all_equipment_items
                if _normalize_text(getattr(item, "name", ""))
            ] or ["Оборудование проекта не выбрано."],
        },
        {"kind": "section_heading", "text": "4. Система пожарной сигнализаци"},
        {"kind": "paragraph", "text": fire_alarm_paragraph},
        {"kind": "paragraph", "text": fire_alarm_algorithm_paragraph},
        {"kind": "paragraph", "text": fire_alarm_network_paragraph},
        {
            "kind": "paragraph",
            "text": (
                "Размещение пожарных извещателей на планах соответствует требованиям раздела 6.6. "
                "\"Размещение пожарных извещателей\" действующего свода правил."
            ),
        },
        {"kind": "paragraph", "text": fire_alarm_topology_paragraph},
        {
            "kind": "paragraph",
            "text": (
                "Извещатели пожарные установить согласно приведенным планам. Допускается менять "
                "расположение извещателей по месту согласно СП 484.1311500.2020 п.6.6.1 и п.6.6.5 "
                "Размещение дымовых и тепловых пожарных извещателей следует производить с учетом "
                "воздушных потолков в защищаемом помещении, вызываемых приточной и/или вытяжной "
                "вентиляцией, при этом расстояние между извещателем и вентиляционным отверстием должно "
                "быть не менее 1 м. Минимальное расстояние от дымовых и тепловых извещателей до "
                "выступающих на 0,25 м и менее от перекрытия строительных конструкций или инженерного "
                "оборудования должны составлять не менее двух высот этих строительных конструкций или "
                "оборудования. Расстояние от дымовых и тепловых извещателей до стен (перегородок), а "
                "также других строительных конструкций и до инженерного оборудования должно быть не "
                "менее 0,5 м."
            ),
        },
        {"kind": "section_heading", "text": "5. Система оповещения и управления эвакуацией."},
        {"kind": "paragraph", "text": soue_intro_paragraph},
        {"kind": "paragraph", "text": "В Систему входят:"},
        {
            "kind": "bullet_list",
            "items": [
                _normalize_text(getattr(item, "name", ""))
                for item in (resolved.get("soue_devices") or [])
                if _normalize_text(getattr(item, "name", ""))
            ] or ["Элементы СОУЭ в проекте не выбраны."],
        },
        {
            "kind": "paragraph",
            "text": (
                "В соответствии с требованиями п.4.4 свода правил звуковые оповещатели располагаются "
                "таким образом, чтобы их верхняя часть была на расстоянии не менее 2,3 м от уровня пола, "
                "и расстояние от потолка до верхней части оповещателя должно быть не менее 150 мм. В "
                "соответствии с требованиями п.4.1 свода правил звуковые оповещатели обеспечивают общий "
                "уровень звука не менее 75 дБ на расстоянии 3 м. При подключении оповещателей в линию "
                "необходимо соблюдать полярность, как минимум, в пределах одного помещения - во "
                "избежание асинхронного звучания. Суммарная номинальная потребляемая мощность речевых "
                "оповещателей всех подключенных линий оповещения не должна превышать 300 Вт. Блок "
                "оповещения установлен в Пожарном шкафу ШПС-12 исп.10. Световые оповещатели "
                f"{exit_sign_text} установлены согласно п.5.3 СП 3.13130 над эвакуационными выходами "
                "непосредственно наружу."
            ),
        },
        {"kind": "section_heading", "text": "6. Огнестойкая кабельная линия."},
        {"kind": "paragraph", "text": cable_paragraph},
        {
            "kind": "paragraph",
            "text": (
                "Кабели, прокладываемые в кабель-каналах должны иметь крепления к стенам, перекрытиям "
                "посредством металлических хомутов FR ПР с шагом 0.4 м. Радиус изгиба кабелей на "
                "поворотах трассы должен быть не менее 7,5-15 его диаметров в зависимости от "
                "применяемого кабеля (по информации производителя). В местах прохождения кабельных трасс "
                "через строительные конструкции необходимо предусмотреть кабельные проходки с пределом "
                "огнестойкости не ниже предела огнестойкости данных конструкций (в соответствии с "
                "требованием 123-ФЗ, ст. 82, п.7). Как правило, огнезащита мест прохода кабелей "
                "выполняется из металлической гильзы из стальной трубы на всю толщину стены и "
                "пластичного огнезащитного состава для герметизации."
            ),
        },
        {
            "kind": "paragraph",
            "text": (
                "Между зданиями Лит А и Лит Б и пунктом охраны на проходной проложить кабель «витая "
                "пара» ParLan U/UTP Cat5e PVC 4х2х0,52 (для внешней прокладки) вдоль стен зданий и на опорах."
            ),
        },
        {
            "kind": "paragraph",
            "text": (
                "При монтаже технических средств сигнализации и системы оповещения должны соблюдаться "
                "требования СНиП, ПУЭ, СП Системы противопожарной защиты, действующих государственных и "
                "отраслевых стандартов. Рабочая документация разработана соответствии с действующими "
                "нормами, правилами и стандартами."
            ),
        },
        {
            "kind": "paragraph",
            "text": "Защитное заземление выполнять в соответствии с ПУЭ и технической документацией на оборудование.",
        },
    ]

    for index, block in enumerate(blocks, start=1):
        block.setdefault("key", f"block_{index}")

    return {
        "project_id": getattr(project, "id", None),
        "page_title": GENERAL_INSTRUCTIONS_PAGE_TITLE,
        "heading": GENERAL_INSTRUCTIONS_HEADING,
        "local_sheet_title": GENERAL_INSTRUCTIONS_PAGE_TITLE,
        "blocks": blocks,
    }


def apply_general_instructions_overrides(payload: dict[str, Any], overrides: dict[str, Any] | None) -> dict[str, Any]:
    result = deepcopy(payload)
    if not isinstance(overrides, dict):
        return result

    for field_name in GENERAL_INSTRUCTIONS_EDITABLE_TOP_LEVEL_FIELDS:
        if isinstance(overrides.get(field_name), str):
            result[field_name] = _normalize_text(overrides[field_name])

    block_overrides = overrides.get("blocks") if isinstance(overrides.get("blocks"), dict) else {}
    for block in result.get("blocks") or []:
        block_override = block_overrides.get(block.get("key"))
        if not isinstance(block_override, dict):
            continue
        if block.get("kind") == "bullet_list":
            if isinstance(block_override.get("items"), list):
                block["items"] = _normalize_item_list(block_override.get("items"))
        elif "text" in block_override and block_override.get("text") is not None:
            block["text"] = _normalize_text(block_override.get("text"))

    return result


def extract_general_instructions_overrides(base_payload: dict[str, Any], updated_payload: dict[str, Any]) -> dict[str, Any]:
    overrides: dict[str, Any] = {}

    for field_name in GENERAL_INSTRUCTIONS_EDITABLE_TOP_LEVEL_FIELDS:
        if _normalize_text(updated_payload.get(field_name)) != _normalize_text(base_payload.get(field_name)):
            overrides[field_name] = _normalize_text(updated_payload.get(field_name))

    updated_blocks = {
        block.get("key"): block
        for block in (updated_payload.get("blocks") or [])
        if isinstance(block, dict) and block.get("key")
    }
    block_overrides: dict[str, dict[str, Any]] = {}
    for base_block in base_payload.get("blocks") or []:
        block_key = base_block.get("key")
        updated_block = updated_blocks.get(block_key)
        if not isinstance(updated_block, dict):
            continue
        if base_block.get("kind") == "bullet_list":
            base_items = _normalize_item_list(base_block.get("items"))
            updated_items = _normalize_item_list(updated_block.get("items"))
            if updated_items != base_items:
                block_overrides[block_key] = {"items": updated_items}
        elif _normalize_text(updated_block.get("text")) != _normalize_text(base_block.get("text")):
            block_overrides[block_key] = {"text": _normalize_text(updated_block.get("text"))}

    if block_overrides:
        overrides["blocks"] = block_overrides

    return overrides
