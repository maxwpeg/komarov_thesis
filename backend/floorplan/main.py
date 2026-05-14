"""Main processing pipeline and CLI interface."""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from .floorplan_types import ProcessingResult, Opening, OpeningType
from .preprocess import preprocess
# from .walls import detect_wall_segments, pair_parallel_lines
from .walls_morph import detect_walls
from .openings import find_gaps_along_wall, classify_opening, remove_duplicate_openings
from .rooms import detect_rooms
from .ocr_dimensions import detect_text_dimensions, assign_dimensions
from .visualize import draw_walls, draw_openings, create_overlay, save_debug_images


class FloorPlanProcessor:
    """Main floor plan processing engine."""

    def __init__(self, debug: bool = False):
        self.debug = debug

    def process(self, image_path: str, debug_dir: Optional[str] = None) -> ProcessingResult:
        """
        Process a floor plan image.

        Args:
            image_path: Path to input image.
            debug_dir: Optional directory to save debug images.

        Returns:
            ProcessingResult with detected walls and openings.
        """
        # Read original image only for validation
        original_img = cv2.imread(image_path)
        if original_img is None:
            raise ValueError(f"Cannot read image: {image_path}")

        # Step 1: Preprocessing
        print("[1/7] Preprocessing.")
        # Для отладки геометрии лучше пока без deskew, если он не стабилен
        binary, preprocessed = preprocess(image_path, rectify=True, deskew_enabled=False)

        # IMPORTANT: use processed image size, not original size
        height, width = preprocessed.shape[:2]

        # # Step 2: Detect walls
        # print("[2/6] Detecting wall segments.")
        # segments = detect_wall_segments(binary)
        # print(f"     Found {len(segments)} line segments")

        # Step 3: Pair parallel lines into walls
        print("[2/7] Pairing parallel lines into walls.")
        walls = detect_walls(binary)
        print(f"     Found {len(walls)} walls")

        # Step 4: Find gaps in walls
        print("[3/7] Finding gaps (openings) in walls.")
        all_gaps = []
        for wall in walls:
            gaps = find_gaps_along_wall(wall, binary)
            all_gaps.extend(gaps)
        print(f"     Found {len(all_gaps)} gaps")

        # Step 5: Classify gaps as doors or windows
        print("[4/7] Classifying openings.")
        openings = []
        for gap in all_gaps:
            wall = next((w for w in walls if w.id == gap.wall_id), None)
            if wall is None:
                continue

            cls_result = classify_opening(gap, wall, binary, preprocessed)
            if cls_result is None:
                continue

            opening_type, confidence, metadata = cls_result

            x1, y1, x2, y2 = gap.bbox
            center_x = (x1 + x2) / 2.0
            center_y = (y1 + y2) / 2.0

            marker = metadata.get("marker") if opening_type == OpeningType.DOOR else None
            lines = metadata.get("lines") if opening_type == OpeningType.WINDOW else None

            opening = Opening(
                type=opening_type,
                wall_id=wall.id,
                bbox=(int(x1), int(y1), int(x2), int(y2)),
                confidence=float(confidence),
                center=(center_x, center_y),
                marker=marker,
                lines=lines,
                metadata=metadata,
            )
            openings.append(opening)

        # Step 6: Post-processing
        print("[5/7] Post-processing openings.")
        openings = remove_duplicate_openings(openings)
        print(f"     Final: {len(openings)} openings")

        # Step 7: Detect enclosed rooms
        print("[6/7] Detecting rooms.")
        rooms = detect_rooms(binary, walls)
        print(f"     Found {len(rooms)} rooms")

        # Step 8: OCR dimensions and assign to nearest wall/room
        print("[7/7] OCR dimensions and assignment.")
        dimensions = detect_text_dimensions(preprocessed)
        dimensions = assign_dimensions(dimensions, walls, rooms)
        print(f"     Found {len(dimensions)} dimensions")

        # Build result
        result = ProcessingResult(
            image_width=width,
            image_height=height,
            walls=walls,
            openings=openings,
            rooms=rooms,
            dimensions=dimensions,
        )

        # Debug output
        if debug_dir:
            print(f"\nSaving debug images to {debug_dir}.")

            # Base for geometry debugging: show walls/openings on binary image, not on photo
            if len(binary.shape) == 2:
                wall_base = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
                gap_base = cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)
            else:
                wall_base = binary.copy()
                gap_base = binary.copy()

            wall_img = draw_walls(wall_base, walls)
            gap_img = draw_walls(gap_base, walls)
            gap_img = draw_openings(gap_img, openings)

            # Final human-readable overlay on preprocessed image
            overlay = create_overlay(preprocessed, result)

            if self.debug:
                print(f"     walls: {len(walls)}")
                print(f"     openings: {len(openings)}")
                print(f"     rooms: {len(rooms)}")
                print(f"     dimensions: {len(dimensions)}")
                print(f"     wall_img changed: {np.any(wall_img != wall_base)}")
                print(f"     gap_img changed: {np.any(gap_img != gap_base)}")
                print(f"     overlay changed: {np.any(overlay != preprocessed)}")

            save_debug_images(
                preprocessed,
                binary,
                wall_img,
                gap_img,
                overlay,
                debug_dir,
            )
            print("     Debug images saved!")

        return result


def main():
    """Command-line interface."""
    parser = argparse.ArgumentParser(
        description="Floor plan analyzer: detect walls, doors, and windows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m floorplan.main --input floor.jpg --out result.json
  python -m floorplan.main --input floor.jpg --out result.json --debug debug_output --overlay floor_result.png
        """,
    )

    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to input floor plan image (jpg/png)",
    )

    parser.add_argument(
        "--out", "-o",
        required=True,
        help="Output JSON file path",
    )

    parser.add_argument(
        "--debug", "-d",
        help="Save intermediate debug images to this directory",
    )

    parser.add_argument(
        "--overlay",
        help="Save visualization overlay image to this path",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output",
    )

    args = parser.parse_args()

    # Validate input
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    if input_path.suffix.lower() not in [".jpg", ".jpeg", ".png"]:
        print(f"Error: Unsupported image format: {input_path.suffix}")
        sys.exit(1)

    # Create output directory if needed
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        processor = FloorPlanProcessor(debug=args.verbose)
        result = processor.process(str(input_path), debug_dir=args.debug)

        # Save JSON
        result.save_json(str(output_path))
        print(f"\n✓ Result saved to: {output_path}")

        # Save overlay if requested
        if args.overlay:
            overlay_path = Path(args.overlay)
            overlay_path.parent.mkdir(parents=True, exist_ok=True)

            # IMPORTANT: overlay must be drawn on the same preprocessed geometry space
            _, preprocessed = preprocess(str(input_path), rectify=True, deskew_enabled=False)
            overlay_img = create_overlay(preprocessed, result)
            cv2.imwrite(str(overlay_path), overlay_img)
            print(f"✓ Overlay saved to: {overlay_path}")

        # Print statistics
        print("\nStatistics:")
        print(f"  Walls detected: {len(result.walls)}")
        print(f"  Openings detected: {len(result.openings)}")
        doors = sum(1 for o in result.openings if o.type == OpeningType.DOOR)
        windows = sum(1 for o in result.openings if o.type == OpeningType.WINDOW)
        print(f"  - Doors: {doors}")
        print(f"  - Windows: {windows}")
        print(f"  Rooms detected: {len(result.rooms)}")
        print(f"  Dimensions detected: {len(result.dimensions)}")

        if args.verbose:
            print("\nDetailed results:")
            print(json.dumps(result.to_dict(), indent=2))

    except Exception as e:
        print(f"Error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
