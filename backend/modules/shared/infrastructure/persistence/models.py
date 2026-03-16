"""
Database models for floor plan management system.
Defines ORM models for projects, floor plans, rooms, and architectural elements.
"""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import declarative_base, relationship

from backend.project_codes import normalize_project_code

Base = declarative_base()


class ProjectYearCounter(Base):
    """Stores the last assigned project number for a specific year."""

    __tablename__ = "project_year_counters"

    year = Column(Integer, primary_key=True, index=True)
    last_number = Column(Integer, nullable=False, default=0)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


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
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    
    # Relationships
    floor_plans = relationship("FloorPlan", back_populates="project", cascade="all, delete-orphan")
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "project_type": self.project_type,
            "number": self.number,
            "year": self.year,
            "code": normalize_project_code(self.code),
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
    ceiling_height_mm = Column(Float, default=3000.0)
    active_signal_system_type = Column(String(32), default="non_addressable")
    pipeline_state = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    
    # Relationships
    project = relationship("Project", back_populates="floor_plans")
    walls = relationship("Wall", back_populates="floor_plan", cascade="all, delete-orphan")
    stairs = relationship("Stair", back_populates="floor_plan", cascade="all, delete-orphan")
    doors = relationship("Door", back_populates="floor_plan", cascade="all, delete-orphan")
    windows = relationship("Window", back_populates="floor_plan", cascade="all, delete-orphan")
    rooms = relationship("Room", back_populates="floor_plan", cascade="all, delete-orphan")
    dimensions = relationship("Dimension", back_populates="floor_plan", cascade="all, delete-orphan")
    fire_alarms = relationship("FireAlarm", back_populates="floor_plan", cascade="all, delete-orphan")
    zkspc_zones = relationship("ZkspcZone", back_populates="floor_plan", cascade="all, delete-orphan")
    signal_instruments = relationship("SignalInstrument", back_populates="floor_plan", cascade="all, delete-orphan")
    cable_routes = relationship("CableRoute", back_populates="floor_plan", cascade="all, delete-orphan")
    floorplan_recognition = relationship("FloorplanRecognition", back_populates="floor_plan", cascade="all, delete-orphan", uselist=False)
    
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
            "ceiling_height_mm": self.ceiling_height_mm,
            "active_signal_system_type": self.active_signal_system_type,
            "pipeline_state": self.pipeline_state,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_elements:
            data["walls"] = [w.to_dict() for w in self.walls]
            data["stairs"] = [s.to_dict() for s in self.stairs]
            data["doors"] = [d.to_dict() for d in self.doors]
            data["windows"] = [w.to_dict() for w in self.windows]
            data["rooms"] = [r.to_dict() for r in self.rooms]
            data["dimensions"] = [d.to_dict() for d in self.dimensions]
            data["fire_alarms"] = [f.to_dict() for f in self.fire_alarms]
            data["zkspc_zones"] = [z.to_dict() for z in self.zkspc_zones]
            data["signal_instruments"] = [i.to_dict() for i in self.signal_instruments]
            data["cable_routes"] = [r.to_dict() for r in self.cable_routes]
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
    length_m = Column(Float, nullable=True)
    length_source = Column(String(20), nullable=True)
    
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
            "length_m": self.length_m,
            "length_source": self.length_source,
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
    wall_id = Column(Integer, nullable=True)
    rotation_deg = Column(Float, default=0.0)
    
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
            "wall_id": self.wall_id,
            "rotation_deg": self.rotation_deg,
            "door_type": self.door_type,
            "swing_angle": self.swing_angle,
            "swing_direction": self.swing_direction,
        }


