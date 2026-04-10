"""Integration layer between floorplan recognition and backend models."""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from floorplan import FloorPlanProcessor, OpeningType, ProcessingResult

from backend.models import Door as DoorModel
from backend.models import Dimension as DimensionModel
from backend.models import Room as RoomModel
from backend.models import Wall as WallModel
from backend.models import Window as WindowModel


class FloorplanRecognitionIntegrator:
    """
    Integration layer for floorplan recognition.
    Converts recognition results to database models.
    """
    
    def __init__(self, debug: bool = False):
        self.processor = FloorPlanProcessor(debug=debug)
        self.debug = debug
    
    def recognize_floor_plan(
        self,
        image_path: str,
        floor_plan_id: int = None,
        debug_dir: Optional[str] = None
    ) -> Tuple[ProcessingResult, Dict]:
        """
        Recognize floor plan from image.
        
        Args:
            image_path: Path to floor plan image
            floor_plan_id: Optional floor plan ID for logging
            debug_dir: Optional directory to save debug images
            
        Returns:
            Tuple of (ProcessingResult, metadata dict with artifact paths)
        """
        result = self.processor.process(image_path, debug_dir=debug_dir)
        metadata = {
            "success": True,
            "error": None,
            "debug_dir": debug_dir,
            "walls_count": len(result.walls),
            "openings_count": len(result.openings),
        }
        return result, metadata
    
    def convert_to_database_models(
        self,
        result: ProcessingResult,
        floor_plan_id: int,
        scale_factor_mm_per_px: float = 1.0,
    ) -> Tuple[List[WallModel], List[DoorModel], List[WindowModel], List[RoomModel], List[DimensionModel]]:
        """
        Convert recognition results to database models.
        
        Args:
            result: ProcessingResult from floorplan module
            floor_plan_id: ID of the floor plan in the database
            
        Returns:
            Tuple of (walls, doors, windows, rooms, dimensions) lists of database models
        """
        walls = []
        doors = []
        windows = []
        rooms = []
        dimensions = []
        
        # Convert walls
        for wall in result.walls:
            pixel_length = math.hypot(wall.midline.x2 - wall.midline.x1, wall.midline.y2 - wall.midline.y1)
            db_wall = WallModel(
                floor_plan_id=floor_plan_id,
                x1=float(wall.midline.x1),  # Convert to Python float
                y1=float(wall.midline.y1),
                x2=float(wall.midline.x2),
                y2=float(wall.midline.y2),
                thickness=float(wall.thickness_px * scale_factor_mm_per_px),  # store wall thickness in mm
                material=f"detected_wall_{wall.id}",  # Mark as auto-detected
                is_load_bearing=False,  # Default - can be determined by user later
                length_m=float(pixel_length * scale_factor_mm_per_px / 1000.0),
                length_source="derived",
            )
            walls.append(db_wall)
        
        # Convert openings (doors and windows)
        for opening in result.openings:
            x1, y1, x2, y2 = opening.bbox
            width = float(x2 - x1)
            height = float(y2 - y1)
            x = float(x1)  # Use top-left corner
            y = float(y1)
            
            if opening.type == OpeningType.DOOR:
                db_door = DoorModel(
                    floor_plan_id=floor_plan_id,
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    wall_id=int(opening.wall_id) if opening.wall_id is not None else None,
                    door_type="standard",
                    swing_angle=90.0,
                    swing_direction=None,
                )
                doors.append(db_door)
            
            elif opening.type == OpeningType.WINDOW:
                db_window = WindowModel(
                    floor_plan_id=floor_plan_id,
                    x=x,
                    y=y,
                    width=width,
                    height=height,
                    wall_id=int(opening.wall_id) if opening.wall_id is not None else None,
                    window_type="standard",
                )
                windows.append(db_window)

        # Convert rooms
        for room in result.rooms:
            db_room = RoomModel(
                floor_plan_id=floor_plan_id,
                name=room.name,
                room_type="detected",
                room_number=str(room.room_number),
                boundary_points=room.boundary_points,
            )
            db_room.calculate_length_width(scale_factor=scale_factor_mm_per_px)
            db_room.calculate_area(scale_factor=scale_factor_mm_per_px)
            db_room.calculate_perimeter(scale_factor=scale_factor_mm_per_px)
            db_room.calculate_center()
            rooms.append(db_room)

        # Convert dimensions (unit is meters in recognition result)
        for dimension in result.dimensions:
            db_dimension = DimensionModel(
                floor_plan_id=floor_plan_id,
                x=float(dimension.x),
                y=float(dimension.y),
                value=float(dimension.value),
                unit=dimension.unit or "m",
                text=dimension.text,
                wall_id=dimension.wall_id,
                room_id=dimension.room_id,
                line_x1=dimension.line_x1,
                line_y1=dimension.line_y1,
                line_x2=dimension.line_x2,
                line_y2=dimension.line_y2,
                dimension_type="linear",
            )
            dimensions.append(db_dimension)
        
        return walls, doors, windows, rooms, dimensions
    
    def result_to_dict(self, result: ProcessingResult) -> Dict:
        """
        Convert ProcessingResult to dictionary for storage/API response.
        
        Args:
            result: ProcessingResult object
            
        Returns:
            Dictionary representation
        """
        def convert_numpy_types(obj):
            """Recursively convert NumPy types to Python types for JSON serialization."""
            if isinstance(obj, dict):
                return {k: convert_numpy_types(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [convert_numpy_types(item) for item in obj]
            elif hasattr(obj, 'item'):  # NumPy scalar
                return obj.item()
            elif hasattr(obj, 'tolist'):  # NumPy array
                return obj.tolist()
            else:
                return obj
        
        return convert_numpy_types({
            "image": {
                "width": result.image_width,
                "height": result.image_height,
            },
            "walls": [
                {
                    "id": wall.id,
                    "midline": [wall.midline.x1, wall.midline.y1, wall.midline.x2, wall.midline.y2],
                    "thickness_px": wall.thickness_px,
                    "angle_deg": wall.angle_deg,
                    "confidence": wall.confidence,
                }
                for wall in result.walls
            ],
            "openings": [
                {
                    "type": opening.type.value,
                    "wall_id": opening.wall_id,
                    "bbox": list(opening.bbox),
                    "confidence": opening.confidence,
                    "center": list(opening.center),
                    "marker": opening.marker,
                    "lines": opening.lines,
                    "metadata": opening.metadata,
                }
                for opening in result.openings
            ],
            "rooms": [
                {
                    "id": room.id,
                    "room_number": room.room_number,
                    "name": room.name,
                    "boundary_points": room.boundary_points,
                    "center": list(room.center),
                    "area_px": room.area_px,
                    "confidence": room.confidence,
                    "metadata": room.metadata,
                }
                for room in result.rooms
            ],
            "dimensions": [
                {
                    "id": dimension.id,
                    "x": dimension.x,
                    "y": dimension.y,
                    "value": dimension.value,
                    "unit": dimension.unit,
                    "text": dimension.text,
                    "confidence": dimension.confidence,
                    "bbox": list(dimension.bbox) if dimension.bbox else None,
                    "wall_id": dimension.wall_id,
                    "room_id": dimension.room_id,
                    "line_x1": dimension.line_x1,
                    "line_y1": dimension.line_y1,
                    "line_x2": dimension.line_x2,
                    "line_y2": dimension.line_y2,
                    "metadata": dimension.metadata,
                }
                for dimension in result.dimensions
            ],
        })

def get_integrator(debug: bool = False) -> FloorplanRecognitionIntegrator:
    """Return a configured integrator instance."""
    return FloorplanRecognitionIntegrator(debug=debug)
