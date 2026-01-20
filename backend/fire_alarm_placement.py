"""
Fire alarm network placement algorithm.
Calculates optimal placement of fire detection and alarm devices based on building codes.
"""
import math
from typing import List, Dict, Tuple, Any
import numpy as np


class FireAlarmPlacement:
    """Calculate fire alarm device placement for floor plans."""
    
    # Default coverage parameters (can be customized)
    DEFAULT_SMOKE_DETECTOR_RADIUS = 7500  # 7.5m in mm
    DEFAULT_HEAT_DETECTOR_RADIUS = 5000   # 5m in mm
    DEFAULT_MANUAL_CALL_POINT_DISTANCE = 45000  # 45m in mm
    DEFAULT_SOUNDER_RADIUS = 30000  # 30m in mm
    DEFAULT_CEILING_HEIGHT = 3000  # 3m in mm
    
    def __init__(
        self,
        smoke_detector_radius: float = None,
        heat_detector_radius: float = None,
        manual_call_point_distance: float = None,
        sounder_radius: float = None,
        ceiling_height: float = None
    ):
        """
        Initialize fire alarm placement calculator.
        
        Args:
            smoke_detector_radius: Coverage radius for smoke detectors (mm)
            heat_detector_radius: Coverage radius for heat detectors (mm)
            manual_call_point_distance: Maximum distance between manual call points (mm)
            sounder_radius: Coverage radius for sounders (mm)
            ceiling_height: Ceiling height for coverage calculations (mm)
        """
        self.smoke_detector_radius = smoke_detector_radius or self.DEFAULT_SMOKE_DETECTOR_RADIUS
        self.heat_detector_radius = heat_detector_radius or self.DEFAULT_HEAT_DETECTOR_RADIUS
        self.manual_call_point_distance = manual_call_point_distance or self.DEFAULT_MANUAL_CALL_POINT_DISTANCE
        self.sounder_radius = sounder_radius or self.DEFAULT_SOUNDER_RADIUS
        self.ceiling_height = ceiling_height or self.DEFAULT_CEILING_HEIGHT
    
    def calculate_room_devices(
        self,
        room: Dict[str, Any],
        scale_factor: float = 1.0,
        room_type: str = "general"
    ) -> List[Dict[str, Any]]:
        """
        Calculate fire alarm devices for a single room.
        
        Args:
            room: Room dictionary with boundary_points, center, area
            scale_factor: mm per pixel conversion
            room_type: Type of room (kitchen, bedroom, corridor, etc.)
        
        Returns:
            List of fire alarm device dictionaries
        """
        if not room.get("boundary_points") or not room.get("area_sqm"):
            return []
        
        devices = []
        
        # Determine detector type based on room type
        if room_type in ["kitchen", "cooking"]:
            # Use heat detectors in kitchens
            detector_type = "heat_detector"
            coverage_radius = self.heat_detector_radius
        else:
            # Use smoke detectors in other areas
            detector_type = "smoke_detector"
            coverage_radius = self.smoke_detector_radius
        
        # Calculate number of detectors needed
        area_mm2 = room["area_sqm"] * 1_000_000  # m² to mm²
        coverage_area = math.pi * (coverage_radius ** 2)
        num_detectors = max(1, math.ceil(area_mm2 / coverage_area))
        
        # Place detectors
        if num_detectors == 1:
            # Single detector at room center
            devices.append({
                "device_type": detector_type,
                "x": room.get("center_x", 0),
                "y": room.get("center_y", 0),
                "coverage_radius": coverage_radius,
                "mounting_height": self.ceiling_height
            })
        else:
            # Multiple detectors - distribute evenly
            positions = self._calculate_detector_grid(
                room["boundary_points"],
                num_detectors,
                coverage_radius
            )
            
            for pos in positions:
                devices.append({
                    "device_type": detector_type,
                    "x": pos[0],
                    "y": pos[1],
                    "coverage_radius": coverage_radius,
                    "mounting_height": self.ceiling_height
                })
        
        return devices
    
    def _calculate_detector_grid(
        self,
        boundary_points: List[List[float]],
        num_detectors: int,
        coverage_radius: float
    ) -> List[Tuple[float, float]]:
        """
        Calculate grid positions for multiple detectors in a room.
        
        Args:
            boundary_points: Room boundary polygon points
            num_detectors: Number of detectors to place
            coverage_radius: Coverage radius of each detector
        
        Returns:
            List of (x, y) positions
        """
        # Find bounding box
        xs = [p[0] for p in boundary_points]
        ys = [p[1] for p in boundary_points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        
        width = max_x - min_x
        height = max_y - min_y
        
        # Calculate grid dimensions
        spacing = coverage_radius * 1.5  # 1.5x radius for overlap
        cols = max(1, int(width / spacing))
        rows = max(1, int(height / spacing))
        
        # Adjust to get closer to num_detectors
        total = cols * rows
        if total < num_detectors:
            if width > height:
                cols += 1
            else:
                rows += 1
        
        # Generate grid positions
        positions = []
        x_step = width / (cols + 1)
        y_step = height / (rows + 1)
        
        for i in range(1, cols + 1):
            for j in range(1, rows + 1):
                x = min_x + i * x_step
                y = min_y + j * y_step
                
                # Check if point is inside polygon
                if self._point_in_polygon((x, y), boundary_points):
                    positions.append((x, y))
                    if len(positions) >= num_detectors:
                        return positions
        
        # If not enough positions, add center
        if len(positions) < num_detectors:
            center_x = (min_x + max_x) / 2
            center_y = (min_y + max_y) / 2
            positions.append((center_x, center_y))
        
        return positions[:num_detectors]
    
    def _point_in_polygon(self, point: Tuple[float, float], polygon: List[List[float]]) -> bool:
        """Check if point is inside polygon using ray casting algorithm."""
        x, y = point
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def calculate_manual_call_points(
        self,
        doors: List[Dict[str, Any]],
        walls: List[Dict[str, Any]],
        scale_factor: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        Calculate manual call point positions near exits.
        
        Args:
            doors: List of door objects
            walls: List of wall objects (for finding exits)
            scale_factor: mm per pixel
        
        Returns:
            List of manual call point devices
        """
        devices = []
        
        for door in doors:
            # Place manual call point near each door/exit
            # Position slightly offset from door
            offset = 300  # 300mm offset in pixels (adjust based on scale)
            
            devices.append({
                "device_type": "manual_call_point",
                "x": door["x"] + offset,
                "y": door["y"] + offset,
                "mounting_height": 1400,  # 1.4m standard height
                "zone": None
            })
        
        return devices
    
    def calculate_sounders(
        self,
        rooms: List[Dict[str, Any]],
        scale_factor: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        Calculate sounder/beacon positions for alarm notification.
        
        Args:
            rooms: List of room objects
            scale_factor: mm per pixel
        
        Returns:
            List of sounder devices
        """
        devices = []
        
        for room in rooms:
            if not room.get("area_sqm"):
                continue
            
            area_mm2 = room["area_sqm"] * 1_000_000
            coverage_area = math.pi * (self.sounder_radius ** 2)
            
            # Typically need fewer sounders than detectors
            num_sounders = max(1, math.ceil(area_mm2 / coverage_area / 2))
            
            if num_sounders == 1 and room.get("center_x"):
                devices.append({
                    "device_type": "sounder",
                    "x": room["center_x"],
                    "y": room["center_y"],
                    "coverage_radius": self.sounder_radius,
                    "mounting_height": self.ceiling_height
                })
        
        return devices
    
    def generate_complete_system(
        self,
        floor_plan_data: Dict[str, Any],
        scale_factor: float = 1.0
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generate complete fire alarm system for a floor plan.
        
        Args:
            floor_plan_data: Complete floor plan data with rooms, doors, walls
            scale_factor: mm per pixel
        
        Returns:
            Dictionary with all device types and their positions
        """
        rooms = floor_plan_data.get("rooms", [])
        doors = floor_plan_data.get("doors", [])
        walls = floor_plan_data.get("walls", [])
        
        # Calculate all device types
        detectors = []
        for room in rooms:
            room_type = room.get("room_type", "general")
            room_devices = self.calculate_room_devices(room, scale_factor, room_type)
            detectors.extend(room_devices)
        
        manual_call_points = self.calculate_manual_call_points(doors, walls, scale_factor)
        sounders = self.calculate_sounders(rooms, scale_factor)
        
        # Assign zones and addresses
        all_devices = []
        device_id = 1
        
        for detector in detectors:
            detector["address"] = f"D{device_id:03d}"
            detector["zone"] = f"Z{((device_id - 1) // 32) + 1}"
            all_devices.append(detector)
            device_id += 1
        
        for mcp in manual_call_points:
            mcp["address"] = f"M{device_id:03d}"
            mcp["zone"] = f"Z{((device_id - 1) // 32) + 1}"
            all_devices.append(mcp)
            device_id += 1
        
        for sounder in sounders:
            sounder["address"] = f"S{device_id:03d}"
            sounder["zone"] = f"Z{((device_id - 1) // 32) + 1}"
            all_devices.append(sounder)
            device_id += 1
        
        return {
            "detectors": detectors,
            "manual_call_points": manual_call_points,
            "sounders": sounders,
            "all_devices": all_devices,
            "summary": {
                "total_devices": len(all_devices),
                "smoke_detectors": sum(1 for d in detectors if d["device_type"] == "smoke_detector"),
                "heat_detectors": sum(1 for d in detectors if d["device_type"] == "heat_detector"),
                "manual_call_points": len(manual_call_points),
                "sounders": len(sounders),
                "zones": max(1, (len(all_devices) - 1) // 32 + 1)
            }
        }


def calculate_fire_alarm_layout(floor_plan_data: Dict[str, Any], scale_factor: float = 1.0) -> Dict[str, Any]:
    """
    Convenience function to calculate fire alarm layout.
    
    Args:
        floor_plan_data: Floor plan dictionary with rooms, doors, walls
        scale_factor: mm per pixel conversion factor
    
    Returns:
        Complete fire alarm system layout
    """
    placement = FireAlarmPlacement()
    return placement.generate_complete_system(floor_plan_data, scale_factor)
