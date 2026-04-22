"""Pydantic schemas for the backend API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    """Base API model."""

    model_config = ConfigDict(from_attributes=True)


SignalSystemType = Literal["addressable", "non_addressable", "common"]
CableSubsystemType = Literal["sps", "soue"]
SoueDeviceType = Literal["siren", "exit_sign"]
WallAlignment = Literal["center", "left", "right"]
EquipmentCategory = Literal[
    "linear",
    "smoke",
    "heat",
    "manual",
    "siren",
    "exit_sign",
    "speech",
    "instrument",
    "keyboard",
    "cable",
    "battery",
    "mounting",
    "other",
]
SmokeAddressing = Literal["addressable", "non_addressable"]
ProjectEquipmentRole = Literal[
    "sps_linear_detector",
    "sps_smoke_detector",
    "sps_heat_detector",
    "sps_manual_call_point",
    "sps_cable",
    "soue_siren",
    "soue_exit_sign",
    "soue_speech_device",
    "soue_cable",
    "common_instrument",
    "common_keyboard",
    "common_other",
]


class ProjectCreate(APIModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "name": "АТМ.АГСВ для офисного здания",
                "project_type": "PS",
                "year": 2026,
                "contractor": "ООО «Подрядчик»",
                "engineer": "Иванов И.И.",
                "cpe": "Петров П.П.",
                "checker": "Сидоров С.С.",
                "facility": "Административное здание",
                "facility_genitive": "административного здания",
                "facility_instrumental": "административным зданием",
                "facility_address": "г. Москва, ул. Примерная, д. 1",
                "project_description": "Оснащение объекта системой пожарной сигнализации и СОУЭ.",
                "stage": "Р",
                "number_of_floors": 3,
            }
        },
    )

    name: str = Field(description="Внутреннее название проекта.")
    project_type: str = Field(default="PS", description="Марка или тип проекта.")
    year: int = Field(default_factory=lambda: datetime.now().year, description="Год выпуска проекта.")
    contractor: str = Field(description="Наименование подрядчика.")
    engineer: str = Field(description="Фамилия и инициалы инженера.")
    cpe: str = Field(description="Фамилия и инициалы ГИП / ответственного лица.")
    checker: str = Field(description="Фамилия и инициалы проверяющего.")
    facility: str = Field(description="Название объекта.")
    facility_genitive: str | None = Field(default=None, description="Название объекта в родительном падеже.")
    facility_instrumental: str | None = Field(default=None, description="Название объекта в творительном падеже.")
    facility_address: str | None = Field(default=None, description="Адрес объекта.")
    project_description: str | None = Field(default=None, description="Краткое описание проекта.")
    stage: str = Field(default="R", description="Стадия проектирования.")
    number_of_floors: int = Field(default=1, description="Количество этажей в проекте.")


class ProjectUpdate(APIModel):
    name: str | None = None
    project_type: str | None = None
    year: int | None = None
    contractor: str | None = None
    engineer: str | None = None
    cpe: str | None = None
    checker: str | None = None
    facility: str | None = None
    facility_genitive: str | None = None
    facility_instrumental: str | None = None
    facility_address: str | None = None
    project_description: str | None = None
    stage: str | None = None
    number_of_floors: int | None = None


class ProjectRead(APIModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 12,
                "name": "АТМ.АГСВ для офисного здания",
                "project_type": "PS",
                "number": 7,
                "year": 2026,
                "code": "АТМ-АГСВ-2026-007",
                "contractor": "ООО «Подрядчик»",
                "engineer": "Иванов И.И.",
                "cpe": "Петров П.П.",
                "checker": "Сидоров С.С.",
                "facility": "Административное здание",
                "facility_genitive": "административного здания",
                "facility_instrumental": "административным зданием",
                "facility_address": "г. Москва, ул. Примерная, д. 1",
                "project_description": "Оснащение объекта системой пожарной сигнализации и СОУЭ.",
                "stage": "«Р»",
                "number_of_floors": 3,
            }
        },
    )

    id: int
    name: str
    project_type: str
    number: int
    year: int
    code: str
    contractor: str
    engineer: str
    cpe: str
    checker: str
    facility: str
    facility_genitive: str | None = None
    facility_instrumental: str | None = None
    facility_address: str | None = None
    project_description: str | None = None
    stage: str
    number_of_floors: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EquipmentItemCreate(APIModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "name": "ДИП-34А",
                "category": "smoke",
                "description": "Адресный дымовой извещатель.",
                "price": 1350.0,
                "manufacturer": "Болид",
                "service_life_years": 10,
                "notes": "Используется в типовых кабинетах.",
                "specs": {
                    "smoke_addressing": "addressable",
                    "standby_current_a": 0.0005,
                    "alarm_current_a": 0.0008,
                },
                "smoke_addressing": "addressable",
                "compatible_equipment_ids": [],
            }
        },
    )

    name: str = Field(description="Название позиции оборудования.")
    category: EquipmentCategory = Field(description="Категория оборудования в каталоге.")
    description: str | None = Field(default=None, description="Текстовое описание позиции.")
    price: float | None = Field(default=None, description="Стоимость одной единицы оборудования.")
    manufacturer: str | None = Field(default=None, description="Производитель оборудования.")
    service_life_years: int | None = Field(default=None, description="Срок службы в годах.")
    notes: str | None = Field(default=None, description="Произвольные примечания.")
    specs: dict[str, Any] = Field(default_factory=dict, description="Нормализованные технические характеристики.")
    coverage_summary: str | None = Field(default=None, description="Краткая сводка по применению оборудования.")
    standby_current_ma: float | None = Field(default=None, description="Ток потребления в дежурном режиме, мА.")
    alarm_current_ma: float | None = Field(default=None, description="Ток потребления в режиме тревоги, мА.")
    smoke_addressing: SmokeAddressing | None = Field(default=None, description="Тип адресности дымового извещателя.")
    label_pdf_path: str | None = Field(default=None, description="Путь к PDF-карточке или ярлыку оборудования.")
    manual_pdf_path: str | None = Field(default=None, description="Путь к PDF-руководству пользователя.")
    compatible_equipment_ids: list[int] = Field(default_factory=list, description="Список совместимых позиций оборудования.")


class EquipmentItemUpdate(APIModel):
    name: str | None = None
    category: EquipmentCategory | None = None
    description: str | None = None
    price: float | None = None
    manufacturer: str | None = None
    service_life_years: int | None = None
    notes: str | None = None
    specs: dict[str, Any] | None = None
    coverage_summary: str | None = None
    standby_current_ma: float | None = None
    alarm_current_ma: float | None = None
    smoke_addressing: SmokeAddressing | None = None
    label_pdf_path: str | None = None
    manual_pdf_path: str | None = None
    compatible_equipment_ids: list[int] | None = None


class EquipmentItemRead(APIModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 25,
                "name": "ДИП-34А",
                "category": "smoke",
                "description": "Адресный дымовой извещатель.",
                "price": 1350.0,
                "manufacturer": "Болид",
                "service_life_years": 10,
                "notes": "Используется в типовых кабинетах.",
                "specs": {"standby_current_a": 0.0005, "alarm_current_a": 0.0008},
                "smoke_addressing": "addressable",
                "compatible_equipment_ids": [],
            }
        },
    )

    id: int
    name: str
    category: EquipmentCategory
    description: str | None = None
    price: float | None = None
    manufacturer: str | None = None
    service_life_years: int | None = None
    notes: str | None = None
    specs: dict[str, Any] = Field(default_factory=dict)
    coverage_summary: str | None = None
    standby_current_ma: float | None = None
    alarm_current_ma: float | None = None
    smoke_addressing: SmokeAddressing | None = None
    image_path: str | None = None
    label_pdf_path: str | None = None
    manual_pdf_path: str | None = None
    compatible_equipment_ids: list[int] = Field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProjectEquipmentAttach(APIModel):
    equipment_id: int


class ProjectEquipmentListRead(APIModel):
    project_id: int
    items: list[EquipmentItemRead] = Field(default_factory=list)


class ProjectEquipmentSelectionsUpdate(APIModel):
    selections: dict[str, int | None] = Field(default_factory=dict)


class ProjectEquipmentSelectionsRead(APIModel):
    project_id: int
    selections: dict[str, int | None] = Field(default_factory=dict)


class EquipmentSpecificationRowRead(APIModel):
    source_key: str
    position: str = ""
    technical_name: str = ""
    type_mark: str = ""
    code: str = ""
    manufacturer: str = ""
    unit: str = ""
    quantity: str = ""
    unit_mass_kg: str = ""
    note: str = ""


class EquipmentSpecificationSectionRead(APIModel):
    key: str
    title: str
    rows: list[EquipmentSpecificationRowRead] = Field(default_factory=list)


class EquipmentSpecificationRead(APIModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"example": {"project_id": 12, "page_title": "Спецификация оборудования и материалов", "column_headers": ["Поз.", "Наименование", "Тип", "Код", "Производитель", "Ед.", "Кол-во", "Масса", "Примечание"], "sections": [], "warnings": []}},
    )

    project_id: int
    page_title: str
    column_headers: list[str] = Field(default_factory=list, min_length=9, max_length=9)
    sections: list[EquipmentSpecificationSectionRead] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class EquipmentSpecificationRowUpdate(APIModel):
    source_key: str
    position: str = ""
    technical_name: str = ""
    type_mark: str = ""
    code: str = ""
    manufacturer: str = ""
    unit: str = ""
    quantity: str = ""
    unit_mass_kg: str = ""
    note: str = ""


class EquipmentSpecificationSectionUpdate(APIModel):
    key: str
    title: str
    rows: list[EquipmentSpecificationRowUpdate] = Field(default_factory=list)


class EquipmentSpecificationUpdate(APIModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"example": {"page_title": "Спецификация оборудования и материалов", "column_headers": ["Поз.", "Наименование", "Тип", "Код", "Производитель", "Ед.", "Кол-во", "Масса", "Примечание"], "sections": []}},
    )

    page_title: str
    column_headers: list[str] = Field(default_factory=list, min_length=9, max_length=9)
    sections: list[EquipmentSpecificationSectionUpdate] = Field(default_factory=list)


class PowerConsumptionCalculationRowRead(APIModel):
    source_key: str
    number: str = ""
    equipment_name: str = ""
    unit: str = ""
    quantity: str = ""
    standby_current: str = ""
    alarm_current: str = ""
    standby_total: str = ""
    alarm_total: str = ""


class PowerConsumptionCalculationCategoryRead(APIModel):
    key: str
    title: str
    rows: list[PowerConsumptionCalculationRowRead] = Field(default_factory=list)


class PowerConsumptionCalculationSummaryRowRead(APIModel):
    key: str
    kind: str
    label: str
    standby: str | None = None
    alarm: str | None = None
    value: str | None = None


class PowerConsumptionCalculationRead(APIModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "project_id": 12,
                "page_title": "Расчет токопотребления системы",
                "introductory_texts": ["Вводный абзац 1.", "Вводный абзац 2."],
                "table_caption": "Таблица 1.",
                "table_title": "Расчет токопотребления системы",
                "categories": [],
                "summary_rows": [],
                "battery_voltage_v": 12,
                "battery_capacity_ah": 8,
                "battery_quantity": 1,
                "final_text": "Исходя из расчетов принимаем использование аккумуляторной батареи 12 В, 8 Ач - 1 шт.",
                "computed_values": {"total_capacity": 7.2},
            }
        },
    )

    project_id: int
    page_title: str
    introductory_texts: list[str] = Field(default_factory=list)
    table_caption: str
    table_title: str
    categories: list[PowerConsumptionCalculationCategoryRead] = Field(default_factory=list)
    summary_rows: list[PowerConsumptionCalculationSummaryRowRead] = Field(default_factory=list)
    battery_voltage_v: str | int | float
    battery_capacity_ah: int
    battery_quantity: str | int | float
    final_text: str
    computed_values: dict[str, float | int] = Field(default_factory=dict)


class PowerConsumptionCalculationRowUpdate(APIModel):
    source_key: str
    number: str = ""
    equipment_name: str = ""
    unit: str = ""
    quantity: str = ""
    standby_current: str = ""
    alarm_current: str = ""


class PowerConsumptionCalculationCategoryUpdate(APIModel):
    key: str
    title: str
    rows: list[PowerConsumptionCalculationRowUpdate] = Field(default_factory=list)


class PowerConsumptionCalculationSummaryRowUpdate(APIModel):
    key: str
    label: str
    standby: str | None = None
    alarm: str | None = None


class PowerConsumptionCalculationUpdate(APIModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "page_title": "Расчет токопотребления системы",
                "introductory_texts": ["Вводный абзац 1.", "Вводный абзац 2."],
                "table_caption": "Таблица 1.",
                "table_title": "Расчет токопотребления системы",
                "categories": [],
                "summary_rows": [],
                "battery_voltage_v": 12,
                "battery_quantity": 1,
            }
        },
    )

    page_title: str
    introductory_texts: list[str] = Field(default_factory=list)
    table_caption: str
    table_title: str
    categories: list[PowerConsumptionCalculationCategoryUpdate] = Field(default_factory=list)
    summary_rows: list[PowerConsumptionCalculationSummaryRowUpdate] = Field(default_factory=list)
    battery_voltage_v: str | int | float
    battery_quantity: str | int | float


class GeneralInstructionsBlockRead(APIModel):
    key: str
    kind: str
    text: str | None = None
    items: list[str] = Field(default_factory=list)


class GeneralInstructionsRead(APIModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "project_id": 12,
                "page_title": "Общие указания",
                "heading": "ОБЩИЕ УКАЗАНИЯ.",
                "local_sheet_title": "Общие указания",
                "blocks": [{"key": "intro", "kind": "paragraph", "text": "Рабочая документация разработана в соответствии с нормативными требованиями.", "items": []}],
            }
        },
    )

    project_id: int | None = None
    page_title: str
    heading: str
    local_sheet_title: str
    blocks: list[GeneralInstructionsBlockRead] = Field(default_factory=list)


class GeneralInstructionsBlockUpdate(APIModel):
    key: str
    kind: str
    text: str | None = None
    items: list[str] = Field(default_factory=list)


class GeneralInstructionsUpdate(APIModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "page_title": "Общие указания",
                "heading": "ОБЩИЕ УКАЗАНИЯ.",
                "local_sheet_title": "Общие указания",
                "blocks": [{"key": "intro", "kind": "paragraph", "text": "Рабочая документация разработана в соответствии с нормативными требованиями.", "items": []}],
            }
        },
    )

    page_title: str
    heading: str
    local_sheet_title: str
    blocks: list[GeneralInstructionsBlockUpdate] = Field(default_factory=list)


class GeneralDataDocumentRowRead(APIModel):
    key: str
    designation: str = ""
    name: str = ""
    note: str = ""


class GeneralDataManifestRowRead(APIModel):
    key: str
    name: str = ""
    sheet_count: int = 0
    note: str = ""


class GeneralDataRead(APIModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "project_id": 12,
                "page_title": "Общие данные",
                "left_table_title": "ВЕДОМОСТЬ ССЫЛОЧНЫХ И ПРИЛАГАЕМЫХ ДОКУМЕНТОВ",
                "right_table_title": "ВЕДОМОСТЬ РАБОЧИХ ЧЕРТЕЖЕЙ ОСНОВНОГО КОМПЛЕКТА",
                "reference_category_title": "Ссылочные документы",
                "attached_category_title": "Прилагаемые документы",
                "reference_documents": [],
                "attached_documents": [],
                "drawing_manifest_rows": [],
                "statement_text": "Технические решения соответствуют действующим нормам.",
                "gip_name": "Петров П.П.",
            }
        },
    )

    project_id: int | None = None
    page_title: str
    left_table_title: str
    right_table_title: str
    reference_category_title: str
    attached_category_title: str
    reference_documents: list[GeneralDataDocumentRowRead] = Field(default_factory=list)
    attached_documents: list[GeneralDataDocumentRowRead] = Field(default_factory=list)
    drawing_manifest_rows: list[GeneralDataManifestRowRead] = Field(default_factory=list)
    statement_text: str = ""
    gip_name: str = ""


class GeneralDataDocumentRowUpdate(APIModel):
    key: str
    designation: str = ""
    name: str = ""
    note: str = ""


class GeneralDataManifestRowUpdate(APIModel):
    key: str
    name: str = ""
    sheet_count: int = 0
    note: str = ""


class GeneralDataUpdate(APIModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "page_title": "Общие данные",
                "left_table_title": "ВЕДОМОСТЬ ССЫЛОЧНЫХ И ПРИЛАГАЕМЫХ ДОКУМЕНТОВ",
                "right_table_title": "ВЕДОМОСТЬ РАБОЧИХ ЧЕРТЕЖЕЙ ОСНОВНОГО КОМПЛЕКТА",
                "reference_category_title": "Ссылочные документы",
                "attached_category_title": "Прилагаемые документы",
                "reference_documents": [],
                "attached_documents": [],
                "drawing_manifest_rows": [],
                "statement_text": "Технические решения соответствуют действующим нормам.",
                "gip_name": "Петров П.П.",
            }
        },
    )

    page_title: str
    left_table_title: str
    right_table_title: str
    reference_category_title: str
    attached_category_title: str
    reference_documents: list[GeneralDataDocumentRowUpdate] = Field(default_factory=list)
    attached_documents: list[GeneralDataDocumentRowUpdate] = Field(default_factory=list)
    drawing_manifest_rows: list[GeneralDataManifestRowUpdate] = Field(default_factory=list)
    statement_text: str = ""
    gip_name: str = ""


class AdditionalInfoRead(APIModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"example": {"page_title": "Доп. сведения", "text": "Дополнительная информация по проекту.", "is_empty": False}},
    )

    page_title: str
    text: str = ""
    is_empty: bool = True


class AdditionalInfoUpdate(APIModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={"example": {"text": "Дополнительная информация по проекту."}},
    )

    text: str = ""


class WallCreate(APIModel):
    floor_plan_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float = 200.0
    alignment: WallAlignment = "center"
    is_load_bearing: bool = False
    material: str | None = None
    length_m: float | None = None
    length_source: Literal["ocr", "manual", "derived"] | None = None


class WallUpdate(APIModel):
    floor_plan_id: int | None = None
    x1: float | None = None
    y1: float | None = None
    x2: float | None = None
    y2: float | None = None
    thickness: float | None = None
    alignment: WallAlignment | None = None
    is_load_bearing: bool | None = None
    material: str | None = None
    length_m: float | None = None
    length_source: Literal["ocr", "manual", "derived"] | None = None


class WallRead(APIModel):
    id: int
    floor_plan_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float
    alignment: WallAlignment = "center"
    is_load_bearing: bool
    material: str | None = None
    length_m: float | None = None
    length_source: str | None = None


class DoorCreate(APIModel):
    floor_plan_id: int
    x: float
    y: float
    width: float
    height: float
    wall_id: int | None = None
    rotation_deg: float = 0.0
    door_type: str = "standard"
    swing_angle: float = 90.0
    swing_direction: str | None = None
    is_evacuation_exit: bool | None = None


class DoorUpdate(APIModel):
    floor_plan_id: int | None = None
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    wall_id: int | None = None
    rotation_deg: float | None = None
    door_type: str | None = None
    swing_angle: float | None = None
    swing_direction: str | None = None
    is_evacuation_exit: bool | None = None


class DoorRead(APIModel):
    id: int
    floor_plan_id: int
    x: float
    y: float
    width: float
    height: float
    wall_id: int | None = None
    rotation_deg: float = 0.0
    door_type: str
    swing_angle: float
    swing_direction: str | None = None
    is_evacuation_exit: bool = False


class WindowCreate(APIModel):
    floor_plan_id: int
    x: float
    y: float
    width: float
    height: float
    wall_id: int | None = None
    rotation_deg: float = 0.0
    window_type: str = "standard"


class WindowUpdate(APIModel):
    floor_plan_id: int | None = None
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    wall_id: int | None = None
    rotation_deg: float | None = None
    window_type: str | None = None


class WindowRead(APIModel):
    id: int
    floor_plan_id: int
    x: float
    y: float
    width: float
    height: float
    wall_id: int | None = None
    rotation_deg: float = 0.0
    window_type: str


class RoomCreate(APIModel):
    floor_plan_id: int
    name: str | None = None
    room_type: str | None = None
    room_number: str | None = None
    max_occupancy: int | None = None
    boundary_points: list[list[float]] | None = None
    length_m: float | None = None
    width_m: float | None = None


class RoomUpdate(APIModel):
    floor_plan_id: int | None = None
    name: str | None = None
    room_type: str | None = None
    room_number: str | None = None
    max_occupancy: int | None = None
    boundary_points: list[list[float]] | None = None
    length_m: float | None = None
    width_m: float | None = None


class RoomRead(APIModel):
    id: int
    floor_plan_id: int
    name: str | None = None
    room_type: str | None = None
    room_number: str | None = None
    max_occupancy: int | None = None
    boundary_points: list[list[float]] | None = None
    area_sqm: float | None = None
    perimeter_m: float | None = None
    length_m: float | None = None
    width_m: float | None = None
    center_x: float | None = None
    center_y: float | None = None


class DimensionCreate(APIModel):
    floor_plan_id: int
    x: float
    y: float
    value: float
    unit: str = "m"
    text: str | None = None
    wall_id: int | None = None
    room_id: int | None = None
    line_x1: float | None = None
    line_y1: float | None = None
    line_x2: float | None = None
    line_y2: float | None = None
    dimension_type: str = "linear"


class DimensionRead(APIModel):
    id: int
    floor_plan_id: int
    x: float
    y: float
    value: float
    unit: str
    text: str | None = None
    wall_id: int | None = None
    room_id: int | None = None
    line_x1: float | None = None
    line_y1: float | None = None
    line_x2: float | None = None
    line_y2: float | None = None
    dimension_type: str


class FireAlarmCreate(APIModel):
    floor_plan_id: int
    x: float
    y: float
    device_type: str
    device_model: str | None = None
    coverage_radius: float | None = None
    mounting_height: float | None = None
    system_type: SignalSystemType = "non_addressable"
    equipment_id: int | None = None
    zkspc_zone_id: int | None = None
    loop_kind: str | None = None
    loop_number: int | None = None
    device_number: int | None = None
    zone: str | None = None
    address: str | None = None
    room_id: int | None = None
    offset_left_m: float | None = None
    offset_top_m: float | None = None
    label_dx: float | None = None
    label_dy: float | None = None


class FireAlarmUpdate(APIModel):
    floor_plan_id: int | None = None
    x: float | None = None
    y: float | None = None
    device_type: str | None = None
    device_model: str | None = None
    coverage_radius: float | None = None
    mounting_height: float | None = None
    system_type: SignalSystemType | None = None
    equipment_id: int | None = None
    zkspc_zone_id: int | None = None
    loop_kind: str | None = None
    loop_number: int | None = None
    device_number: int | None = None
    zone: str | None = None
    address: str | None = None
    room_id: int | None = None
    offset_left_m: float | None = None
    offset_top_m: float | None = None
    label_dx: float | None = None
    label_dy: float | None = None


class FireAlarmRead(APIModel):
    id: int
    floor_plan_id: int
    x: float
    y: float
    device_type: str
    device_model: str | None = None
    coverage_radius: float | None = None
    mounting_height: float | None = None
    system_type: SignalSystemType = "non_addressable"
    equipment_id: int | None = None
    zkspc_zone_id: int | None = None
    loop_kind: str | None = None
    loop_number: int | None = None
    device_number: int | None = None
    zone: str | None = None
    address: str | None = None
    room_id: int | None = None
    offset_left_m: float | None = None
    offset_top_m: float | None = None
    label_dx: float | None = None
    label_dy: float | None = None


class FireAlarmAutoLayoutDeviceRead(APIModel):
    x: float
    y: float
    device_type: str
    device_model: str | None = None
    coverage_radius: float | None = None
    mounting_height: float | None = None
    system_type: SignalSystemType = "non_addressable"
    equipment_id: int | None = None
    zkspc_zone_id: int | None = None
    loop_kind: str | None = None
    loop_number: int | None = None
    device_number: int | None = None
    zone: str | None = None
    address: str | None = None
    room_id: int | None = None
    offset_left_m: float | None = None
    offset_top_m: float | None = None
    label_dx: float | None = None
    label_dy: float | None = None


class FireAlarmAutoLayoutRead(APIModel):
    devices: list[FireAlarmAutoLayoutDeviceRead] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class SoueDeviceCreate(APIModel):
    floor_plan_id: int
    x: float
    y: float
    device_type: SoueDeviceType
    device_model: str | None = None
    sound_pressure_db: float | None = None
    mounting_height: float | None = None
    system_type: SignalSystemType = "non_addressable"
    equipment_id: int | None = None
    loop_kind: str | None = None
    loop_number: int | None = None
    device_number: int | None = None
    room_id: int | None = None
    offset_left_m: float | None = None
    offset_top_m: float | None = None
    label_dx: float | None = None
    label_dy: float | None = None


class SoueDeviceUpdate(APIModel):
    floor_plan_id: int | None = None
    x: float | None = None
    y: float | None = None
    device_type: SoueDeviceType | None = None
    device_model: str | None = None
    sound_pressure_db: float | None = None
    mounting_height: float | None = None
    system_type: SignalSystemType | None = None
    equipment_id: int | None = None
    loop_kind: str | None = None
    loop_number: int | None = None
    device_number: int | None = None
    room_id: int | None = None
    offset_left_m: float | None = None
    offset_top_m: float | None = None
    label_dx: float | None = None
    label_dy: float | None = None


class SoueDeviceRead(APIModel):
    id: int
    floor_plan_id: int
    x: float
    y: float
    device_type: SoueDeviceType
    device_model: str | None = None
    sound_pressure_db: float | None = None
    mounting_height: float | None = None
    system_type: SignalSystemType = "non_addressable"
    equipment_id: int | None = None
    loop_kind: str | None = None
    loop_number: int | None = None
    device_number: int | None = None
    room_id: int | None = None
    offset_left_m: float | None = None
    offset_top_m: float | None = None
    label_dx: float | None = None
    label_dy: float | None = None


class SoueDeviceAutoLayoutDeviceRead(APIModel):
    x: float
    y: float
    device_type: SoueDeviceType
    device_model: str | None = None
    sound_pressure_db: float | None = None
    mounting_height: float | None = None
    system_type: SignalSystemType = "non_addressable"
    equipment_id: int | None = None
    loop_kind: str | None = None
    loop_number: int | None = None
    device_number: int | None = None
    room_id: int | None = None
    offset_left_m: float | None = None
    offset_top_m: float | None = None
    label_dx: float | None = None
    label_dy: float | None = None


class SoueDeviceAutoLayoutRead(APIModel):
    devices: list[SoueDeviceAutoLayoutDeviceRead] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class FloorPlanCreate(APIModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "project_id": 12,
                "floor_number": 1,
                "name": "1 этаж",
                "scale_factor": 10.0,
                "ceiling_height_mm": 3000.0,
                "active_signal_system_type": "non_addressable",
            }
        },
    )

    project_id: int = Field(description="Идентификатор проекта, к которому относится новый план.")
    floor_number: int = Field(description="Номер этажа внутри проекта.")
    name: str | None = Field(default=None, description="Пользовательское название плана этажа.")
    scale_factor: float = Field(default=1.0, description="Масштаб плана в миллиметрах на пиксель.")
    ceiling_height_mm: float = Field(default=3000.0, description="Высота помещений на этаже, мм.")
    active_signal_system_type: SignalSystemType = Field(
        default="non_addressable",
        description="Активная ветка сигнальной системы для этапов редактора.",
    )


class FloorPlanUpdate(APIModel):
    floor_number: int | None = None
    name: str | None = None
    scale_factor: float | None = None
    ceiling_height_mm: float | None = None
    active_signal_system_type: SignalSystemType | None = None


class StairCreate(APIModel):
    floor_plan_id: int
    x: float
    y: float
    width: float
    height: float
    rotation_deg: float = 0.0
    step_count: int = 5
    step_axis: Literal["horizontal", "vertical"] | None = None


class StairUpdate(APIModel):
    floor_plan_id: int | None = None
    x: float | None = None
    y: float | None = None
    width: float | None = None
    height: float | None = None
    rotation_deg: float | None = None
    step_count: int | None = None
    step_axis: Literal["horizontal", "vertical"] | None = None


class StairRead(APIModel):
    id: int
    floor_plan_id: int
    x: float
    y: float
    width: float
    height: float
    rotation_deg: float = 0.0
    step_count: int
    step_axis: Literal["horizontal", "vertical"]


class ZkspcZoneRead(APIModel):
    id: int
    floor_plan_id: int
    zone_number: int
    name: str | None = None
    area_sqm: float | None = None
    room_count: int
    room_ids: list[int] = Field(default_factory=list)
    is_manual: bool = False
    is_locked: bool = False
    compliance_warnings: list[str] = Field(default_factory=list)


class ZkspcZoneCommit(APIModel):
    id: int | None = None
    zone_number: int | None = None
    name: str | None = None
    room_ids: list[int] = Field(default_factory=list)
    is_manual: bool = True
    is_locked: bool = False


class SignalInstrumentCreate(APIModel):
    floor_plan_id: int
    system_type: SignalSystemType = "non_addressable"
    instrument_type: Literal["control_panel", "loop_controller", "annunciator"] = "control_panel"
    equipment_id: int | None = None
    x: float
    y: float
    name: str | None = None
    supports_cable_merge: bool | None = None
    label_dx: float | None = None
    label_dy: float | None = None


class SignalInstrumentUpdate(APIModel):
    floor_plan_id: int | None = None
    system_type: SignalSystemType | None = None
    instrument_type: Literal["control_panel", "loop_controller", "annunciator"] | None = None
    equipment_id: int | None = None
    x: float | None = None
    y: float | None = None
    name: str | None = None
    supports_cable_merge: bool | None = None
    label_dx: float | None = None
    label_dy: float | None = None


class SignalInstrumentRead(APIModel):
    id: int
    floor_plan_id: int
    system_type: SignalSystemType
    instrument_type: Literal["control_panel", "loop_controller", "annunciator"]
    equipment_id: int | None = None
    x: float
    y: float
    name: str | None = None
    supports_cable_merge: bool
    label_dx: float | None = None
    label_dy: float | None = None


class CableRouteRead(APIModel):
    id: int
    floor_plan_id: int
    system_type: SignalSystemType
    subsystem_type: CableSubsystemType = "sps"
    instrument_id: int
    route_kind: str
    route_number: int
    polyline_points: list[list[float]] = Field(default_factory=list)
    device_ids: list[int] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    length_m: float | None = None
    is_manual: bool = False
    zc_label_dx: float | None = None
    zc_label_dy: float | None = None


class CableRouteUpdate(APIModel):
    polyline_points: list[list[float]] = Field(default_factory=list)
    is_manual: bool = True
    zc_label_dx: float | None = None
    zc_label_dy: float | None = None


class InstrumentCableMergeRequest(APIModel):
    device_ids: list[int] = Field(default_factory=list)
    subsystem_type: CableSubsystemType = "sps"
    system_type: SignalSystemType | None = None


class CableRoutesRecalculateRequest(APIModel):
    system_type: SignalSystemType
    subsystem_type: CableSubsystemType = "sps"
    use_shared_trunk: bool = False


class SignalBranchStepCommitRequest(APIModel):
    system_type: SignalSystemType = "non_addressable"


class FloorPlanRead(APIModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 31,
                "project_id": 12,
                "floor_number": 1,
                "name": "1 этаж",
                "scale_factor": 10.0,
                "ceiling_height_mm": 3000.0,
                "active_signal_system_type": "non_addressable",
                "walls": [],
                "stairs": [],
                "doors": [],
                "windows": [],
                "rooms": [],
                "dimensions": [],
                "fire_alarms": [],
                "soue_devices": [],
                "zkspc_zones": [],
                "signal_instruments": [],
                "cable_routes": [],
            }
        },
    )

    id: int
    project_id: int
    floor_number: int
    name: str | None = None
    original_image_path: str | None = None
    processed_image_path: str | None = None
    image_width: int | None = None
    image_height: int | None = None
    scale_factor: float
    ceiling_height_mm: float = 3000.0
    active_signal_system_type: SignalSystemType = "non_addressable"
    pipeline_state: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    walls: list[WallRead] = Field(default_factory=list)
    stairs: list[StairRead] = Field(default_factory=list)
    doors: list[DoorRead] = Field(default_factory=list)
    windows: list[WindowRead] = Field(default_factory=list)
    rooms: list[RoomRead] = Field(default_factory=list)
    dimensions: list[DimensionRead] = Field(default_factory=list)
    fire_alarms: list[FireAlarmRead] = Field(default_factory=list)
    soue_devices: list[SoueDeviceRead] = Field(default_factory=list)
    zkspc_zones: list[ZkspcZoneRead] = Field(default_factory=list)
    signal_instruments: list[SignalInstrumentRead] = Field(default_factory=list)
    cable_routes: list[CableRouteRead] = Field(default_factory=list)


class RecognitionProcessRead(APIModel):
    message: str
    walls_detected: int
    doors_detected: int
    windows_detected: int
    rooms_detected: int
    dimensions_detected: int
    recognition_id: int


class DebugImageRead(APIModel):
    step: str
    path: str


class RecognitionRead(APIModel):
    id: int | None = None
    floor_plan_id: int | None = None
    status: str
    recognition_result: dict[str, Any] | None = None
    error_message: str | None = None
    processed_at: datetime | None = None
    debug_artifacts_dir: str | None = None
    debug_images: list[DebugImageRead] = Field(default_factory=list)


class RecognitionFeedbackRead(APIModel):
    id: int
    recognition_id: int
    status: str
    submitted_at: datetime | None = None
    exported_at: datetime | None = None


class RecognitionTrainingBatchRead(APIModel):
    batch_id: str
    step: str
    status: str
    export_dir: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    exported_at: datetime | None = None


class RecognitionFeedbackPendingCountsRead(APIModel):
    approved: int = 0
    batched: int = 0
    exported: int = 0
    used: int = 0
    total: int = 0


class RecognitionBatchThresholdsRead(APIModel):
    approved_examples: int | None = None
    minimum_hard_examples: int | None = None
    minimum_labeled_openings: int | None = None
    max_idle_days: int = 14
    minimum_real_correction_ratio: float = 0.2


class RecognitionBatchHintRead(APIModel):
    step: str
    eligible: bool = False
    reason: str = "not_ready"
    approved_examples: int = 0
    selected_examples: int = 0
    real_correction_examples: int = 0
    hard_examples: int = 0
    pending_examples: int = 0
    labeled_openings: int = 0
    has_door_examples: bool = False
    has_window_examples: bool = False
    last_batch_id: str | None = None


class RecognitionFeedbackStepStatsRead(APIModel):
    step: str
    detector_version: str
    pending_counts: RecognitionFeedbackPendingCountsRead
    thresholds: RecognitionBatchThresholdsRead
    next_batch_hint: RecognitionBatchHintRead
    last_batch: RecognitionTrainingBatchRead | None = None


class RecognitionFeedbackStatsRead(APIModel):
    detector_version: str
    steps: list[RecognitionFeedbackStepStatsRead] = Field(default_factory=list)


class RecognitionTrainingDefaultsRead(APIModel):
    model: str
    epochs: int
    imgsz: int
    batch: int
    patience: int
    device: str


class RecognitionTrainingArtifactsRead(APIModel):
    best_checkpoint_path: str | None = None
    last_checkpoint_path: str | None = None
    metrics_json_path: str | None = None
    params_json_path: str | None = None
    has_best_checkpoint: bool = False
    has_last_checkpoint: bool = False


class RecognitionActiveModelRead(APIModel):
    step: Literal["walls", "openings"]
    training_run_id: int
    run_id: str | None = None
    artifact_path: str
    activated_at: datetime | None = None
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    metrics_summary: dict[str, Any] = Field(default_factory=dict)


class RecognitionTrainingRunRead(APIModel):
    run_id: str
    step: Literal["walls", "openings"]
    status: str
    config: dict[str, Any] = Field(default_factory=dict)
    metrics_summary: dict[str, Any] = Field(default_factory=dict)
    artifacts: RecognitionTrainingArtifactsRead = Field(default_factory=RecognitionTrainingArtifactsRead)
    is_active_for_step: bool = False
    artifact_dir: str | None = None
    log_path: str | None = None
    error_message: str | None = None
    requested_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    batch: RecognitionTrainingBatchRead | None = None


class RecognitionTrainingOverviewStepRead(APIModel):
    step: Literal["walls", "openings"]
    detector_version: str
    approved_examples: int = 0
    excluded_examples: int = 0
    selected_for_batch: int = 0
    recommended_batch_size: int = 0
    thresholds: RecognitionBatchThresholdsRead
    next_batch_hint: RecognitionBatchHintRead
    last_batch: RecognitionTrainingBatchRead | None = None
    last_successful_run: RecognitionTrainingRunRead | None = None
    active_model: RecognitionActiveModelRead | None = None
    training_defaults: RecognitionTrainingDefaultsRead


class RecognitionTrainingOverviewRead(APIModel):
    detector_version: str
    steps: list[RecognitionTrainingOverviewStepRead] = Field(default_factory=list)


class RecognitionTrainingExampleSummaryRead(APIModel):
    id: int
    step: Literal["walls", "openings"]
    floor_plan_id: int
    floor_plan_name: str | None = None
    floor_number: int | None = None
    project_id: int | None = None
    project_name: str | None = None
    project_code: str | None = None
    submitted_at: datetime | None = None
    hardness_score: float = 0.0
    changed: bool = False
    issue_tags: list[str] = Field(default_factory=list)
    notes: str | None = None
    curation_status: Literal["approved", "excluded"] = "approved"
    times_used: int = 0


class RecognitionTrainingExampleBatchRead(RecognitionTrainingBatchRead):
    included_at: datetime | None = None


class RecognitionTrainingExampleDetailRead(RecognitionTrainingExampleSummaryRead):
    step_revision: int
    detector_version: str
    source_snapshot: dict[str, Any] = Field(default_factory=dict)
    corrected_snapshot: dict[str, Any] = Field(default_factory=dict)
    diff_summary: dict[str, Any] = Field(default_factory=dict)
    original_image_path: str | None = None
    batches: list[RecognitionTrainingExampleBatchRead] = Field(default_factory=list)
    runs: list[RecognitionTrainingRunRead] = Field(default_factory=list)


class RecognitionTrainingExampleUpdate(APIModel):
    curation_status: Literal["approved", "excluded"] | None = None
    issue_tags: list[str] | None = None
    notes: str | None = None


class RecognitionTrainingBulkCurateRequest(APIModel):
    example_ids: list[int] = Field(default_factory=list)
    curation_status: Literal["approved", "excluded"]


class RecognitionTrainingBulkCurateRead(APIModel):
    updated_count: int
    curation_status: Literal["approved", "excluded"]


class RecognitionTrainingRunCreateRequest(APIModel):
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "step": "walls",
                "epochs": 100,
                "imgsz": 1024,
                "batch": 8,
                "patience": 20,
                "force": False,
            }
        },
    )

    step: Literal["walls", "openings"] = Field(description="Этап распознавания, для которого запускается обучение.")
    epochs: int | None = Field(default=None, description="Количество эпох обучения.")
    imgsz: int | None = Field(default=None, description="Размер входного изображения для обучения.")
    batch: int | None = Field(default=None, description="Batch size для обучения.")
    patience: int | None = Field(default=None, description="Количество эпох без улучшения до ранней остановки.")
    force: bool = Field(default=False, description="Разрешить запуск даже если рекомендация по данным не выполнена.")


class RecognitionTrainingRunLogRead(APIModel):
    run_id: str
    log_path: str | None = None
    content: str = ""


class HealthRead(APIModel):
    status: str
    message: str


class MessageRead(APIModel):
    message: str


class FeedbackCreate(APIModel):
    objects: list[Any]


ElementType = Literal["walls", "stairs", "doors", "windows", "fire-alarms", "soue-devices", "rooms", "dimensions"]


class DeleteElementCommand(APIModel):
    element_type: ElementType
    id: int


class WallUpdateCommand(APIModel):
    id: int
    data: WallUpdate


class DoorUpdateCommand(APIModel):
    id: int
    data: DoorUpdate


class WindowUpdateCommand(APIModel):
    id: int
    data: WindowUpdate


class StairUpdateCommand(APIModel):
    id: int
    data: StairUpdate


class FireAlarmUpdateCommand(APIModel):
    id: int
    data: FireAlarmUpdate


class SoueDeviceUpdateCommand(APIModel):
    id: int
    data: SoueDeviceUpdate


class RoomUpdateCommand(APIModel):
    id: int
    data: RoomUpdate


class BatchSaveRequest(APIModel):
    deleted: list[DeleteElementCommand] = Field(default_factory=list)
    create_walls: list[WallCreate] = Field(default_factory=list)
    create_stairs: list[StairCreate] = Field(default_factory=list)
    create_doors: list[DoorCreate] = Field(default_factory=list)
    create_windows: list[WindowCreate] = Field(default_factory=list)
    create_fire_alarms: list[FireAlarmCreate] = Field(default_factory=list)
    create_soue_devices: list[SoueDeviceCreate] = Field(default_factory=list)
    update_walls: list[WallUpdateCommand] = Field(default_factory=list)
    update_stairs: list[StairUpdateCommand] = Field(default_factory=list)
    update_doors: list[DoorUpdateCommand] = Field(default_factory=list)
    update_windows: list[WindowUpdateCommand] = Field(default_factory=list)
    update_rooms: list[RoomUpdateCommand] = Field(default_factory=list)
    update_fire_alarms: list[FireAlarmUpdateCommand] = Field(default_factory=list)
    update_soue_devices: list[SoueDeviceUpdateCommand] = Field(default_factory=list)


class BatchSaveResult(APIModel):
    message: str
    floor_plan: FloorPlanRead


StepStatus = Literal["draft", "validated", "stale", "locked"]


class PipelineStepState(APIModel):
    status: StepStatus = "draft"
    revision: int = 0
    detected_at: datetime | None = None
    committed_at: datetime | None = None
    feedback_status: str | None = None
    feedback_example_id: int | None = None
    feedback_submitted_at: datetime | None = None
    feedback_submitted_revision: int | None = None


class PipelineBranchState(APIModel):
    active_step: str = "signal_instruments"
    steps: dict[str, PipelineStepState] = Field(default_factory=dict)


class PipelineStateRead(APIModel):
    floor_plan_id: int
    active_step: str = "walls"
    active_signal_system_type: SignalSystemType = "non_addressable"
    steps: dict[str, PipelineStepState]
    branches: dict[str, PipelineBranchState] = Field(default_factory=dict)


class WallLengthUpdate(APIModel):
    wall_id: int
    length_m: float
    length_source: Literal["ocr", "manual", "derived"] = "manual"


class PipelineWallsCommitRequest(APIModel):
    changes: BatchSaveRequest = Field(default_factory=BatchSaveRequest)
    wall_lengths: list[WallLengthUpdate] = Field(default_factory=list)


class PipelineOpeningsCommitRequest(APIModel):
    changes: BatchSaveRequest = Field(default_factory=BatchSaveRequest)


class RoomCommitUpdate(APIModel):
    room_id: int
    name: str | None = None
    room_number: str | None = None
    room_type: str | None = None
    length_m: float | None = None
    width_m: float | None = None


class PipelineRoomsCommitRequest(APIModel):
    changes: BatchSaveRequest = Field(default_factory=BatchSaveRequest)
    room_updates: list[RoomCommitUpdate] = Field(default_factory=list)


class PipelineZkspcCommitRequest(APIModel):
    zones: list[ZkspcZoneCommit] = Field(default_factory=list)


class PipelineDetectResult(APIModel):
    message: str
    floor_plan: FloorPlanRead
    pipeline_state: PipelineStateRead


class PipelineCommitResult(APIModel):
    message: str
    floor_plan: FloorPlanRead
    pipeline_state: PipelineStateRead


class PipelineStepFeedbackRequest(APIModel):
    step_revision: int
    issue_tags: list[str] = Field(default_factory=list)
    notes: str | None = None


class PipelineStepFeedbackRead(APIModel):
    feedback_id: int
    step: Literal["walls", "openings"]
    status: str
    submitted_revision: int
    pending_counts: RecognitionFeedbackPendingCountsRead
    next_batch_hint: RecognitionBatchHintRead
