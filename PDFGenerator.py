# from reportlab.pdfgen import canvas
# from reportlab.lib.pagesizes import A3, A4, landscape
# from reportlab.lib.units import mm
# from reportlab.lib import colors
# from reportlab.pdfbase import pdfmetrics
# from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from Page import Page
from Project import Project
from consts import *


class PDFGenerator:
    """High-level orchestrator that composes PdfFile and PdfPage.

    This class keeps much of the original constructor/validation surface so
    existing callers can be migrated with minimal changes.
    """

    def __init__(
        self,
        filename: str = "output.pdf",
        page_format: str = "A3",
        orientation: str = "vertical",
        left_border_mm: float = 20.0,
        right_border_mm: float = 5.0,
        top_border_mm: float = 5.0,
        bottom_border_mm: float = 5.0,
        main_title_type: str = "1"
    ):
        self.filename = filename
        self.page_format = page_format
        self.orientation = orientation

        # Create a PdfPage which also resolves its own pagesize
        self.pdf_page = Page()

        # Use pagesize from the page object for canvas creation
        # self.pagesize = self.pdf_page.pagesize
        # self.page_width, self.page_height = self.pagesize

        # Compose file helper
        self.pdf_file = Project()

    def create_pdf(self):
        pass
        # c = self.pdf_file.create_canvas()
        # self.pdf_file.add_page(c, self.pdf_page,)
        # self.pdf_file.save(c)


if __name__ == "__main__":
    additional_texts: list[tuple[str, float, float, str, float, str]] = [
        ("ООО \"Флагман-СБ\"", 160, 6.5, "GOST Type A", 12, "center"),
        ("Щербакова Н.С.", 21, 26, "GOST Type A", 10, "left"),
        ("Гостев В.В.", 21, 21, "GOST Type A", 12, "left"),
        ("Комаров С.Л.", 21, 1, "GOST Type A", 12, "left"),
        ("РП-ЗК-11/25-ПС", 125, 49, "GOST Type A", 12, "center"),
        ("Магазин ИП Гришанов А.В.", 125, 39, "GOST Type A", 12, "center"),
        ("Тульская обл., г. Ефремов, ул. Энтузиастов, д. 17", 125, 34, "GOST Type A", 12, "center"),
        ("Система пожарной сигнализации", 100, 26.5, "GOST Type A", 12, "center"),
        ("и система оповещения и управления ", 100, 21.5, "GOST Type A", 12, "center"),
        ("эвакуацией людей при пожаре", 100, 16.5, "GOST Type A", 12, "center"),
        ("Р", 142.5, 19, "GOST Type A", 12, "center"),
        ("5", 157.5, 19, "GOST Type A", 12, "center"),
        ("10", 175, 19, "GOST Type A", 12, "center"),
        ("План ЗКПС", 100, 6.5, "GOST Type A", 12, "center"),

    ]


    pdfmetrics.registerFont(TTFont("GOST Type A", "./GOST_A.TTF"))
    gen = PDFGenerator("A3.pdf", orientation="horizontal")
    gen.create_pdf()