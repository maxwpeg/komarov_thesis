from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3, A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


class PdfPage:
    """Page-level configuration and drawing.

    New functional contract:
    - page_format: 'A3' or 'A4'
    - orientation: 'horizontal' or 'vertical' (A4 only allows 'vertical')
    - fixed outer border thickness 1.4 mm and margins: left 20 mm, right 5 mm, top 5 mm, bottom 5 mm
    - main_title_type: '1' or '2' (type '1' implemented with a default table and line list)
    """

    DEFAULT_OUTER_BORDER_THICKNESS_MM = 0.8
    DEFAULT_LEFT_BORDER_MM = 20.0
    DEFAULT_RIGHT_BORDER_MM = 5.0
    DEFAULT_TOP_BORDER_MM = 5.0
    DEFAULT_BOTTOM_BORDER_MM = 5.0
    

    # default main title table size for type '1'
    MAIN_TITLE_W_MM = 185.0
    MAIN_TITLE_H_MM = 55.0

    def __init__(
        self,
        page_format: str = "A3",
        orientation: str = "vertical",
        left_border_mm: float = DEFAULT_LEFT_BORDER_MM,
        right_border_mm: float = DEFAULT_RIGHT_BORDER_MM,
        top_border_mm: float = DEFAULT_TOP_BORDER_MM,
        bottom_border_mm: float = DEFAULT_BOTTOM_BORDER_MM,
        outer_border_thickness_mm: float = DEFAULT_OUTER_BORDER_THICKNESS_MM,
        main_title_type: str = "1",
        main_title_lines: list = None,
        main_title_texts: list = None,
        additional_title_texts: list = None,
        border_color=colors.black,
        main_title_color=colors.black,
    ):
        page_format = page_format.upper()
        orientation = orientation.lower()
        if page_format not in ("A3", "A4"):
            raise ValueError("page_format must be 'A3' or 'A4'")
        if page_format == "A4" and orientation != "vertical":
            raise ValueError("A4 pages can only be vertical orientation")

        # resolve pagesize
        if page_format == "A3":
            base_size = A3
        else:
            base_size = A4

        if orientation == "horizontal":
            pagesize = landscape(base_size)
        else:
            pagesize = base_size

        self.page_format = page_format
        self.orientation = orientation
        self.pagesize = pagesize
        self.page_width, self.page_height = pagesize

        # Margins and border
        self.left_border = left_border_mm * mm
        self.right_border = right_border_mm * mm
        self.top_border = top_border_mm * mm
        self.bottom_border = bottom_border_mm * mm
        self.outer_border_thickness = outer_border_thickness_mm * mm
        self.border_color = border_color

        # Main title box configuration
        self.main_title_type = main_title_type
        self.main_title_w = self.MAIN_TITLE_W_MM * mm
        self.main_title_h = self.MAIN_TITLE_H_MM * mm
        self.main_title_color = main_title_color

        # default lines for main title type '1' (tuples: (type, x_mm, y_mm, length_mm, thickness_mm?))
        if main_title_lines is None and main_title_type == "1":
            self.main_title_lines = [
                ("v", 65, 55, 55),
                ("h", 0, 50, 65, 0.5),
                ("h", 0, 45, 65, 0.5),
                ("h", 0, 40, 65, 0.5),
                ("h", 0, 35, 65),
                ("h", 0, 30, 65),
                ("h", 0, 25, 65, 0.5),
                ("h", 0, 20, 65, 0.5),
                ("h", 0, 15, 65, 0.5),
                ("h", 0, 10, 65, 0.5),
                ("h", 0, 5, 65, 0.5),
                ("v", 10, 55, 25),
                ("v", 20, 55, 55),
                ("v", 30, 55, 25),
                ("v", 40, 55, 55),
                ("v", 55, 55, 55),
                ("h", 65, 45, 120),
                ("h", 65, 30, 120),
                ("h", 65, 15, 120),
                ("v", 135, 30, 30),
                ("h", 135, 25, 50),
                ("v", 150, 30, 15),
                ("v", 165, 30, 15)
            ]
        else:
            self.main_title_lines = main_title_lines or []
        # text blocks to draw inside the main title box
        # each entry: tuple/list (text, x_mm, y_mm, font_name, size_pt, align)
        # or dict with keys text,x,y,font,size,align
        self.main_title_texts = main_title_texts or []
        self.additional_title_texts = additional_title_texts or []

    def draw(self, c: canvas.Canvas):
        """Draw outer border and main title box with its lines onto the canvas.

        Note: this method uses the page size stored in the instance. The
        caller should have created the canvas with the same pagesize.
        """
        page_width, page_height = self.page_width, self.page_height

        # Draw outer border rectangle inside margins
        x = self.left_border
        y = self.bottom_border
        width = page_width - self.left_border - self.right_border
        height = page_height - self.top_border - self.bottom_border

        c.setStrokeColor(self.border_color)
        c.setLineWidth(self.outer_border_thickness)
        c.rect(x, y, width, height, stroke=1, fill=0)

        # Draw main title box in right-bottom corner (inside margins)
        box_x = page_width - self.right_border - self.main_title_w
        box_y = self.bottom_border
        c.setStrokeColor(self.main_title_color)
        c.setLineWidth(self.outer_border_thickness)
        c.rect(box_x, box_y, self.main_title_w, self.main_title_h, stroke=1, fill=0)

        # Draw any configured text blocks inside the main title box
        try:
            self.draw_main_title_text(c, box_x, box_y, self.main_title_w, self.main_title_h)
        except Exception as e:
            print(f"Warning: failed to draw main title texts: {e}")

        # Draw lines defined in main_title_lines
        for entry in self.main_title_lines:
            if not entry:
                continue
            # normalize tuple length
            if len(entry) == 4:
                typ, x_mm, y_mm, length_mm = entry
                thickness_mm = None
            elif len(entry) >= 5:
                typ, x_mm, y_mm, length_mm, thickness_mm = entry[:5]
            else:
                continue

            start_x = box_x + x_mm * mm
            start_y = box_y + y_mm * mm
            lw = (thickness_mm if thickness_mm is not None else self.DEFAULT_OUTER_BORDER_THICKNESS_MM) * mm
            c.setLineWidth(lw)
            if typ.lower() == "v":
                # vertical: from (start_x, start_y) up by length
                c.line(start_x, start_y, start_x, start_y - length_mm * mm)
            else:
                # horizontal: from (start_x, start_y) right by length
                c.line(start_x, start_y, start_x + length_mm * mm, start_y)

    def draw_main_title_text(self, c: canvas.Canvas, left_x: float, bottom_y: float, box_w: float, box_h: float):
        """Draw text blocks inside the main title rectangle.

        Coordinates in the text entries are in millimetres relative to the
        rectangle's bottom-left corner. Each entry may be a tuple/list or a dict:
          (text, x_mm, y_mm, font_name, size_pt, align)
        align is one of 'left' (default), 'center', or 'right'.
        """
        if not self.main_title_texts:
            return

        for entry in self.main_title_texts + self.additional_title_texts:
            if isinstance(entry, (list, tuple)):
                text = str(entry[0])
                x_mm = float(entry[1]) if len(entry) > 1 and entry[1] is not None else 0.0
                y_mm = float(entry[2]) if len(entry) > 2 and entry[2] is not None else 0.0
                font_name = entry[3] if len(entry) > 3 else None
                size_pt = float(entry[4]) if len(entry) > 4 and entry[4] is not None else 8.0
                align = entry[5] if len(entry) > 5 else "left"
            elif isinstance(entry, dict):
                text = str(entry.get("text", ""))
                x_mm = float(entry.get("x", 0.0))
                y_mm = float(entry.get("y", 0.0))
                font_name = entry.get("font")
                size_pt = float(entry.get("size", 8.0))
                align = entry.get("align", "left")
            else:
                continue

            x_pt = left_x + x_mm * mm
            y_pt = bottom_y + y_mm * mm

            # Try to set the requested font; if it's not registered/fails, fall back to Helvetica
            try:
                if font_name:
                    c.setFont(font_name, size_pt)
                else:
                    c.setFont("Helvetica", size_pt)
            except Exception:
                c.setFont("Helvetica", size_pt)

            if align == "center":
                c.drawCentredString(x_pt, y_pt, text)
            elif align == "right":
                c.drawRightString(x_pt, y_pt, text)
            else:
                c.drawString(x_pt, y_pt, text)