class Stair(Base):
    """Stair model - represents a stair flight on the floor plan."""
    __tablename__ = 'stairs'

    id = Column(Integer, primary_key=True, index=True)
    floor_plan_id = Column(Integer, ForeignKey('floor_plans.id'), nullable=False)

    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    width = Column(Float, nullable=False)
    height = Column(Float, nullable=False)
    rotation_deg = Column(Float, default=0.0)
    step_count = Column(Integer, default=5)
    step_axis = Column(String(20), default="horizontal")

    floor_plan = relationship("FloorPlan", back_populates="stairs")

    def to_dict(self):
        return {
            "id": self.id,
            "floor_plan_id": self.floor_plan_id,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "rotation_deg": self.rotation_deg,
            "step_count": self.step_count,
            "step_axis": self.step_axis,
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
    wall_id = Column(Integer, nullable=True)
    rotation_deg = Column(Float, default=0.0)
    
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
            "wall_id": self.wall_id,
            "rotation_deg": self.rotation_deg,
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
    length_m = Column(Float, nullable=True)
    width_m = Column(Float, nullable=True)
    
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
            "length_m": self.length_m,
            "width_m": self.width_m,
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

    def calculate_length_width(self, scale_factor: float = 1.0):
        """
        Estimate room length/width from minimum-area rotated rectangle and convert to meters.
        """
        if not self.boundary_points or len(self.boundary_points) < 3:
            self.length_m = 0.0
            self.width_m = 0.0
            return (0.0, 0.0)

        try:
            import cv2
            import numpy as np
        except Exception:
            self.length_m = None
            self.width_m = None
            return (None, None)

        points = np.array(self.boundary_points, dtype=np.float32)
        (_, _), (w_px, h_px), _ = cv2.minAreaRect(points)

        if w_px <= 0 or h_px <= 0:
            self.length_m = 0.0
            self.width_m = 0.0
            return (0.0, 0.0)

        long_px = max(float(w_px), float(h_px))
        short_px = min(float(w_px), float(h_px))
        self.length_m = long_px * scale_factor / 1000.0
        self.width_m = short_px * scale_factor / 1000.0
        return (self.length_m, self.width_m)


class Dimension(Base):
    """Dimension model - represents measurement annotations on floor plan."""
    __tablename__ = 'dimensions'
    
    id = Column(Integer, primary_key=True, index=True)
    floor_plan_id = Column(Integer, ForeignKey('floor_plans.id'), nullable=False)
    
    # Position (text label location in pixels)
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)

    # Optional links to recognized entities
    wall_id = Column(Integer, nullable=True)
    room_id = Column(Integer, nullable=True)
    
    # Dimension line endpoints (if applicable)
    line_x1 = Column(Float, nullable=True)
    line_y1 = Column(Float, nullable=True)
    line_x2 = Column(Float, nullable=True)
    line_y2 = Column(Float, nullable=True)
    
    # Measurement value
    value = Column(Float, nullable=False)  # default unit is meters for OCR pipeline
    unit = Column(String(10), default="m")
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
            "wall_id": self.wall_id,
            "room_id": self.room_id,
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
    system_type = Column(String(32), default="non_addressable")
    zkspc_zone_id = Column(Integer, ForeignKey("zkspc_zones.id"), nullable=True)
    loop_kind = Column(String(32), nullable=True)
    loop_number = Column(Integer, nullable=True)
    device_number = Column(Integer, nullable=True)
    zone = Column(String(50), nullable=True)
    address = Column(String(50), nullable=True)  # Device address on fire alarm loop
    room_id = Column(Integer, nullable=True)
    offset_left_m = Column(Float, nullable=True)
    offset_top_m = Column(Float, nullable=True)

    # Relationships
    floor_plan = relationship("FloorPlan", back_populates="fire_alarms")
    zkspc_zone = relationship("ZkspcZone", back_populates="fire_alarms")
    
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
            "system_type": self.system_type,
            "zkspc_zone_id": self.zkspc_zone_id,
            "loop_kind": self.loop_kind,
            "loop_number": self.loop_number,
            "device_number": self.device_number,
            "zone": self.zone,
            "address": self.address,
            "room_id": self.room_id,
            "offset_left_m": self.offset_left_m,
            "offset_top_m": self.offset_top_m,
        }


class ZkspcZone(Base):
    """Common fire alarm zone (ЗКСПС) definition for a floor plan."""

    __tablename__ = "zkspc_zones"

    id = Column(Integer, primary_key=True, index=True)
    floor_plan_id = Column(Integer, ForeignKey("floor_plans.id"), nullable=False)
    zone_number = Column(Integer, nullable=False, default=1)
    name = Column(String(100), nullable=True)
    area_sqm = Column(Float, nullable=True)
    room_count = Column(Integer, nullable=False, default=0)
    is_manual = Column(Boolean, default=False)
    is_locked = Column(Boolean, default=False)
    compliance_warnings = Column(JSON, nullable=True)

    floor_plan = relationship("FloorPlan", back_populates="zkspc_zones")
    room_links = relationship("ZkspcZoneRoom", back_populates="zone", cascade="all, delete-orphan")
    fire_alarms = relationship("FireAlarm", back_populates="zkspc_zone")

    def to_dict(self):
        return {
            "id": self.id,
            "floor_plan_id": self.floor_plan_id,
            "zone_number": self.zone_number,
            "name": self.name,
            "area_sqm": self.area_sqm,
            "room_count": self.room_count,
            "room_ids": [link.room_id for link in sorted(self.room_links, key=lambda item: item.room_id)],
            "is_manual": self.is_manual,
            "is_locked": self.is_locked,
            "compliance_warnings": self.compliance_warnings or [],
        }


