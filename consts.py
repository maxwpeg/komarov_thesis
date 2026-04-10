from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.lib.pagesizes import A4, A3, landscape

# Alignment constants
CENTER = 'center'
LEFT = 'left'
RIGHT = 'right'

# Default font settings
DEFAULT_FONT_NAME = "GOST Type A"
DEFAULT_FONT_SIZE = 12

# Page size constants
PAGESIZE_A4 = A4
PAGESIZE_A4_LANDSCAPE = (A4[1], A4[0])  # Landscape orientation
PAGESIZE_A3 = A3
PAGESIZE_A3_LANDSCAPE = (A3[1], A3[0])  # Landscape orientation

# Default constants for PDF page layout and styling
DEFAULT_OUTER_BORDER_THICKNESS_MM = 0.8 * mm
DEFAULT_INNER_BORDER_THICKNESS_MM = 0.5 * mm

# Default border sizes in millimeters
DEFAULT_LEFT_BORDER_MM = 20.0 * mm
DEFAULT_RIGHT_BORDER_MM = 5.0 * mm
DEFAULT_TOP_BORDER_MM = 5.0 * mm
DEFAULT_BOTTOM_BORDER_MM = 5.0 * mm

DEFAULT_BORDERS: dict[str, float] = {
    "left": DEFAULT_LEFT_BORDER_MM,
    "right": DEFAULT_RIGHT_BORDER_MM,
    "top": DEFAULT_TOP_BORDER_MM,
    "bottom": DEFAULT_BOTTOM_BORDER_MM,
}

# Default colors
DEFAULT_BORDER_COLOR = colors.black
DEFAULT_MAIN_TITLE_COLOR = colors.black

# Default main title box sizes
MAIN_TITLE_BOX_DICT = {
    "1": (185.0 * mm, 55.0 * mm),
    "2": (185.0 * mm, 15.0 * mm),
    # Future types can be added here
}