class PdfFile:
    """Handles file-level operations (canvas creation, page lifecycle)."""

    def __init__(self, filename: str, pagesize):
        self.filename = filename
        self.pagesize = pagesize

    def create_canvas(self) -> canvas.Canvas:
        return canvas.Canvas(self.filename, pagesize=self.pagesize)

    def add_page(self, c: canvas.Canvas, page: PdfPage, page_width: float, page_height: float):
        # PdfPage.draw now draws using its own stored pagesize; just call draw(c)
        page.draw(c)
        c.showPage()

    def save(self, c: canvas.Canvas):
        c.save()


class PDFGenerator:
    """High-level orchestrator that composes PdfFile and PdfPage.

    This class keeps much of the original constructor/validation surface so
    existing callers can be migrated with minimal changes.
    """

    MAIN_TITLE_TEXTS = [
        ("Изм.", 5, 31, "GOST Type A", 12, "center"),
        ("Кол.уч", 15, 31, "GOST Type A", 12, "center"),
        ("Лист", 25, 31, "GOST Type A", 12, "center"),
        ("Nдок.", 35, 31, "GOST Type A", 12, "center"),
        ("Подпись", 47.5, 31, "GOST Type A", 12, "center"),
        ("Дата", 60, 31, "GOST Type A", 12, "center"),
        ("Разраб.", 1, 26, "GOST Type A", 12, "left"),
        ("Пров.", 1, 21, "GOST Type A", 12, "left"),
        ("Утв.", 1, 1, "GOST Type A", 12, "left"),
        ("Стадия", 142.5, 26, "GOST Type A", 12, "center"),
        ("Лист", 157.5, 26, "GOST Type A", 12, "center"),
        ("Листов", 175, 26, "GOST Type A", 12, "center")
    ]

    def __init__(
        self,
        filename: str = "output.pdf",
        page_format: str = "A3",
        orientation: str = "vertical",
        left_border_mm: float = 20.0,
        right_border_mm: float = 5.0,
        top_border_mm: float = 5.0,
        bottom_border_mm: float = 5.0,
        outer_border_thickness_mm: float = None,
        main_title_type: str = "1",
        main_title_lines: list | None = None,
        main_title_texts: list = MAIN_TITLE_TEXTS,
        additional_title_texts: list = None,
        border_color=colors.black,
        main_title_color=colors.black,
    ):
        self.filename = filename
        self.page_format = page_format
        self.orientation = orientation
        pdfmetrics.registerFont(TTFont("GOST Type A", "./GOST_A.ttf"))

        # Create a PdfPage which also resolves its own pagesize
        self.pdf_page = PdfPage(
            page_format=page_format,
            orientation=orientation,
            left_border_mm=left_border_mm,
            right_border_mm=right_border_mm,
            top_border_mm=top_border_mm,
            bottom_border_mm=bottom_border_mm,
            outer_border_thickness_mm=outer_border_thickness_mm
            if outer_border_thickness_mm is not None
            else PdfPage.DEFAULT_OUTER_BORDER_THICKNESS_MM,
            main_title_type=main_title_type,
            main_title_lines=main_title_lines,
            main_title_texts=main_title_texts,
            additional_title_texts=additional_title_texts,
            border_color=border_color,
            main_title_color=main_title_color,
        )

        # Use pagesize from the page object for canvas creation
        self.pagesize = self.pdf_page.pagesize
        self.page_width, self.page_height = self.pagesize

        # Compose file helper
        self.pdf_file = PdfFile(self.filename, self.pagesize)

    def create_pdf(self):
        c = self.pdf_file.create_canvas()
        self.pdf_file.add_page(c, self.pdf_page, self.page_width, self.page_height)
        self.pdf_file.save(c)


if __name__ == "__main__":
    additional_texts = [
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
    gen = PDFGenerator("A3.pdf", orientation="horizontal", additional_title_texts=additional_texts)
    gen.create_pdf()