class ZkspcZoneRoom(Base):
    """Associates rooms with a ZKSPС zone."""

    __tablename__ = "zkspc_zone_rooms"

    id = Column(Integer, primary_key=True, index=True)
    zone_id = Column(Integer, ForeignKey("zkspc_zones.id"), nullable=False)
    room_id = Column(Integer, ForeignKey("rooms.id"), nullable=False)

    zone = relationship("ZkspcZone", back_populates="room_links")
    room = relationship("Room")

    def to_dict(self):
        return {
            "id": self.id,
            "zone_id": self.zone_id,
            "room_id": self.room_id,
        }


class SignalInstrument(Base):
    """Fire alarm instrument/panel used for cable routing."""

    __tablename__ = "signal_instruments"

    id = Column(Integer, primary_key=True, index=True)
    floor_plan_id = Column(Integer, ForeignKey("floor_plans.id"), nullable=False)
    system_type = Column(String(32), nullable=False, default="non_addressable")
    instrument_type = Column(String(32), nullable=False, default="control_panel")
    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)
    name = Column(String(100), nullable=True)
    supports_cable_merge = Column(Boolean, default=False)

    floor_plan = relationship("FloorPlan", back_populates="signal_instruments")
    cable_routes = relationship("CableRoute", back_populates="instrument", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id": self.id,
            "floor_plan_id": self.floor_plan_id,
            "system_type": self.system_type,
            "instrument_type": self.instrument_type,
            "x": self.x,
            "y": self.y,
            "name": self.name,
            "supports_cable_merge": self.supports_cable_merge,
        }


class CableRoute(Base):
    """Branch-specific cable route stored as an editable orthogonal polyline."""

    __tablename__ = "cable_routes"

    id = Column(Integer, primary_key=True, index=True)
    floor_plan_id = Column(Integer, ForeignKey("floor_plans.id"), nullable=False)
    system_type = Column(String(32), nullable=False, default="non_addressable")
    instrument_id = Column(Integer, ForeignKey("signal_instruments.id"), nullable=False)
    route_kind = Column(String(32), nullable=False)
    route_number = Column(Integer, nullable=False, default=1)
    polyline_points = Column(JSON, nullable=False)
    device_ids = Column(JSON, nullable=True)
    warnings = Column(JSON, nullable=True)
    length_m = Column(Float, nullable=True)
    is_manual = Column(Boolean, default=False)

    floor_plan = relationship("FloorPlan", back_populates="cable_routes")
    instrument = relationship("SignalInstrument", back_populates="cable_routes")

    def to_dict(self):
        return {
            "id": self.id,
            "floor_plan_id": self.floor_plan_id,
            "system_type": self.system_type,
            "instrument_id": self.instrument_id,
            "route_kind": self.route_kind,
            "route_number": self.route_number,
            "polyline_points": self.polyline_points or [],
            "device_ids": self.device_ids or [],
            "warnings": self.warnings or [],
            "length_m": self.length_m,
            "is_manual": self.is_manual,
        }


class FloorplanRecognition(Base):
    """Floorplan recognition result - stores AI-recognized walls and openings."""
    __tablename__ = 'floorplan_recognitions'
    
    id = Column(Integer, primary_key=True, index=True)
    floor_plan_id = Column(Integer, ForeignKey('floor_plans.id'), nullable=False, unique=True)
    
    # Recognition result (JSON with raw output from floorplan module)
    recognition_result = Column(JSON, nullable=False)
    
    # Status tracking
    status = Column(String(20), default="completed")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    
    # Metadata
    processed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    debug_artifacts_dir = Column(String(500), nullable=True)  # Path to debug images if available
    
    # Relationships
    floor_plan = relationship("FloorPlan", back_populates="floorplan_recognition")
    
    def to_dict(self):
        return {
            "id": self.id,
            "floor_plan_id": self.floor_plan_id,
            "status": self.status,
            "recognition_result": self.recognition_result,
            "error_message": self.error_message,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "debug_artifacts_dir": self.debug_artifacts_dir,
        }


class AuditEvent(Base):
    """Structured audit trail event for critical backend operations."""

    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    event_name = Column(String(100), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)
    use_case = Column(String(100), nullable=False)
    request_id = Column(String(64), nullable=True, index=True)
    project_id = Column(Integer, nullable=True, index=True)
    floor_plan_id = Column(Integer, nullable=True, index=True)
    pipeline_step = Column(String(50), nullable=True, index=True)
    system_type = Column(String(32), nullable=True, index=True)
    payload = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "event_name": self.event_name,
            "category": self.category,
            "use_case": self.use_case,
            "request_id": self.request_id,
            "project_id": self.project_id,
            "floor_plan_id": self.floor_plan_id,
            "pipeline_step": self.pipeline_step,
            "system_type": self.system_type,
            "payload": self.payload,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
