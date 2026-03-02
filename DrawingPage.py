from Page import Page
from reportlab.lib import colors
from consts import *


class DrawingPage(Page):
    """DrawingPage-level configuration and drawing."""
    
    def __init__(
        self,
        page_format: tuple[float, float] = PAGESIZE_A4,
        main_title_box_type: str = "1",
        creds: dict[str, str] = DEFAULT_CREDS_DICT,
        page_number: int = 1,
        borders_mm: dict[str, float] = DEFAULT_BORDERS,
        floor_plan_data: dict = None,
        title: str = ""
    ):
        super().__init__(page_format, main_title_box_type, creds, page_number, borders_mm)
        self.floor_plan_data = floor_plan_data
        self.title = title
        
        # Вычисляем область для рисования
        self.drawing_x = self.borders_mm["left"]
        self.drawing_y = self.borders_mm["bottom"] + MAIN_TITLE_BOX_DICT["1"][1] + 5 * mm
        self.drawing_width = self.page_width - self.borders_mm["left"] - self.borders_mm["right"]
        self.drawing_height = (self.page_height - self.borders_mm["top"] - 
                              self.borders_mm["bottom"] - MAIN_TITLE_BOX_DICT["1"][1] - 10 * mm)
    
    def draw_floor_plan_elements(self, c, floor_plan_data: dict):
        """Отрисовывает элементы плана этажа (стены, двери, окна) на PDF."""
        if not floor_plan_data:
            return
        
        # Вычисляем масштаб на основе размеров изображения
        img_width = floor_plan_data.get('image_width', 800)
        img_height = floor_plan_data.get('image_height', 600)
        
        scale_x = self.drawing_width / img_width
        scale_y = self.drawing_height / img_height
        scale = min(scale_x, scale_y)
        
        scaled_width = img_width * scale
        scaled_height = img_height * scale
        
        # Центрируем чертеж
        offset_x = self.drawing_x + (self.drawing_width - scaled_width) / 2
        offset_y = self.drawing_y + (self.drawing_height - scaled_height) / 2
        
        # Рисуем стены
        walls = floor_plan_data.get('walls', [])
        if walls:
            c.setStrokeColor(colors.black)
            c.setLineWidth(2.0)
            
            for wall in walls:
                x1 = offset_x + wall['x1'] * scale
                y1 = offset_y + wall['y1'] * scale
                x2 = offset_x + wall['x2'] * scale
                y2 = offset_y + wall['y2'] * scale
                c.line(x1, y1, x2, y2)
        
        # Рисуем двери
        doors = floor_plan_data.get('doors', [])
        if doors:
            c.setStrokeColor(colors.blue)
            c.setLineWidth(1.5)
            
            for door in doors:
                x = offset_x + door['x'] * scale
                y = offset_y + door['y'] * scale
                width = door.get('width', 20) * scale
                height = door.get('height', 10) * scale
                rotation = door.get('rotation', 0)
                
                c.saveState()
                c.translate(x, y)
                c.rotate(rotation)
                c.rect(0, 0, width, height, stroke=1, fill=0)
                c.restoreState()
        
        # Рисуем окна
        windows = floor_plan_data.get('windows', [])
        if windows:
            c.setStrokeColor(colors.green)
            c.setLineWidth(1.5)
            
            for window in windows:
                x = offset_x + window['x'] * scale
                y = offset_y + window['y'] * scale
                width = window.get('width', 20) * scale
                height = window.get('height', 5) * scale
                rotation = window.get('rotation', 0)
                
                c.saveState()
                c.translate(x, y)
                c.rotate(rotation)
                c.rect(0, 0, width, height, stroke=1, fill=0)
                c.line(0, 0, width, height)
                c.line(width, 0, 0, height)
                c.restoreState()
        
        # Рисуем пожарные извещатели
        fire_alarms = floor_plan_data.get('fire_alarms', [])
        if fire_alarms:
            c.setStrokeColor(colors.red)
            c.setFillColor(colors.red)
            
            for alarm in fire_alarms:
                x = offset_x + alarm['x'] * scale
                y = offset_y + alarm['y'] * scale
                c.circle(x, y, 2 * mm, stroke=1, fill=1)
    
    def draw(self, c):
        """Draw page with floor plan elements."""
        c.setPageSize((self.page_width, self.page_height))
        c.setFont(DEFAULT_FONT_NAME, DEFAULT_FONT_SIZE)
        
        # Draw outer border
        self.draw_outer_border(c)
        
        # Draw title if provided
        if self.title:
            self.fit_text_in_box(
                c,
                self.title,
                self.drawing_x,
                self.page_height - self.borders_mm["top"] - 15 * mm,
                self.drawing_width,
                10 * mm,
                CENTER,
                font_size=14,
                bold=True
            )
        
        # Draw floor plan elements
        if self.floor_plan_data:
            self.draw_floor_plan_elements(c, self.floor_plan_data)
        
        # Draw main title box
        if self.page_number > 0:
            self.draw_main_title_box(c, self.main_title_box_type)
            self.fill_main_title_box(c, self.main_title_box_type)
        
        c.showPage()
