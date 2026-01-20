"""
PDF generation service integrating existing Page, Project, TitlePage classes.
"""
import datetime
import os
import sys
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from PIL import Image
import io

# Add parent directory to path to import existing classes
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from Page import Page
from TitlePage import TitlePage
from Project import Project as PDFProject
from DrawingPage import DrawingPage
from consts import *


class FloorPlanPDFGenerator:
    """Generate fire alarm PDFs from floor plan data."""
    
    def __init__(self, project_data: dict, floor_plans_data: list):
        """
        Initialize PDF generator.
        
        Args:
            project_data: Project information dictionary
            floor_plans_data: List of floor plan data with rooms and fire alarms
        """
        self.project_data = project_data
        self.floor_plans_data = floor_plans_data
    
    def create_pdf(self, output_path: str = None) -> str:
        """
        Generate complete PDF with title pages and floor plan drawings.
        
        Args:
            output_path: Optional output file path
        
        Returns:
            Path to generated PDF
        """
        # Prepare credentials dictionary
        creds = {
            "Contractor": self.project_data.get("contractor", DEFAULT_CONTRACTOR_NAME),
            "Engineer": self.project_data.get("engineer", DEFAULT_ENGINEER_NAME),
            "CPE": self.project_data.get("cpe", DEFAULT_CPE_NAME),
            "Checker": self.project_data.get("checker", DEFAULT_CHECKER_NAME),
            "Facility": self.project_data.get("facility", DEFAULT_FACILITY_NAME),
            "Facility Address": self.project_data.get("facility_address", ""),
            "Project Description": self.project_data.get("project_description", DEFAULT_PROJECT_DESCRIPTION),
            "Stage": self.project_data.get("stage", DEFAULT_STAGE),
            "Project Code": self.project_data.get("code", ""),
        }
        
        # Create PDF using existing Project class
        project = PDFProject(
            project_type=self.project_data.get("project_type", "ПС"),
            number=self.project_data.get("number", 1),
            year=self.project_data.get("year", datetime.datetime.now().year),
            creds=creds,
            number_of_floors=len(self.floor_plans_data)
        )
        
        # Add title pages
        project.add_title_page(signed=False)
        project.add_title_page(signed=True)
        
        # Add floor plan pages
        for floor_plan_data in self.floor_plans_data:
            self._add_floor_plan_page(project, floor_plan_data, creds)
        
        # Save PDF
        project.save()
        
        # Return the generated filename
        return project._c._filename
    
    def _add_floor_plan_page(self, project: PDFProject, floor_plan_data: dict, creds: dict):
        """
        Add a floor plan drawing page to the project.
        
        Args:
            project: PDFProject instance
            floor_plan_data: Floor plan data including image, rooms, fire alarms
            creds: Credentials dictionary
        """
        # Create a drawing page
        page = DrawingPage(
            page_format=PAGESIZE_A3_LANDSCAPE,  # Use A3 landscape for better space
            page_number=project.number_of_pages + 1,
            creds=creds,
            main_title_box_type="1"
        )
        
        # Calculate drawing area
        drawing_x = page.borders_mm["left"]
        drawing_y = page.borders_mm["bottom"] + MAIN_TITLE_BOX_DICT["1"][1] + 5 * mm
        drawing_width = page.page_width - page.borders_mm["left"] - page.borders_mm["right"]
        drawing_height = (page.page_height - page.borders_mm["top"] - 
                         page.borders_mm["bottom"] - MAIN_TITLE_BOX_DICT["1"][1] - 10 * mm)
        
        # Draw the page structure
        project._c.setPageSize((page.page_width, page.page_height))
        page.draw(project._c)
        
        # Add floor plan image if exists
        if floor_plan_data.get("original_image_path"):
            self._draw_floor_plan_image(
                project._c,
                floor_plan_data["original_image_path"],
                drawing_x, drawing_y, drawing_width, drawing_height
            )
        
        # Draw rooms
        self._draw_rooms(
            project._c,
            floor_plan_data.get("rooms", []),
            drawing_x, drawing_y,
            floor_plan_data.get("image_width", 1),
            floor_plan_data.get("image_height", 1),
            drawing_width, drawing_height
        )
        
        # Draw fire alarms
        self._draw_fire_alarms(
            project._c,
            floor_plan_data.get("fire_alarms", []),
            drawing_x, drawing_y,
            floor_plan_data.get("image_width", 1),
            floor_plan_data.get("image_height", 1),
            drawing_width, drawing_height
        )
        
        # Draw dimensions
        self._draw_dimensions(
            project._c,
            floor_plan_data.get("dimensions", []),
            drawing_x, drawing_y,
            floor_plan_data.get("image_width", 1),
            floor_plan_data.get("image_height", 1),
            drawing_width, drawing_height
        )
        
        project._c.showPage()
        project.number_of_pages += 1
    
    def _draw_floor_plan_image(
        self,
        c: canvas.Canvas,
        image_path: str,
        x: float, y: float,
        width: float, height: float
    ):
        """Draw the floor plan image scaled to fit the drawing area."""
        try:
            img = Image.open(image_path)
            
            # Convert to grayscale (black and white)
            img = img.convert('L')
            
            img_width, img_height = img.size
            
            # Calculate scaling to fit
            scale_x = width / img_width
            scale_y = height / img_height
            scale = min(scale_x, scale_y)
            
            scaled_width = img_width * scale
            scaled_height = img_height * scale
            
            # Center the image
            offset_x = (width - scaled_width) / 2
            offset_y = (height - scaled_height) / 2
            
            # Save converted image to BytesIO for drawing
            img_buffer = io.BytesIO()
            img.save(img_buffer, format='PNG')
            img_buffer.seek(0)
            
            c.drawImage(
                img_buffer,
                x + offset_x, y + offset_y,
                width=scaled_width,
                height=scaled_height,
                preserveAspectRatio=True
            )
        except Exception as e:
            print(f"Error drawing floor plan image: {e}")
    
    def _draw_rooms(
        self,
        c: canvas.Canvas,
        rooms: list,
        offset_x: float, offset_y: float,
        orig_width: float, orig_height: float,
        draw_width: float, draw_height: float
    ):
        """Draw room boundaries and labels."""
        scale_x = draw_width / orig_width
        scale_y = draw_height / orig_height
        scale = min(scale_x, scale_y)
        
        c.setStrokeColor(colors.purple)
        c.setLineWidth(0.5 * mm)
        c.setFont(DEFAULT_FONT_NAME, 10)
        
        for index, room in enumerate(rooms, start=1):
            if not room.get("boundary_points"):
                continue
            
            # Draw boundary
            points = room["boundary_points"]
            if len(points) < 3:
                continue
            
            # Scale and offset points
            path = c.beginPath()
            first_point = points[0]
            path.moveTo(
                offset_x + first_point[0] * scale,
                offset_y + first_point[1] * scale
            )
            
            for point in points[1:]:
                path.lineTo(
                    offset_x + point[0] * scale,
                    offset_y + point[1] * scale
                )
            
            path.close()
            c.drawPath(path, stroke=1, fill=0)
            
            # Draw room label with area
            if room.get("center_x") and room.get("center_y"):
                cx = offset_x + room["center_x"] * scale
                cy = offset_y + room["center_y"] * scale
                
                label = room.get("name", f"Помещение {index}")
                if room.get("area_sqm"):
                    label += f"\n{room['area_sqm']:.2f} м²"
                
                c.setFillColor(colors.purple)
                c.drawCentredString(cx, cy, label)
    
    def _draw_fire_alarms(
        self,
        c: canvas.Canvas,
        fire_alarms: list,
        offset_x: float, offset_y: float,
        orig_width: float, orig_height: float,
        draw_width: float, draw_height: float
    ):
        """Draw fire alarm devices."""
        scale_x = draw_width / orig_width
        scale_y = draw_height / orig_height
        scale = min(scale_x, scale_y)
        
        c.setStrokeColor(colors.red)
        c.setFillColor(colors.red)
        c.setFont(DEFAULT_FONT_NAME, 8)
        
        for alarm in fire_alarms:
            x = offset_x + alarm["x"] * scale
            y = offset_y + alarm["y"] * scale
            
            # Draw device symbol (circle for detectors)
            radius = 3 * mm
            c.circle(x, y, radius, stroke=1, fill=1)
            
            # Draw device label
            device_type = alarm.get("device_type", "")
            if device_type:
                c.setFillColor(colors.black)
                c.drawCentredString(x, y - radius - 3 * mm, device_type[:4].upper())
    
    def _draw_dimensions(
        self,
        c: canvas.Canvas,
        dimensions: list,
        offset_x: float, offset_y: float,
        orig_width: float, orig_height: float,
        draw_width: float, draw_height: float
    ):
        """Draw dimension annotations."""
        scale_x = draw_width / orig_width
        scale_y = draw_height / orig_height
        scale = min(scale_x, scale_y)
        
        c.setFillColor(colors.black)
        c.setFont(DEFAULT_FONT_NAME, 8)
        
        for dim in dimensions:
            x = offset_x + dim["x"] * scale
            y = offset_y + dim["y"] * scale
            
            text = dim.get("text", f"{dim.get('value', 0)} {dim.get('unit', 'mm')}")
            c.drawString(x, y, text)


def generate_project_pdf(project_data: dict, floor_plans_data: list, output_dir: str = "outputs") -> str:
    """
    Convenience function to generate PDF for a project.
    
    Args:
        project_data: Project dictionary from database
        floor_plans_data: List of floor plan dictionaries with all elements
        output_dir: Output directory for PDF
    
    Returns:
        Path to generated PDF file
    """
    os.makedirs(output_dir, exist_ok=True)
    
    generator = FloorPlanPDFGenerator(project_data, floor_plans_data)
    pdf_path = generator.create_pdf()
    
    # Move to output directory if needed
    if output_dir and not pdf_path.startswith(output_dir):
        import shutil
        new_path = os.path.join(output_dir, os.path.basename(pdf_path))
        shutil.move(pdf_path, new_path)
        return new_path
    
    return pdf_path