# Default main title line configurations for type '1'
MAIN_TITLE_BOX_1_LINES: list[tuple[str, float, float, float, float]] = [
                ("v", 65, 55, 55, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("h", 0, 50, 65, DEFAULT_INNER_BORDER_THICKNESS_MM),
                ("h", 0, 45, 65, DEFAULT_INNER_BORDER_THICKNESS_MM),
                ("h", 0, 40, 65, DEFAULT_INNER_BORDER_THICKNESS_MM),
                ("h", 0, 35, 65, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("h", 0, 30, 65, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("h", 0, 25, 65, DEFAULT_INNER_BORDER_THICKNESS_MM),
                ("h", 0, 20, 65, DEFAULT_INNER_BORDER_THICKNESS_MM),
                ("h", 0, 15, 65, DEFAULT_INNER_BORDER_THICKNESS_MM),
                ("h", 0, 10, 65, DEFAULT_INNER_BORDER_THICKNESS_MM),
                ("h", 0, 5, 65, DEFAULT_INNER_BORDER_THICKNESS_MM),
                ("v", 10, 55, 25, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("v", 20, 55, 55, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("v", 30, 55, 25, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("v", 40, 55, 55, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("v", 55, 55, 55, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("h", 65, 45, 120, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("h", 65, 30, 120, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("h", 65, 15, 120, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("v", 135, 30, 30, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("h", 135, 25, 50, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("v", 150, 30, 15, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("v", 165, 30, 15, DEFAULT_OUTER_BORDER_THICKNESS_MM)
            ]

MAIN_TITLE_BOX_2_LINES: list[tuple[str, float, float, float, float]] = [
                ("v", 65, 15, 15, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("h", 0, 10, 65, DEFAULT_INNER_BORDER_THICKNESS_MM),
                ("h", 0, 5, 65, DEFAULT_INNER_BORDER_THICKNESS_MM),
                ("v", 10, 15, 15, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("v", 20, 15, 15, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("v", 30, 15, 15, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("v", 40, 15, 15, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("v", 55, 15, 15, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("v", 170, 15, 15, DEFAULT_OUTER_BORDER_THICKNESS_MM),
                ("h", 170, 10, 15, DEFAULT_OUTER_BORDER_THICKNESS_MM)
]

# Default main title text configurations for type '1'
MAIN_TITLE_BOX_1_TEXTS: list[tuple[str, float, float, str]] = [
        ("Изм.", 5, 31, CENTER),
        ("Кол.уч", 15, 31, CENTER),
        ("Лист", 25, 31, CENTER),
        ("Nдок.", 35, 31, CENTER),
        ("Подпись", 47.5, 31, CENTER),
        ("Дата", 60, 31, CENTER),
        ("Разраб.", 1, 26, LEFT),
        ("Пров.", 1, 21, LEFT),
        ("Утв.", 1, 1, LEFT),
        ("Стадия", 142.5, 26, CENTER),
        ("Лист", 157.5, 26, CENTER),
        ("Листов", 175, 26, CENTER)
    ]

# Default main title text configurations for type '2'
MAIN_TITLE_BOX_2_TEXTS: list[tuple[str, float, float, float, float, str]] = [
        ("Изм.", 0, 0, 10, 5, LEFT),
        ("Кол.уч", 10, 0, 10, 5, LEFT),
        ("Лист", 20, 0, 10, 5, LEFT),
        ("Nдок.", 30, 0, 10, 5, LEFT),
        ("Подпись", 40, 0, 15, 5, LEFT),
        ("Дата", 55, 0, 10, 5, LEFT),
        ("Лист", 170, 10, 15, 5, CENTER),
    ]

# Default project information
DEFAULT_CONTRACTOR_NAME = "ООО \"Флагман-СБ\""
DEFAULT_CHECKER_NAME = "Комаров С.Л."
DEFAULT_CPE_NAME = "Гостев В.В."
DEFAULT_ENGINEER_NAME = "Комарова Н.С."
DEFAULT_FACILITY_NAME = "Магазин ИП Гришанов А.В."
DEFAULT_FACILITY_ADDRESS = "Тульская обл., г. Ефремов, ул. Энтузиастов, д. 17"
DEFAULT_PROJECT_TYPE = "ПС"
DEFAULT_PROJECT_NUMBER = 1
DEFAULT_PROJECT_YEAR = 26
DEFAULT_NUMBER_OF_FLOORS = 1
DEFAULT_PROJECT_DESCRIPTION = "Система пожарной сигнализации и система оповещения и управления эвакуацией людей при пожаре"
DEFAULT_STAGE = "«Р»"

DEFAULT_CREDS: list[str] = [
    DEFAULT_CONTRACTOR_NAME,
    DEFAULT_ENGINEER_NAME,
    DEFAULT_CPE_NAME,
    DEFAULT_CHECKER_NAME,
    DEFAULT_FACILITY_NAME,
    DEFAULT_FACILITY_ADDRESS,
    DEFAULT_PROJECT_DESCRIPTION,
    DEFAULT_STAGE
]

DEFAULT_CREDS_DICT: dict[str, str] = {
    "Contractor": DEFAULT_CONTRACTOR_NAME,
    "Engineer": DEFAULT_ENGINEER_NAME,
    "CPE": DEFAULT_CPE_NAME,
    "Checker": DEFAULT_CHECKER_NAME,
    "Facility": DEFAULT_FACILITY_NAME,
    "Facility Address": DEFAULT_FACILITY_ADDRESS,
    "Project Description": DEFAULT_PROJECT_DESCRIPTION,
    "Stage": DEFAULT_STAGE,
}

MAIN_TITLE_BOX_1_FILLINGS_POSITIONINGS: dict[str, tuple[float, float, float, float, str]] = {
    "Contractor": (135, 0, 50, 15, CENTER),
    "Engineer": (20, 25, 20, 5, LEFT),
    "CPE": (20, 20, 20, 5, LEFT),
    "Checker": (20, 0, 20, 5, LEFT),
    "Facility": (65, 40, 120, 5, CENTER),
    "Facility Address": (65, 30, 120, 10, CENTER),
    "Project Description": (65, 15, 70, 15, CENTER),
    "Stage": (135, 15, 15, 10, CENTER),
    "Project Code": (65, 45, 120, 10, CENTER),
    "Sheet Number": (150, 15, 15, 10, CENTER),
    "Total Sheets": (165, 15, 20, 10, CENTER),
    "Title of the Drawing": (65, 0, 70, 15, CENTER),
}

MAIN_TITLE_BOX_2_FILLINGS_POSITIONINGS: dict[str, tuple[float, float, float, float, str]] = {
    "Sheet Number": (170, 0, 15, 10, CENTER),
    "Project Code": (65, 0, 105, 15, CENTER),
}

PROJECT_DESCRIPTION_BOX_HEIGHT_MM = 15 * mm
PROJECT_DESCRIPTION_BOX_WIDTH_MM = 70 * mm
PROJECT_DESCRIPTION_BOX_X_MM = 65 * mm
PROJECT_DESCRIPTION_BOX_Y_MM = 15 * mm


MAIN_SET_OF_WORKING_DRAWINGS_STR = "Основной комплект рабочих чертежей"

DEFAULT_TITLE_FONT_SIZE = 18
DIMENSION_TEXT_FONT_SIZE = 10.0
DIMENSION_ARROW_SIZE = 3.0 * mm
DIMENSION_TEXT_GAP = 0.5 * DIMENSION_TEXT_FONT_SIZE

CEO_STR = "Генеральный директор"
CPE_STR = "Главный инженер проекта"
SIGN_LINE_STR = "____________________"
GAP3_STR = "   "  # three spaces gap for signature line
