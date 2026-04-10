import datetime

from reportlab.pdfgen import canvas

from DrawingPage import DrawingPage
from Page import Page
from TitlePage import TitlePage
from backend.bootstrap import register_pdf_fonts
from backend.project_codes import build_project_code
from consts import *


def _sanitize_filename(filename: str) -> str:
    """Replace characters that are invalid in a filesystem path."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    return filename


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
    ):
        if number is None:
            number = DEFAULT_PROJECT_NUMBER
        self.project_type = project_type
        self.number = number
        self.year = year
        self.creds = creds.copy()
        self.number_of_floors = number_of_floors
        self.floor_plans_data = floor_plans_data or []

        self.code = build_project_code(number=number, year=year, project_type=project_type)
        self.creds["Project Code"] = self.code
        self.number_of_pages = 0

        filename = f"{self.creds['Facility']} {number}-{self.year} {self.creds['Contractor']}.pdf"
        filename = _sanitize_filename(filename)
        register_pdf_fonts()
        self._c = canvas.Canvas(filename, pagesize=PAGESIZE_A4)
        self._c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)

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

    def launch(self):
        self.add_title_page(signed=False)
        self.add_title_page(signed=True)
        self.add_page(PAGESIZE_A3_LANDSCAPE, mtbox_type="1")
        self.add_page(PAGESIZE_A4, mtbox_type="1")
        self.add_page(PAGESIZE_A4, mtbox_type="2")
        self.add_page(PAGESIZE_A4, mtbox_type="1")
        self.add_page(PAGESIZE_A4, mtbox_type="1")

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

        self.add_page(PAGESIZE_A3_LANDSCAPE, mtbox_type="1")
        self.add_page(PAGESIZE_A3_LANDSCAPE, mtbox_type="1")
        self.add_page(PAGESIZE_A4, mtbox_type="1")

    def save(self):
        self._c.save()
