from reportlab.pdfgen import canvas
from Page import Page
from TitlePage import TitlePage
from DrawingPage import DrawingPage
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
            number_of_floors: int = DEFAULT_NUMBER_OF_FLOORS,
            floor_plans_data: list = None
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
        self.floor_plans_data = floor_plans_data or []

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
    
    def add_drawing_page_with_image(self, floor_plan_data: dict = None, pagesize: tuple[float, float] = PAGESIZE_A3_LANDSCAPE, title: str = ""):
        """Добавляет страницу с чертежом (только линии элементов)."""
        page = DrawingPage(
            page_format=pagesize,
            page_number=self.number_of_pages + 1,
            creds=self.creds,
            main_title_box_type="1",
            floor_plan_data=floor_plan_data,
            title=title
        )
        
        # Рисуем страницу (все элементы отрисовываются внутри)
        page.draw(self._c)
        self.number_of_pages += 1
    
    def launch(self):
        """Генерирует полный PDF документ со всеми необходимыми страницами."""
        # 1. Титульный лист без подписи
        self.add_title_page(signed=False)
        
        # 2. Титульный лист с подписью
        self.add_title_page(signed=True)
        
        # 3. Страница A3 горизонтальная
        self.add_page(PAGESIZE_A3_LANDSCAPE, mtbox_type="1")
        
        # 4. Страница A4 вертикальная
        self.add_page(PAGESIZE_A4, mtbox_type="1")
        
        # 5. Страница A4 вертикальная с рамкой типа 2
        self.add_page(PAGESIZE_A4, mtbox_type="2")
        
        # 6. Еще 2 страницы A4 вертикальных
        self.add_page(PAGESIZE_A4, mtbox_type="1")
        self.add_page(PAGESIZE_A4, mtbox_type="1")
        
        # 7-9. Каждый план этажа трижды: ЗКСПС, СПС, СОУЭ
        # Рисуем каждый план на трех отдельных листах A3 горизонтальных
        for fp in self.floor_plans_data:
            # ЗКСПС
            self.add_drawing_page_with_image(
                floor_plan_data=fp,
                pagesize=PAGESIZE_A3_LANDSCAPE,
                title=f"ЗКСПС - {fp.get('name', 'План этажа')}"
            )
            
            # СПС
            self.add_drawing_page_with_image(
                floor_plan_data=fp,
                pagesize=PAGESIZE_A3_LANDSCAPE,
                title=f"СПС - {fp.get('name', 'План этажа')}"
            )
            
            # СОУЭ
            self.add_drawing_page_with_image(
                floor_plan_data=fp,
                pagesize=PAGESIZE_A3_LANDSCAPE,
                title=f"СОУЭ - {fp.get('name', 'План этажа')}"
            )
        
        # 10. Лист A3 горизонтальный (схемы подключения)
        self.add_page(PAGESIZE_A3_LANDSCAPE, mtbox_type="1")
        # TODO: Добавить логику для схем подключения
        
        # 11. Лист A3 горизонтальный (спецификация)
        self.add_page(PAGESIZE_A3_LANDSCAPE, mtbox_type="1")
        # TODO: Добавить логику для спецификации
        
        # 12. Лист A4 вертикальный (расчет токопотребления)
        self.add_page(PAGESIZE_A4, mtbox_type="1")
        # TODO: Добавить логику для расчета токопотребления


    def save(self):
        self._c.save()


Project.number_of_projects = _load_counter()