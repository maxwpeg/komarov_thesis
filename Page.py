from consts import *
from reportlab.pdfgen import canvas


class Page:
    """Page-level configuration and drawing.

    New functional contract:
    - page_format: 'A3' or 'A4'
    - orientation: 'horizontal' or 'vertical' (A4 only allows 'vertical')
    - fixed outer border thickness 1.4 mm and margins: left 20 mm, right 5 mm, top 5 mm, bottom 5 mm
    - main_title_type: '1' or '2' (type '1' implemented with a default table and line list)
    """

    def __init__(
        self,
        page_format: tuple[float, float] = PAGESIZE_A4,
        main_title_box_type: str = "1",
        creds: dict[str, str] = DEFAULT_CREDS_DICT,
        page_number: int = 1,
        borders_mm: dict[str, float] = DEFAULT_BORDERS
    ):
        # Page size
        self.page_width, self.page_height = page_format
        # Main title box configuration
        self.main_title_box_type = main_title_box_type
        self.creds = creds.copy()
        self.page_number = page_number
        self.borders_mm = borders_mm
        self.main_title_box_x = self.page_width - self.borders_mm["right"] - MAIN_TITLE_BOX_DICT.get(
            main_title_box_type,
            MAIN_TITLE_BOX_DICT["1"]
        )[0]
        self.main_title_box_y = self.borders_mm["bottom"]

    def draw_outer_border(self, c: canvas.Canvas):
        """Draw the outer border of the page."""
        x = self.borders_mm["left"]
        y = self.borders_mm["bottom"]
        width = self.page_width - self.borders_mm["left"] - self.borders_mm["right"]
        height = self.page_height - self.borders_mm["top"] - self.borders_mm["bottom"]

        c.setStrokeColor(DEFAULT_BORDER_COLOR)
        c.setLineWidth(DEFAULT_OUTER_BORDER_THICKNESS_MM)
        c.rect(x, y, width, height, stroke=1, fill=0)


    def fit_text_in_box(
            self,
            c: canvas.Canvas,
            text: str,
            box_x_left: float, 
            box_y_bottom: float,
            box_width: float,
            box_height: float,
            align: str,
            font_size: float = DEFAULT_FONT_SIZE,
            font_name: str = DEFAULT_FONT_NAME,
            bold: bool = False,
            padding_mm: float = 0.0
            ):
        """Fit the given text inside the specified box area on the canvas."""

        if bold:
            c.setFont(font_name + " Bold", font_size)
        else:
            c.setFont(font_name, font_size)
        # Measure the text width
        text_width = c.stringWidth(text, font_name, font_size)
        if text_width + padding_mm > box_width:
            # split the text into multiple lines
            words = text.split()
            lines = []
            current_line = ""
            for word in words:
                test_line = current_line + " " + word if current_line else word
                test_line_width = c.stringWidth(test_line, font_name, font_size)
                if test_line_width + padding_mm <= box_width:
                    current_line = test_line
                else:
                    lines.append(current_line)
                    current_line = word
            if current_line:
                lines.append(current_line)
            # Draw each line
            line_height = font_size
            total_text_height = len(lines) * line_height
            start_y = box_y_bottom + (box_height - total_text_height) / 2 + (len(lines) - 1) * line_height + DEFAULT_OUTER_BORDER_THICKNESS_MM # slight adjustment for better vertical centering
            for line in lines:
                if align == CENTER:
                    c.drawCentredString(box_x_left + box_width / 2 , start_y, line)
                elif align == RIGHT:
                    c.drawRightString(box_x_left + box_width, start_y, line)
                else:
                    c.drawString(box_x_left + DEFAULT_OUTER_BORDER_THICKNESS_MM, start_y, line)
                start_y -= line_height
            
        else:
            # Text fits in one line
            y_position = box_y_bottom + (box_height - font_size) / 2 + DEFAULT_OUTER_BORDER_THICKNESS_MM # slight adjustment for better vertical centering
            if align == CENTER:
                c.drawCentredString(box_x_left + box_width / 2, y_position, text)
            elif align == RIGHT:
                c.drawRightString(box_x_left + box_width, y_position, text)
            else:
                c.drawString(box_x_left + DEFAULT_OUTER_BORDER_THICKNESS_MM, y_position, text)
    
    def draw_lines(self, c: canvas.Canvas, lines: list[tuple[str, float, float, float, float]]):
        """Draw lines on the canvas based on the provided specifications."""
        for entry in lines:
            typ, x_mm, y_mm, length_mm, thickness_mm = entry

            start_x = self.main_title_box_x + x_mm * mm
            start_y = self.main_title_box_y + y_mm * mm
        
            c.setLineWidth(thickness_mm)

            if typ.lower() == "v":
                # vertical: from (start_x, start_y) up by length
                c.line(start_x, start_y, start_x, start_y - length_mm * mm)
            else:
                # horizontal: from (start_x, start_y) right by length
                c.line(start_x, start_y, start_x + length_mm * mm, start_y)
        return
    
    def draw_texts(self, c: canvas.Canvas, texts: list[tuple[str, float, float, str]]):
        """Draw texts on the canvas based on the provided specifications."""
        for entry in texts:
            text = str(entry[0])
            x_mm = float(entry[1])
            y_mm = float(entry[2])
            align = entry[3]

            x_pt = self.main_title_box_x + x_mm * mm
            y_pt = self.main_title_box_y + y_mm * mm

            if align == "center":
                c.drawCentredString(x_pt, y_pt, text)
            elif align == "right":
                c.drawRightString(x_pt, y_pt, text)
            else:
                c.drawString(x_pt, y_pt, text)
        return
    
    def draw_main_title_box(self, c: canvas.Canvas, box_type: str):
        # TODO: remake the type 1 drawing lines using the fit_text_in_box method for better scaling
        """Draw the main title box of the page."""
        c.setStrokeColor(DEFAULT_MAIN_TITLE_COLOR)
        c.setLineWidth(DEFAULT_OUTER_BORDER_THICKNESS_MM)

        if box_type == "1":
            # Draw main rectangle
            
            c.rect(self.main_title_box_x, self.main_title_box_y, MAIN_TITLE_BOX_DICT["1"][0], MAIN_TITLE_BOX_DICT["1"][1], stroke=1, fill=0)

            # Draw lines inside the main title box
            self.draw_lines(c, MAIN_TITLE_BOX_1_LINES)
            
            # Draw text inside the main title box
            self.draw_texts(c, MAIN_TITLE_BOX_1_TEXTS)


        elif box_type == '2':
            c.rect(self.main_title_box_x, self.main_title_box_y, MAIN_TITLE_BOX_DICT["2"][0], MAIN_TITLE_BOX_DICT["2"][1], stroke=1, fill=0)

            self.draw_lines(c, MAIN_TITLE_BOX_2_LINES)
            
            for entry in MAIN_TITLE_BOX_2_TEXTS:
                self.fit_text_in_box(
                    c,
                    entry[0],
                    self.main_title_box_x + entry[1] * mm,
                    self.main_title_box_y + entry[2] * mm,
                    entry[3] * mm,
                    entry[4] * mm,
                    entry[5]
                )

        return 


    def fill_main_title_box(self, c: canvas.Canvas, box_type: str):
        """Fill in the main title box with project credentials."""
        if not str(self.creds.get("Sheet Number", "")).strip():
            self.creds["Sheet Number"] = str(self.page_number)
        fillings = MAIN_TITLE_BOX_1_FILLINGS_POSITIONINGS if box_type == "1" else MAIN_TITLE_BOX_2_FILLINGS_POSITIONINGS
        for key, val in fillings.items():
            x_mm, y_mm, width_mm, height_mm, align = val
            text = self.creds.get(key, "")
            self.fit_text_in_box(
                c,
                text,
                self.main_title_box_x + x_mm * mm,
                self.main_title_box_y + y_mm * mm,
                width_mm * mm,
                height_mm * mm,
                align
            )


    def draw(self, c: canvas.Canvas):
        """Draw outer border and main title box with its lines onto the canvas.

        Note: this method uses the page size stored in the instance. The
        caller should have created the canvas with the same pagesize.
        """
        c.setPageSize((self.page_width, self.page_height))
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        # Draw outer border rectangle inside margins
        self.draw_outer_border(c)

        if self.page_number > 0:
        # Draw main title box in right-bottom corner (inside margins)
            self.draw_main_title_box(c, self.main_title_box_type)
        
            self.fill_main_title_box(c, self.main_title_box_type)

            c.showPage()
        return
