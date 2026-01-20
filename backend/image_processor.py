"""
Image processing module for floor plan parsing.
Includes line detection, OCR for dimensions, and architectural element recognition.
"""
import cv2
import numpy as np
import pytesseract
from PIL import Image
from typing import List, Tuple, Dict, Any
import re


class FloorPlanProcessor:
    """Process floor plan images to extract architectural elements and dimensions."""
    
    def __init__(self, tesseract_cmd: str = None):
        """
        Initialize the floor plan processor.
        
        Args:
            tesseract_cmd: Path to tesseract executable (Windows: C:/Program Files/Tesseract-OCR/tesseract.exe)
        """
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    
    def preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Preprocess the floor plan image for better line and text detection.
        
        Args:
            image: Input image as numpy array (BGR)
        
        Returns:
            Preprocessed grayscale image
        """
        # Convert to grayscale
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        # Apply bilateral filter to reduce noise while preserving edges
        denoised = cv2.bilateralFilter(gray, 9, 75, 75)
        
        # Apply adaptive thresholding
        binary = cv2.adaptiveThreshold(
            denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        
        return binary
    
    def detect_lines(self, image: np.ndarray, min_line_length: int = 50) -> List[Dict[str, Any]]:
        """
        Detect straight lines in the floor plan (walls).
        
        Args:
            image: Preprocessed binary image
            min_line_length: Minimum length of lines to detect (pixels)
        
        Returns:
            List of detected lines with properties
        """
        # Apply edge detection
        edges = cv2.Canny(image, 50, 150, apertureSize=3)
        
        # Detect lines using Hough Line Transform
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=100,
            minLineLength=min_line_length,
            maxLineGap=10
        )
        
        detected_lines = []
        if lines is not None:
            for i, line in enumerate(lines):
                x1, y1, x2, y2 = line[0]
                
                # Calculate angle
                angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
                
                # Classify as horizontal or vertical
                is_horizontal = abs(angle) < 15 or abs(angle) > 165
                is_vertical = 75 < abs(angle) < 105
                
                detected_lines.append({
                    "x1": float(x1),
                    "y1": float(y1),
                    "x2": float(x2),
                    "y2": float(y2),
                    "angle": float(angle),
                    "length": float(np.sqrt((x2 - x1)**2 + (y2 - y1)**2)),
                    "is_horizontal": is_horizontal,
                    "is_vertical": is_vertical
                })
        
        return detected_lines
    
    def merge_collinear_lines(
        self,
        lines: List[Dict[str, Any]],
        distance_threshold: float = 10.0,
        angle_threshold: float = 5.0
    ) -> List[Dict[str, Any]]:
        """
        Merge collinear lines that are close together.
        
        Args:
            lines: List of detected lines
            distance_threshold: Maximum distance between lines to merge
            angle_threshold: Maximum angle difference for merging
        
        Returns:
            Merged lines
        """
        if not lines:
            return []
        
        merged = []
        used = set()
        
        for i, line1 in enumerate(lines):
            if i in used:
                continue
            
            group = [line1]
            used.add(i)
            
            for j, line2 in enumerate(lines):
                if j in used or j <= i:
                    continue
                
                # Check if angles are similar
                angle_diff = abs(line1["angle"] - line2["angle"])
                if angle_diff > angle_threshold and angle_diff < (180 - angle_threshold):
                    continue
                
                # Check if lines are close
                # Simple distance check between endpoints
                dist = min(
                    np.sqrt((line1["x1"] - line2["x1"])**2 + (line1["y1"] - line2["y1"])**2),
                    np.sqrt((line1["x1"] - line2["x2"])**2 + (line1["y1"] - line2["y2"])**2),
                    np.sqrt((line1["x2"] - line2["x1"])**2 + (line1["y2"] - line2["y1"])**2),
                    np.sqrt((line1["x2"] - line2["x2"])**2 + (line1["y2"] - line2["y2"])**2)
                )
                
                if dist < distance_threshold:
                    group.append(line2)
                    used.add(j)
            
            # Merge group into single line
            if len(group) == 1:
                merged.append(group[0])
            else:
                # Find extreme points
                all_x = [p["x1"] for p in group] + [p["x2"] for p in group]
                all_y = [p["y1"] for p in group] + [p["y2"] for p in group]
                
                x1, x2 = min(all_x), max(all_x)
                y1, y2 = min(all_y), max(all_y)
                
                avg_angle = np.mean([p["angle"] for p in group])
                
                merged.append({
                    "x1": float(x1),
                    "y1": float(y1),
                    "x2": float(x2),
                    "y2": float(y2),
                    "angle": float(avg_angle),
                    "length": float(np.sqrt((x2 - x1)**2 + (y2 - y1)**2)),
                    "is_horizontal": abs(avg_angle) < 15 or abs(avg_angle) > 165,
                    "is_vertical": 75 < abs(avg_angle) < 105
                })
        
        return merged
    
    def extract_text_regions(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Extract text regions from the floor plan using OCR.
        
        Args:
            image: Input image (grayscale or BGR)
        
        Returns:
            List of text regions with OCR results
        """
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Enhance contrast for better OCR
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Use pytesseract to get detailed OCR data
        try:
            ocr_data = pytesseract.image_to_data(enhanced, output_type=pytesseract.Output.DICT, lang='eng+rus')
        except Exception as e:
            print(f"OCR Error: {e}")
            return []
        
        text_regions = []
        n_boxes = len(ocr_data['text'])
        
        for i in range(n_boxes):
            text = ocr_data['text'][i].strip()
            conf = int(ocr_data['conf'][i])
            
            # Filter out low confidence and empty text
            if conf > 30 and text:
                x, y, w, h = (
                    ocr_data['left'][i],
                    ocr_data['top'][i],
                    ocr_data['width'][i],
                    ocr_data['height'][i]
                )
                
                text_regions.append({
                    "text": text,
                    "x": x,
                    "y": y,
                    "width": w,
                    "height": h,
                    "confidence": conf
                })
        
        return text_regions
    
    def extract_dimensions(self, text_regions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract dimension measurements from OCR text.
        
        Args:
            text_regions: List of OCR text regions
        
        Returns:
            List of dimension annotations
        """
        dimensions = []
        
        # Pattern to match numbers with optional decimal point and units
        # Examples: "3.5", "240", "2,8", "1.35"
        number_pattern = r'[\d]+[.,]?[\d]*'
        
        for region in text_regions:
            text = region['text']
            
            # Try to extract numeric values
            matches = re.findall(number_pattern, text)
            
            for match in matches:
                # Clean the number (replace comma with dot)
                value_str = match.replace(',', '.')
                
                try:
                    value = float(value_str)
                    
                    # Heuristic: dimensions on floor plans are usually in mm or cm
                    # If value is small (< 20), assume it's in meters and convert to mm
                    if value < 20:
                        value_mm = value * 1000  # meters to mm
                    elif value < 500:
                        value_mm = value * 10  # cm to mm
                    else:
                        value_mm = value  # already in mm
                    
                    dimensions.append({
                        "x": float(region['x'] + region['width'] / 2),
                        "y": float(region['y'] + region['height'] / 2),
                        "value": float(value_mm),
                        "text": text,
                        "confidence": region['confidence'],
                        "unit": "mm"
                    })
                except ValueError:
                    continue
        
        return dimensions
    
    def detect_rooms(self, image: np.ndarray, walls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect room boundaries using contour detection.
        
        Args:
            image: Binary image of the floor plan
            walls: List of detected walls
        
        Returns:
            List of room polygons
        """
        # Find contours
        contours, _ = cv2.findContours(
            cv2.bitwise_not(image),
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE
        )
        
        rooms = []
        min_area = 1000  # Minimum area to consider as a room (pixels²)
        
        for i, contour in enumerate(contours):
            area = cv2.contourArea(contour)
            
            if area > min_area:
                # Approximate contour to polygon
                epsilon = 0.01 * cv2.arcLength(contour, True)
                approx = cv2.approxPolyDP(contour, epsilon, True)
                
                # Extract boundary points
                boundary_points = [[float(p[0][0]), float(p[0][1])] for p in approx]
                
                # Calculate centroid
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = M["m10"] / M["m00"]
                    cy = M["m01"] / M["m00"]
                else:
                    cx, cy = 0, 0
                
                rooms.append({
                    "id": i,
                    "boundary_points": boundary_points,
                    "area_pixels": float(area),
                    "center_x": float(cx),
                    "center_y": float(cy),
                    "num_vertices": len(boundary_points)
                })
        
        return rooms
    
    def process_floor_plan(
        self,
        image_path: str,
        detect_text: bool = True,
        detect_rooms: bool = True
    ) -> Dict[str, Any]:
        """
        Complete pipeline to process a floor plan image.
        
        Args:
            image_path: Path to the floor plan image
            detect_text: Whether to perform OCR
            detect_rooms: Whether to detect room boundaries
        
        Returns:
            Dictionary with all detected elements
        """
        # Load image
        image = cv2.imread(image_path)
        if image is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        height, width = image.shape[:2]
        
        # Preprocess
        binary = self.preprocess_image(image)
        
        # Detect lines (walls)
        raw_lines = self.detect_lines(binary)
        walls = self.merge_collinear_lines(raw_lines)
        
        results = {
            "image_width": width,
            "image_height": height,
            "walls": walls,
            "dimensions": [],
            "rooms": []
        }
        
        # Extract text and dimensions
        if detect_text:
            text_regions = self.extract_text_regions(image)
            dimensions = self.extract_dimensions(text_regions)
            results["dimensions"] = dimensions
            results["text_regions"] = text_regions
        
        # Detect rooms
        if detect_rooms:
            rooms = self.detect_rooms(binary, walls)
            results["rooms"] = rooms
        
        return results


def process_uploaded_floor_plan(image_path: str) -> Dict[str, Any]:
    """
    Convenience function to process an uploaded floor plan.
    
    Args:
        image_path: Path to the uploaded image
    
    Returns:
        Processed floor plan data
    """
    processor = FloorPlanProcessor()
    return processor.process_floor_plan(image_path)
