from .Page import Page
from .consts import *
from reportlab.pdfgen import canvas
import datetime


class TitlePage(Page):
    """TitlePage-level configuration and drawing."""
    
    def __init__(
        self,
        signed: bool = False,
        creds: dict[str, str] = DEFAULT_CREDS_DICT,
    ):
        super().__init__(
            main_title_box_type="0",
            creds=creds,
            page_number=0
        )

        self.signed = signed
    
    def draw(self, c: canvas.Canvas, year: int = datetime.datetime.now().year):
        """Draw the title page on the given canvas."""
        super().draw(c)

        # Add contractor name centered at the top
        self.fit_text_in_box(
            c, 
            self.creds.get("Contractor", ""), 
            self.borders_mm["left"], 
            self.page_height - self.borders_mm["top"] - 25 * mm, 
            self.page_width - self.borders_mm["left"] - self.borders_mm["right"],
            25 * mm,
            CENTER,
            font_size=DEFAULT_TITLE_FONT_SIZE,
            bold=True
        )

        # Add "Main Set of Working Drawings" in the center of the page
        self.fit_text_in_box(
            c,
            MAIN_SET_OF_WORKING_DRAWINGS_STR,
            self.borders_mm["left"],
            self.borders_mm["bottom"],
            self.page_width - self.borders_mm["left"] - self.borders_mm["right"],
            self.page_height - self.borders_mm["top"] - self.borders_mm["bottom"] - DEFAULT_TITLE_FONT_SIZE * .5,
            CENTER,
            font_size=DEFAULT_TITLE_FONT_SIZE,
            bold=True
        )

        # Add facility name centered in the upper half
        self.fit_text_in_box(
            c,
            self.creds.get("Facility", ""),
            self.borders_mm["left"],
            self.borders_mm["bottom"] + (self.page_height - self.borders_mm["top"] - self.borders_mm["bottom"]) *.5,
            self.page_width - self.borders_mm["left"] - self.borders_mm["right"],
            (self.page_height - self.borders_mm["top"] - self.borders_mm["bottom"]) *.5,
            CENTER,
            font_size=DEFAULT_TITLE_FONT_SIZE,
            bold=True
        )

        # Add project description centered lower 3/4
        self.fit_text_in_box(
            c,
            self.creds.get("Project Description", ""),
            self.borders_mm["left"],
            self.borders_mm["bottom"],
            self.page_width - self.borders_mm["left"] - self.borders_mm["right"],
            (self.page_height - self.borders_mm["top"] - self.borders_mm["bottom"]) *.75,
            CENTER,
            font_size=DEFAULT_TITLE_FONT_SIZE,
            bold=True,
            padding_mm=20.0 * mm
        )

        # Add project code centered at the lower half
        self.fit_text_in_box(
            c,
            self.creds.get("Project Code", ""),
            self.borders_mm["left"],
            self.borders_mm["bottom"],
            self.page_width - self.borders_mm["left"] - self.borders_mm["right"],
            (self.page_height - self.borders_mm["top"] - self.borders_mm["bottom"]) *.5,
            CENTER,
            font_size=DEFAULT_TITLE_FONT_SIZE,
            bold=True
        )

        # Add year centered at the very bottom
        self.fit_text_in_box(
            c,
            str(year) + " г.",
            self.borders_mm["left"],
            self.borders_mm["bottom"] + 8 * mm,
            self.page_width - self.borders_mm["left"] - self.borders_mm["right"],
            8 * mm,
            CENTER,
            font_size=DEFAULT_TITLE_FONT_SIZE,
            bold=True
        )

        if self.signed:
            self.fit_text_in_box(
                c,
                CEO_STR + GAP3_STR + SIGN_LINE_STR + GAP3_STR + self.creds.get("Checker", ""),
                self.borders_mm["left"],
                self.borders_mm["bottom"] + 8 * mm,
                self.page_width - self.borders_mm["left"] - self.borders_mm["right"],
                (self.page_height - self.borders_mm["top"] - self.borders_mm["bottom"]) *.25,
                CENTER,
                font_size=DEFAULT_FONT_SIZE,
            )

            self.fit_text_in_box(
                c,
                CPE_STR + GAP3_STR + SIGN_LINE_STR + GAP3_STR + self.creds.get("CPE", ""),
                self.borders_mm["left"],
                self.borders_mm["bottom"],
                self.page_width - self.borders_mm["left"] - self.borders_mm["right"],
                (self.page_height - self.borders_mm["top"] - self.borders_mm["bottom"]) *.25,
                CENTER,
                font_size=DEFAULT_FONT_SIZE,
            )
        c.showPage()