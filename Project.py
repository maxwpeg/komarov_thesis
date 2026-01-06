from reportlab.pdfgen import canvas
from Page import Page
from TitlePage import TitlePage
from consts import *
import os
import json
import datetime

# файл для хранения счётчика проектов
_COUNTER_FILE = os.path.join(os.path.dirname(__file__), "project_counter.json")

def _sanitize_filename(filename: str) -> str:
    """Заменяет недопустимые символы в имени файла на подчеркивания."""
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '')
    return filename

def _load_counter() -> int:
    try:
        with open(_COUNTER_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return int(data.get("number_of_projects", 1))
    except Exception:
        return 1

def _save_counter(value: int):
    try:
        with open(_COUNTER_FILE, "w", encoding="utf-8") as f:
            json.dump({"number_of_projects": int(value)}, f)
    except Exception:
        # молча игнорируем ошибки записи
        pass

class Project:
    """Handles file-level operations (canvas creation, page lifecycle)."""

    number_of_projects = 1

    def __init__(
            self, 
            project_type: str = DEFAULT_PROJECT_TYPE, 
            number: int | None = None, 
            year: int = datetime.datetime.now().year, 
            creds: dict[str, str] = DEFAULT_CREDS_DICT,
            number_of_floors: int = DEFAULT_NUMBER_OF_FLOORS
            ):
        if number is None:
            number = Project.number_of_projects
        
        Project.number_of_projects += 1
        _save_counter(Project.number_of_projects)
        self.project_type = project_type
        self.number = number
        self.year = year
        self.creds = creds.copy()
        self.number_of_floors = number_of_floors

        self.code = f"РП-ЗК-{number}/{year % 100}-{project_type}"
        self.creds["Project Code"] = self.code
        self.number_of_pages = 0

        # приватное поле для canvas
        filename = f"{self.creds['Facility']} {number}-{self.year} {self.creds['Contractor']}.pdf"
        filename = _sanitize_filename(filename)
        self._c = canvas.Canvas(filename, pagesize=PAGESIZE_A4)
        self._c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)

    def add_page(self, pagesize: tuple[float, float], mtbox_type: str = "1"):
        # используем внутреннее поле canvas
        page = Page(pagesize, page_number=self.number_of_pages + 1, creds=self.creds, main_title_box_type=mtbox_type)
        page.draw(self._c)
        self.number_of_pages += 1

    def add_title_page(self, signed: bool = False):
        title_page = TitlePage(creds=self.creds, signed=signed)
        title_page.draw(self._c, year=self.year)
    
    def launch(self):
        self.add_title_page()
        self.add_title_page(signed=True)
        self.add_page(PAGESIZE_A4)
        self.add_page(PAGESIZE_A4, mtbox_type="2")

    def save(self):
        self._c.save()


Project.number_of_projects = _load_counter()