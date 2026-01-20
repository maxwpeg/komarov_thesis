"""
Database models for floor plan management system.
Defines ORM models for projects, floor plans, rooms, and architectural elements.
"""
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import json

Base = declarative_base()


class Project(Base):
    """Project model - top-level container for floor plans."""
    __tablename__ = 'projects'
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    project_type = Column(String(50), default="ПС")
    number = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    code = Column(String(100), unique=True, nullable=False)  # e.g., "РП-ЗК-102/26-ПС"
    
    # Credentials
    contractor = Column(String(255), nullable=False)
    engineer = Column(String(255), nullable=False)
    cpe = Column(String(255), nullable=False)
    checker = Column(String(255), nullable=False)
    facility = Column(String(255), nullable=False)
    facility_address = Column(Text, nullable=True)
    project_description = Column(Text, nullable=True)
    stage = Column(String(50), default="«Р»")
    
    number_of_floors = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    floor_plans = relationship("FloorPlan", back_populates="project", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "project_type": self.project_type,
            "number": self.number,
            "year": self.year,
            "code": self.code,
            "contractor": self.contractor,
            "engineer": self.engineer,
            "cpe": self.cpe,
            "checker": self.checker,
            "facility": self.facility,
            "facility_address": self.facility_address,
            "project_description": self.project_description,
            "stage": self.stage,
            "number_of_floors": self.number_of_floors,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class FloorPlan(Base):
    """Floor plan model - represents a single floor with architectural elements."""
    __tablename__ = 'floor_plans'
    
    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False)
    floor_number = Column(Integer, nullable=False)
    name = Column(String(255), nullable=True)  # e.g., "First Floor", "Ground Level"
    
    # Image data
    original_image_path = Column(String(500), nullable=True)
    processed_image_path = Column(String(500), nullable=True)
    image_width = Column(Integer, nullable=True)
    image_height = Column(Integer, nullable=True)
    
    # Scale information (mm per pixel)
    scale_factor = Column(Float, default=1.0)  # Real world mm per pixel
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project = relationship("Project", back_populates="floor_plans")
    walls = relationship("Wall", back_populates="floor_plan", cascade="all, delete-orphan")
    doors = relationship("Door", back_populates="floor_plan", cascade="all, delete-orphan")
    windows = relationship("Window", back_populates="floor_plan", cascade="all, delete-orphan")
    rooms = relationship("Room", back_populates="floor_plan", cascade="all, delete-orphan")
    dimensions = relationship("Dimension", back_populates="floor_plan", cascade="all, delete-orphan")
    fire_alarms = relationship("FireAlarm", back_populates="floor_plan", cascade="all, delete-orphan")
    
    def to_dict(self, include_elements=False):
        data = {
            "id": self.id,
            "project_id": self.project_id,
            "floor_number": self.floor_number,
            "name": self.name,
            "original_image_path": self.original_image_path,
            "processed_image_path": self.processed_image_path,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "scale_factor": self.scale_factor,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_elements:
            data["walls"] = [w.to_dict() for w in self.walls]
            data["doors"] = [d.to_dict() for d in self.doors]
            data["windows"] = [w.to_dict() for w in self.windows]
            data["rooms"] = [r.to_dict() for r in self.rooms]
            data["dimensions"] = [d.to_dict() for d in self.dimensions]
            data["fire_alarms"] = [f.to_dict() for f in self.fire_alarms]
        return data


class Wall(Base):
    """Wall model - represents structural walls."""
    __tablename__ = 'walls'
    
    id = Column(Integer, primary_key=True, index=True)
    floor_plan_id = Column(Integer, ForeignKey('floor_plans.id'), nullable=False)
    
    # Coordinates (in pixels on the floor plan image)
    x1 = Column(Float, nullable=False)
    y1 = Column(Float, nullable=False)
    x2 = Column(Float, nullable=False)
    y2 = Column(Float, nullable=False)
    
    # Wall properties
    thickness = Column(Float, default=200.0)  # mm
    is_load_bearing = Column(Boolean, default=False)
    material = Column(String(100), nullable=True)
    
    # Relationships
    floor_plan = relationship("FloorPlan", back_populates="walls")
    
    def to_dict(self):
        return {
            "id": self.id,
            "floor_plan_id": self.floor_plan_id,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
            "thickness": self.thickness,
            "is_load_bearing": self.is_load_bearing,
            "material": self.material,
        }


class Door(Base):
    """Door model - represents doors in the floor plan."""
    __tablename__ = 'doors'
    
    id = Column(Integer, primary_key=True, index=True)
    floor_plan_id = Column(Integer, ForeignKey('floor_plans.id'), nullable=False)
    
    # Position and dimensions (bounding box in pixels)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    width = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    
    # Door properties
    door_type = Column(String(50), default="standard")  # standard, fire, emergency, sliding
    swing_angle = Column(Float, default=90.0)  # degrees
    swing_direction = Column(String(20), nullable=True)  # left, right, inward, outward
    
    # Relationships
    floor_plan = relationship("FloorPlan", back_populates="doors")
    
    def to_dict(self):
        return {
            "id": self.id,
            "floor_plan_id": self.floor_plan_id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "door_type": self.door_type,
            "swing_angle": self.swing_angle,
            "swing_direction": self.swing_direction,
        }


class Window(Base):
    """Window model - represents windows in the floor plan."""
    __tablename__ = 'windows'
    
    id = Column(Integer, primary_key=True, index=True)
    floor_plan_id = Column(Integer, ForeignKey('floor_plans.id'), nullable=False)
    
    # Position and dimensions (bounding box in pixels)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    width = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    
    # Window properties
    window_type = Column(String(50), default="standard")  # standard, bay, sliding
    
    # Relationships
    floor_plan = relationship("FloorPlan", back_populates="windows")
    
    def to_dict(self):
        return {
            "id": self.id,
            "floor_plan_id": self.floor_plan_id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "window_type": self.window_type,
        }


class Room(Base):
    """Room model - represents individual rooms with calculated areas."""
    __tablename__ = 'rooms'
    
    id = Column(Integer, primary_key=True, index=True)
    floor_plan_id = Column(Integer, ForeignKey('floor_plans.id'), nullable=False)
    
    # Room identification
    name = Column(String(255), nullable=True)  # e.g., "Kitchen", "Bedroom 1"
    room_type = Column(String(100), nullable=True)  # bedroom, kitchen, bathroom, office, etc.
    room_number = Column(String(50), nullable=True)  # e.g., "1.01"
    
    # Geometry (polygon vertices in pixels, stored as JSON)
    boundary_points = Column(JSON, nullable=True)  # [[x1, y1], [x2, y2], ...]
    
    # Calculated properties
    area_sqm = Column(Float, nullable=True)  # Square meters
    perimeter_m = Column(Float, nullable=True)  # Meters
    
    # Center point for labeling
    center_x = Column(Float, nullable=True)
    center_y = Column(Float, nullable=True)
    
    # Relationships
    floor_plan = relationship("FloorPlan", back_populates="rooms")
    
    def to_dict(self):
        return {
            "id": self.id,
            "floor_plan_id": self.floor_plan_id,
            "name": self.name,
            "room_type": self.room_type,
            "room_number": self.room_number,
            "boundary_points": self.boundary_points,
            "area_sqm": self.area_sqm,
            "perimeter_m": self.perimeter_m,
            "center_x": self.center_x,
            "center_y": self.center_y,
        }
    
    def calculate_area(self, scale_factor: float = 1.0):
        """Calculate room area using shoelace formula.
        
        Args:
            scale_factor: mm per pixel conversion factor
        """
        if not self.boundary_points or len(self.boundary_points) < 3:
            self.area_sqm = 0.0
            return 0.0
        
        # Shoelace formula for polygon area
        points = self.boundary_points
        n = len(points)
        area_pixels = 0.0
        
        for i in range(n):
            j = (i + 1) % n
            area_pixels += points[i][0] * points[j][1]
            area_pixels -= points[j][0] * points[i][1]
        
        area_pixels = abs(area_pixels) / 2.0
        
        # Convert pixels² to mm² then to m²
        area_mm2 = area_pixels * (scale_factor ** 2)
        self.area_sqm = area_mm2 / 1_000_000.0  # mm² to m²
        
        return self.area_sqm
    
    def calculate_perimeter(self, scale_factor: float = 1.0):
        """Calculate room perimeter.
        
        Args:
            scale_factor: mm per pixel conversion factor
        """
        if not self.boundary_points or len(self.boundary_points) < 2:
            self.perimeter_m = 0.0
            return 0.0
        
        points = self.boundary_points
        n = len(points)
        perimeter_pixels = 0.0
        
        for i in range(n):
            j = (i + 1) % n
            dx = points[j][0] - points[i][0]
            dy = points[j][1] - points[i][1]
            perimeter_pixels += (dx**2 + dy**2) ** 0.5
        
        # Convert pixels to mm then to m
        perimeter_mm = perimeter_pixels * scale_factor
        self.perimeter_m = perimeter_mm / 1000.0  # mm to m
        
        return self.perimeter_m
    
    def calculate_center(self):
        """Calculate centroid of the room polygon."""
        if not self.boundary_points or len(self.boundary_points) < 3:
            self.center_x = 0.0
            self.center_y = 0.0
            return (0.0, 0.0)
        
        points = self.boundary_points
        n = len(points)
        
        # Centroid formula for polygon
        cx = sum(p[0] for p in points) / n
        cy = sum(p[1] for p in points) / n
        
        self.center_x = cx
        self.center_y = cy
        
        return (cx, cy)


class Dimension(Base):
    """Dimension model - represents measurement annotations on floor plan."""
    __tablename__ = 'dimensions'
    
    id = Column(Integer, primary_key=True, index=True)
    floor_plan_id = Column(Integer, ForeignKey('floor_plans.id'), nullable=False)
    
    # Position (text label location in pixels)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    
    # Dimension line endpoints (if applicable)
    line_x1 = Column(Float, nullable=True)
    line_y1 = Column(Float, nullable=True)
    line_x2 = Column(Float, nullable=True)
    line_y2 = Column(Float, nullable=True)
    
    # Measurement value
    value = Column(Float, nullable=False)  # in mm
    unit = Column(String(10), default="mm")
    text = Column(String(50), nullable=True)  # Original OCR text
    
    # Dimension type
    dimension_type = Column(String(50), default="linear")  # linear, angular, area
    
    # Relationships
    floor_plan = relationship("FloorPlan", back_populates="dimensions")
    
    def to_dict(self):
        return {
            "id": self.id,
            "floor_plan_id": self.floor_plan_id,
            "x": self.x,
            "y": self.y,
            "line_x1": self.line_x1,
            "line_y1": self.line_y1,
            "line_x2": self.line_x2,
            "line_y2": self.line_y2,
            "value": self.value,
            "unit": self.unit,
            "text": self.text,
            "dimension_type": self.dimension_type,
        }


class FireAlarm(Base):
    """Fire alarm device model - represents fire detection/alarm equipment."""
    __tablename__ = 'fire_alarms'
    
    id = Column(Integer, primary_key=True, index=True)
    floor_plan_id = Column(Integer, ForeignKey('floor_plans.id'), nullable=False)
    
    # Position (in pixels)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    
    # Device properties
    device_type = Column(String(100), nullable=False)  # smoke_detector, heat_detector, manual_call_point, sounder, etc.
    device_model = Column(String(100), nullable=True)
    coverage_radius = Column(Float, nullable=True)  # Coverage radius in mm
    
    # Installation details
    mounting_height = Column(Float, nullable=True)  # Height in mm
    zone = Column(String(50), nullable=True)
    address = Column(String(50), nullable=True)  # Device address on fire alarm loop
    
    # Relationships
    floor_plan = relationship("FloorPlan", back_populates="fire_alarms")
    
    def to_dict(self):
        return {
            "id": self.id,
            "floor_plan_id": self.floor_plan_id,
            "x": self.x,
            "y": self.y,
            "device_type": self.device_type,
            "device_model": self.device_model,
            "coverage_radius": self.coverage_radius,
            "mounting_height": self.mounting_height,
            "zone": self.zone,
            "address": self.address,
        }
