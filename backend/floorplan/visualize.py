"""Visualization of floor plan processing results."""

import cv2
import numpy as np
from typing import List
from .floorplan_types import ProcessingResult, Opening
from .geometry import wall_boundary_lines


def draw_walls(img: np.ndarray, walls: list, color: tuple = (0, 255, 0), thickness: int = 2) -> np.ndarray:
    """
    Draw walls on image.
    
    Args:
        img: Input image (BGR).
        walls: List of Wall objects.
        color: Line color (BGR).
        thickness: Line thickness.
        
    Returns:
        Image with drawn walls.
    """
    result = img.copy()
    
    for wall in walls:
        line_a, line_b = wall_boundary_lines(wall)
        cv2.line(
            result,
            (int(round(line_a.x1)), int(round(line_a.y1))),
            (int(round(line_a.x2)), int(round(line_a.y2))),
            color,
            thickness,
        )
        cv2.line(
            result,
            (int(round(line_b.x1)), int(round(line_b.y1))),
            (int(round(line_b.x2)), int(round(line_b.y2))),
            color,
            thickness,
        )

        # Draw wall ID
        midline = wall.midline
        mid_x = int(round((midline.x1 + midline.x2) / 2.0))
        mid_y = int(round((midline.y1 + midline.y2) / 2.0))
        cv2.putText(result, f"W{wall.id}", (mid_x, mid_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
    
    return result


def draw_openings(img: np.ndarray, openings: List[Opening], thickness: int = 2) -> np.ndarray:
    result = img.copy()

    for opening in openings:
        x1, y1, x2, y2 = map(int, opening.bbox)

        if opening.type.value == "door":
            color = (0, 0, 255)   # red
        else:
            color = (255, 0, 0)   # blue

        cv2.rectangle(result, (x1, y1), (x2, y2), color, thickness)

        cx, cy = int(opening.center[0]), int(opening.center[1])
        cv2.circle(result, (cx, cy), max(2, thickness), color, -1)

        # door marker: [x1, y1, x2, y2]
        if opening.marker is not None:
            try:
                if len(opening.marker) == 4:
                    mx1, my1, mx2, my2 = map(int, opening.marker)
                    cv2.line(result, (mx1, my1), (mx2, my2), (0, 255, 255), thickness)
            except Exception:
                pass

        # window lines: [(x1,y1,x2,y2), ...]
        if opening.lines is not None:
            try:
                for line in opening.lines:
                    if len(line) == 4:
                        lx1, ly1, lx2, ly2 = map(int, line)
                        cv2.line(result, (lx1, ly1), (lx2, ly2), (255, 255, 0), thickness)
            except Exception:
                pass

        cv2.putText(
            result,
            opening.type.value.upper(),
            (x1, max(15, y1 - 18)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
        )
        cv2.putText(
            result,
            f"{opening.confidence:.2f}",
            (x1, max(15, y1 - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            1,
        )

    return result


def draw_rooms(img: np.ndarray, rooms: list) -> np.ndarray:
    result = img.copy()
    for room in rooms:
        if not room.boundary_points or len(room.boundary_points) < 3:
            continue
        contour = np.array(room.boundary_points, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(result, [contour], isClosed=True, color=(180, 0, 180), thickness=1)
        cx, cy = int(room.center[0]), int(room.center[1])
        cv2.putText(
            result,
            f"R{room.room_number}",
            (cx - 12, cy),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (180, 0, 180),
            1,
        )
    return result


def draw_dimensions(img: np.ndarray, dimensions: list) -> np.ndarray:
    result = img.copy()
    for dim in dimensions:
        x = int(round(dim.x))
        y = int(round(dim.y))
        cv2.circle(result, (x, y), 2, (0, 0, 255), -1)
        cv2.putText(
            result,
            f"{dim.value:.2f}m",
            (x + 4, y - 4),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.4,
            (0, 0, 255),
            1,
        )
    return result


def create_overlay(img: np.ndarray, result: ProcessingResult) -> np.ndarray:
    """
    Create overlay visualization with walls and openings.
    
    Args:
        img: Original image (BGR).
        result: ProcessingResult object.
        
    Returns:
        Visualization image.
    """
    overlay = img.copy()
    
    # Draw walls
    overlay = draw_walls(overlay, result.walls, color=(0, 255, 0), thickness=2)
    
    # Draw openings
    overlay = draw_openings(overlay, result.openings, thickness=2)

    # Draw rooms and OCR dimensions
    overlay = draw_rooms(overlay, result.rooms)
    overlay = draw_dimensions(overlay, result.dimensions)
    
    return overlay


def save_debug_images(
    preprocessed: np.ndarray,
    binary: np.ndarray,
    wall_image: np.ndarray,
    gap_image: np.ndarray,
    overlay: np.ndarray,
    output_dir: str
) -> None:
    """
    Save intermediate processing images for debugging.
    
    Args:
        preprocessed: Preprocessed (rectified/deskewed) image.
        binary: Binary image.
        wall_image: Image with detected walls.
        gap_image: Image with detected gaps.
        overlay: Final overlay image.
        output_dir: Output directory path.
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    cv2.imwrite(os.path.join(output_dir, "01_preprocessed.png"), preprocessed)
    cv2.imwrite(os.path.join(output_dir, "02_binary.png"), binary)
    cv2.imwrite(os.path.join(output_dir, "03_walls.png"), wall_image)
    cv2.imwrite(os.path.join(output_dir, "04_gaps.png"), gap_image)
    cv2.imwrite(os.path.join(output_dir, "05_overlay.png"), overlay)
