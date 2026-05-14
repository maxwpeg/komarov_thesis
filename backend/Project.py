import datetime
import re

from reportlab.pdfgen import canvas

from AdditionalInfoPage import AdditionalInfoPage
from ConnectionDiagramPage import ConnectionDiagramPage
from ConventionalSymbolsPage import ConventionalSymbolsPage
from DrawingPage import DrawingPage
from GeneralDataPage import (
    DEFAULT_GENERAL_DATA_REFERENCE_DOCUMENTS,
    DEFAULT_GENERAL_DATA_STATEMENT,
    GeneralDataPage,
)
from GeneralInstructionsPage import GeneralInstructionsPage
from Page import Page
from PowerConsumptionCalculationPage import PowerConsumptionCalculationPage
from SpecificationPage import SpecificationPage
from StructuralSchemePage import StructuralSchemePage
from TitlePage import TitlePage
from backend.bootstrap import register_pdf_fonts
from backend.project_codes import build_project_code
from consts import *


def _sanitize_filename(filename: str) -> str:
    """Replace characters that are invalid in a filesystem path."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "")
    filename = re.sub(r"\s+", " ", filename).strip().rstrip(".")
    return filename or "project"


def _normalize_stage_value(value: object) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        return DEFAULT_STAGE
    if normalized in {"R", "\u0420", DEFAULT_STAGE, '"\u0420"', "'\u0420'", '"R"', "'R'"}:
        return DEFAULT_STAGE
    return normalized


class Project:
    """Handles file-level operations (canvas creation, page lifecycle)."""

    def __init__(
        self,
        project_type: str = DEFAULT_PROJECT_TYPE,
        number: int | None = None,
        year: int = datetime.datetime.now().year,
        creds: dict[str, str] = DEFAULT_CREDS_DICT,
        number_of_floors: int = DEFAULT_NUMBER_OF_FLOORS,
        floor_plans_data: list | None = None,
        general_data: dict | None = None,
        general_instructions: dict | None = None,
        conventional_symbols: dict | None = None,
        equipment_specification: dict | None = None,
        power_consumption_calculation: dict | None = None,
        additional_info: dict | None = None,
        structural_scheme: dict | None = None,
        connection_diagrams: list[dict] | None = None,
    ):
        if number is None:
            number = DEFAULT_PROJECT_NUMBER
        self.project_type = project_type
        self.number = number
        self.year = year
        self.creds = creds.copy()
        self.creds["Stage"] = _normalize_stage_value(self.creds.get("Stage", DEFAULT_STAGE))
        self.number_of_floors = number_of_floors
        self.floor_plans_data = floor_plans_data or []
        self.general_data = general_data or None
        self.general_instructions = general_instructions or None
        self.conventional_symbols = conventional_symbols or None
        self.equipment_specification = equipment_specification or None
        self.power_consumption_calculation = power_consumption_calculation or None
        self.additional_info = additional_info or None
        self.structural_scheme = structural_scheme or None
        self.connection_diagrams = list(connection_diagrams or [])

        self.code = build_project_code(number=number, year=year, project_type=project_type)
        self.creds["Project Code"] = self.code
        self.number_of_pages = 0

        facility_name = str(self.creds.get("Facility") or "").strip() or "Объект"
        filename = f"{facility_name} {self.code}.pdf"
        filename = _sanitize_filename(filename)
        register_pdf_fonts()
        self._c = canvas.Canvas(filename, pagesize=PAGESIZE_A4)
        self._c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        self._c.setTitle(facility_name)
        self._c.setSubject(f"Проект {facility_name}")
        self._c.setAuthor(str(self.creds.get("Contractor") or DEFAULT_CONTRACTOR_NAME))

    def add_page(self, pagesize: tuple[float, float], mtbox_type: str = "1"):
        page = Page(
            pagesize,
            page_number=self.number_of_pages + 1,
            creds=self.creds,
            main_title_box_type=mtbox_type,
        )
        page.draw(self._c)
        self.number_of_pages += 1

    def add_title_page(self, signed: bool = False):
        title_page = TitlePage(creds=self.creds, signed=signed)
        title_page.draw(self._c, year=self.year)

    def add_drawing_page_with_image(
        self,
        floor_plan_data: dict | None = None,
        pagesize: tuple[float, float] = PAGESIZE_A3_LANDSCAPE,
        title: str = "",
        sheet_kind: str = "generic",
    ):
        resolved_sheet_kind = sheet_kind
        normalized_title = title.lower()
        if resolved_sheet_kind == "generic":
            if "\u0437\u043a\u0441\u043f\u0441" in normalized_title:
                resolved_sheet_kind = "zkspc"
            elif "\u0441\u043f\u0441" in normalized_title:
                resolved_sheet_kind = "sps"
            elif "\u0441\u043e\u0443\u044d" in normalized_title:
                resolved_sheet_kind = "soue"

        page = DrawingPage(
            page_format=pagesize,
            page_number=self.number_of_pages + 1,
            creds=self.creds,
            main_title_box_type="1",
            floor_plan_data=floor_plan_data,
            title=title,
            sheet_kind=resolved_sheet_kind,
        )
        page.draw(self._c)
        self.number_of_pages += 1

    def add_equipment_specification_page(
        self,
        specification: dict | None = None,
        pagesize: tuple[float, float] = PAGESIZE_A3_LANDSCAPE,
    ):
        page = SpecificationPage(
            specification=specification or self.equipment_specification or {},
            page_format=pagesize,
            page_number=self.number_of_pages + 1,
            creds=self.creds,
            main_title_box_type="1",
        )
        page.draw(self._c)
        self.number_of_pages += 1

    def _build_general_instructions_segments(self) -> list[dict[str, object]]:
        if not self.general_instructions:
            return []
        return GeneralInstructionsPage.paginate(
            self.general_instructions,
            page_format=PAGESIZE_A4,
            creds=self.creds,
        )

    def _build_conventional_symbols_segments(self) -> list[dict[str, object]]:
        if not self.conventional_symbols:
            return []
        return ConventionalSymbolsPage.paginate(
            self.conventional_symbols,
            page_format=PAGESIZE_A4,
            creds=self.creds,
        )

    def _build_additional_info_segments(self) -> list[dict[str, object]]:
        if not self.additional_info or bool(self.additional_info.get("is_empty")):
            return []
        return AdditionalInfoPage.paginate(
            self.additional_info,
            page_format=PAGESIZE_A4,
            creds=self.creds,
        )

    def _build_power_consumption_segments(self) -> list[dict[str, object]]:
        if not self.power_consumption_calculation:
            return []
        return PowerConsumptionCalculationPage.paginate(
            self.power_consumption_calculation,
            page_format=PAGESIZE_A4,
            main_title_box_type="1",
            creds=self.creds,
        )

    def _calculate_total_sheets(
        self,
        *,
        general_instructions_segments: list[dict[str, object]] | None = None,
        conventional_symbols_segments: list[dict[str, object]] | None = None,
        additional_info_segments: list[dict[str, object]] | None = None,
        power_consumption_segments: list[dict[str, object]] | None = None,
    ) -> int:
        instructions_count = len(
            general_instructions_segments
            if general_instructions_segments is not None
            else self._build_general_instructions_segments()
        ) or 2
        symbols_count = len(
            conventional_symbols_segments
            if conventional_symbols_segments is not None
            else self._build_conventional_symbols_segments()
        ) or 1
        additional_count = len(
            additional_info_segments
            if additional_info_segments is not None
            else self._build_additional_info_segments()
        )
        power_count = (
            len(
                power_consumption_segments
                if power_consumption_segments is not None
                else self._build_power_consumption_segments()
            )
            if self.power_consumption_calculation
            else 1
        )
        return (
            1  # General data
            + instructions_count
            + symbols_count
            + 1  # Structural scheme
            + len(self.floor_plans_data) * 3
            + max(1, len(self.connection_diagrams))
            + 1  # Equipment specification, rendered as a blank sheet if empty
            + power_count
            + additional_count
        )

    def _build_general_data_payload(
        self,
        general_instructions_sheet_count: int | None = None,
        conventional_symbols_sheet_count: int | None = None,
        additional_info_sheet_count: int | None = None,
    ) -> dict[str, object]:
        if self.general_data is not None:
            return dict(self.general_data)
        floor_count = len(self.floor_plans_data) or int(self.number_of_floors or 0)
        if floor_count < 1:
            floor_count = 1
        if general_instructions_sheet_count is None:
            if self.general_instructions:
                general_instructions_sheet_count = len(self._build_general_instructions_segments())
            else:
                general_instructions_sheet_count = 1
        if conventional_symbols_sheet_count is None:
            if self.conventional_symbols:
                conventional_symbols_sheet_count = len(self._build_conventional_symbols_segments())
            else:
                conventional_symbols_sheet_count = 1
        if additional_info_sheet_count is None:
            additional_info_sheet_count = len(self._build_additional_info_segments()) if self.additional_info else 0

        manifest_rows: list[dict[str, object]] = [
            {"name": "Общие данные", "sheet_count": 1, "note": ""},
            {
                "name": "Общие указания",
                "sheet_count": general_instructions_sheet_count,
                "note": f"на {general_instructions_sheet_count}-х листах" if general_instructions_sheet_count > 1 else "",
            },
            {
                "name": "Условные графические обозначения",
                "sheet_count": conventional_symbols_sheet_count,
                "note": f"на {conventional_symbols_sheet_count}-х листах" if conventional_symbols_sheet_count > 1 else "",
            },
            {"name": "Структурная схема СПС и СОУЭ", "sheet_count": 1, "note": ""},
            {
                "name": "План зон контроля сетей пожарной сигнализации",
                "sheet_count": floor_count,
                "note": f"на {floor_count}-х листах" if floor_count > 1 else "",
            },
            {
                "name": "План сетей системы пожарной сигнализации",
                "sheet_count": floor_count,
                "note": f"на {floor_count}-х листах" if floor_count > 1 else "",
            },
            {
                "name": "План сетей системы оповещения и управления эвакуацией людей при пожаре",
                "sheet_count": floor_count,
                "note": f"на {floor_count}-х листах" if floor_count > 1 else "",
            },
        ]

        connection_diagrams_count = max(1, len(self.connection_diagrams))
        manifest_rows.append(
            {
                "name": "Схемы подключения оборудования",
                "sheet_count": connection_diagrams_count,
                "note": f"на {connection_diagrams_count}-х листах" if connection_diagrams_count > 1 else "",
            }
        )

        if self.equipment_specification:
            manifest_rows.append(
                {
                    "name": "Спецификация оборудования и материалов",
                    "sheet_count": 1,
                    "note": "",
                }
            )

        if self.power_consumption_calculation:
            power_sheet_count = len(
                PowerConsumptionCalculationPage.paginate(
                    self.power_consumption_calculation,
                    page_format=PAGESIZE_A4,
                    main_title_box_type="1",
                    creds=self.creds,
                )
            )
            manifest_rows.append(
                {
                    "name": "Расчет токопотребления системы",
                    "sheet_count": power_sheet_count,
                    "note": f"на {power_sheet_count}-х листах" if power_sheet_count > 1 else "",
                }
            )

        if self.additional_info and not bool(self.additional_info.get("is_empty")) and additional_info_sheet_count:
            manifest_rows.append(
                {
                    "name": "Р”РѕРї. СЃРІРµРґРµРЅРёСЏ",
                    "sheet_count": additional_info_sheet_count,
                    "note": f"РЅР° {additional_info_sheet_count}-С… Р»РёСЃС‚Р°С…" if additional_info_sheet_count > 1 else "",
                }
            )

        return {
            "reference_documents": [dict(row) for row in DEFAULT_GENERAL_DATA_REFERENCE_DOCUMENTS],
            "attached_documents": [
                {
                    "designation": self.code,
                    "name": "Спецификация оборудования и материалов",
                    "note": "",
                }
            ],
            "drawing_manifest_rows": manifest_rows,
            "statement_text": DEFAULT_GENERAL_DATA_STATEMENT,
            "gip_name": str(self.creds.get("CPE") or ""),
        }

    def add_general_data_page(
        self,
        general_data: dict | None = None,
        pagesize: tuple[float, float] = PAGESIZE_A3_LANDSCAPE,
    ):
        page = GeneralDataPage(
            general_data=general_data or self._build_general_data_payload(),
            page_format=pagesize,
            page_number=self.number_of_pages + 1,
            creds=self.creds,
            main_title_box_type="1",
        )
        page.draw(self._c)
        self.number_of_pages += 1

    def add_general_instructions_pages(
        self,
        instructions: dict | None = None,
        *,
        segments: list[dict[str, object]] | None = None,
        pagesize: tuple[float, float] = PAGESIZE_A4,
    ):
        resolved_instructions = instructions or self.general_instructions or {}
        resolved_segments = list(
            segments
            or GeneralInstructionsPage.paginate(
                resolved_instructions,
                page_format=pagesize,
                creds=self.creds,
            )
        )
        total_sheets = len(resolved_segments)
        for index, segment in enumerate(resolved_segments, start=1):
            page = GeneralInstructionsPage(
                instructions=resolved_instructions,
                page_lines=segment.get("page_lines") or [],
                show_heading=bool(segment.get("show_heading")),
                is_continuation=bool(segment.get("is_continuation")),
                local_sheet_number=index,
                local_total_sheets=total_sheets,
                page_format=pagesize,
                page_number=self.number_of_pages + 1,
                creds=self.creds,
                main_title_box_type=str(segment.get("main_title_box_type") or "1"),
            )
            page.draw(self._c)
            self.number_of_pages += 1

    def add_conventional_symbols_pages(
        self,
        conventional_symbols: dict | None = None,
        *,
        segments: list[dict[str, object]] | None = None,
        pagesize: tuple[float, float] = PAGESIZE_A4,
    ):
        resolved_symbols = conventional_symbols or self.conventional_symbols or {}
        resolved_segments = list(
            segments
            or ConventionalSymbolsPage.paginate(
                resolved_symbols,
                page_format=pagesize,
                creds=self.creds,
            )
        )
        for segment in resolved_segments:
            page = ConventionalSymbolsPage(
                conventional_symbols=resolved_symbols,
                page_rows=segment.get("page_rows") or [],
                show_decode=bool(segment.get("show_decode")),
                is_continuation=bool(segment.get("is_continuation")),
                page_format=pagesize,
                page_number=self.number_of_pages + 1,
                creds=self.creds,
                main_title_box_type=str(segment.get("main_title_box_type") or "1"),
            )
            page.draw(self._c)
            self.number_of_pages += 1

    def add_power_consumption_calculation_pages(
        self,
        calculation: dict | None = None,
        pagesize: tuple[float, float] = PAGESIZE_A4,
    ):
        resolved_calculation = calculation or self.power_consumption_calculation or {}
        segments = PowerConsumptionCalculationPage.paginate(
            resolved_calculation,
            page_format=pagesize,
            main_title_box_type="1",
            creds=self.creds,
        )
        for segment in segments:
            page = PowerConsumptionCalculationPage(
                calculation=resolved_calculation,
                page_rows=segment.get("page_rows") or [],
                show_intro=bool(segment.get("show_intro")),
                show_summary=bool(segment.get("show_summary")),
                is_continuation=bool(segment.get("is_continuation")),
                page_format=pagesize,
                page_number=self.number_of_pages + 1,
                creds=self.creds,
                main_title_box_type="1",
            )
            page.draw(self._c)
            self.number_of_pages += 1

    def add_structural_scheme_page(
        self,
        structural_scheme: dict | None = None,
        pagesize: tuple[float, float] = PAGESIZE_A3_LANDSCAPE,
    ):
        page = StructuralSchemePage(
            structural_scheme=structural_scheme or self.structural_scheme or {},
            page_format=pagesize,
            page_number=self.number_of_pages + 1,
            creds=self.creds,
            main_title_box_type="1",
        )
        page.draw(self._c)
        self.number_of_pages += 1

    def add_additional_info_pages(
        self,
        additional_info: dict | None = None,
        *,
        segments: list[dict[str, object]] | None = None,
        pagesize: tuple[float, float] = PAGESIZE_A4,
    ):
        resolved_info = additional_info or self.additional_info or {}
        resolved_segments = list(
            segments
            or AdditionalInfoPage.paginate(
                resolved_info,
                page_format=pagesize,
                creds=self.creds,
            )
        )
        total_sheets = len(resolved_segments)
        for index, segment in enumerate(resolved_segments, start=1):
            page = AdditionalInfoPage(
                instructions=resolved_info,
                page_lines=segment.get("page_lines") or [],
                show_heading=bool(segment.get("show_heading")),
                is_continuation=bool(segment.get("is_continuation")),
                local_sheet_number=index,
                local_total_sheets=total_sheets,
                page_format=pagesize,
                page_number=self.number_of_pages + 1,
                creds=self.creds,
                main_title_box_type=str(segment.get("main_title_box_type") or "1"),
            )
            page.draw(self._c)
            self.number_of_pages += 1

    def add_connection_diagram_pages(
        self,
        diagrams: list[dict] | None = None,
        pagesize: tuple[float, float] = PAGESIZE_A3_LANDSCAPE,
    ):
        resolved_diagrams = list(diagrams if diagrams is not None else self.connection_diagrams)
        if not resolved_diagrams:
            self.add_page(pagesize, mtbox_type="1")
            return
        for diagram in resolved_diagrams:
            page = ConnectionDiagramPage(
                diagram=diagram,
                page_format=pagesize,
                page_number=self.number_of_pages + 1,
                creds=self.creds,
                main_title_box_type="1",
            )
            page.draw(self._c)
            self.number_of_pages += 1

    def launch(self):
        general_instructions_segments = self._build_general_instructions_segments()
        conventional_symbols_segments = self._build_conventional_symbols_segments()
        additional_info_segments = self._build_additional_info_segments()
        power_consumption_segments = self._build_power_consumption_segments()
        self.creds["Total Sheets"] = str(
            self._calculate_total_sheets(
                general_instructions_segments=general_instructions_segments,
                conventional_symbols_segments=conventional_symbols_segments,
                additional_info_segments=additional_info_segments,
                power_consumption_segments=power_consumption_segments,
            )
        )
        self.add_title_page(signed=False)
        self.add_title_page(signed=True)
        self.add_general_data_page(
            general_data=self._build_general_data_payload(
                general_instructions_sheet_count=len(general_instructions_segments) or 1,
                conventional_symbols_sheet_count=len(conventional_symbols_segments) or 1,
                additional_info_sheet_count=len(additional_info_segments),
            ),
            pagesize=PAGESIZE_A3_LANDSCAPE,
        )
        if general_instructions_segments:
            self.add_general_instructions_pages(
                self.general_instructions,
                segments=general_instructions_segments,
                pagesize=PAGESIZE_A4,
            )
        else:
            self.add_page(PAGESIZE_A4, mtbox_type="1")
            self.add_page(PAGESIZE_A4, mtbox_type="2")
        if conventional_symbols_segments:
            self.add_conventional_symbols_pages(
                self.conventional_symbols,
                segments=conventional_symbols_segments,
                pagesize=PAGESIZE_A4,
            )
        else:
            self.add_page(PAGESIZE_A4, mtbox_type="1")
        self.add_structural_scheme_page(self.structural_scheme, PAGESIZE_A3_LANDSCAPE)

        for floor_plan in self.floor_plans_data:
            floor_name = floor_plan.get("name", "План этажа")
            self.add_drawing_page_with_image(
                floor_plan_data=floor_plan,
                pagesize=PAGESIZE_A3_LANDSCAPE,
                title=f"ЗКСПС - {floor_name}",
                sheet_kind="zkspc",
            )
            self.add_drawing_page_with_image(
                floor_plan_data=floor_plan,
                pagesize=PAGESIZE_A3_LANDSCAPE,
                title=f"СПС - {floor_name}",
                sheet_kind="sps",
            )
            self.add_drawing_page_with_image(
                floor_plan_data=floor_plan,
                pagesize=PAGESIZE_A3_LANDSCAPE,
                title=f"СОУЭ - {floor_name}",
                sheet_kind="soue",
            )

        self.add_connection_diagram_pages(self.connection_diagrams, PAGESIZE_A3_LANDSCAPE)
        if self.equipment_specification:
            self.add_equipment_specification_page(self.equipment_specification, PAGESIZE_A3_LANDSCAPE)
        else:
            self.add_equipment_specification_page({}, PAGESIZE_A3_LANDSCAPE)
        if self.power_consumption_calculation:
            self.add_power_consumption_calculation_pages(self.power_consumption_calculation, PAGESIZE_A4)
        else:
            self.add_page(PAGESIZE_A4, mtbox_type="1")
        if additional_info_segments:
            self.add_additional_info_pages(
                self.additional_info,
                segments=additional_info_segments,
                pagesize=PAGESIZE_A4,
            )

    def save(self):
        self._c.save()
