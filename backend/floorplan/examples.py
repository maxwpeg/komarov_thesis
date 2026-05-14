"""Example usage of the floorplan module."""

import sys
from pathlib import Path

# Add parent directory to path if needed
sys.path.insert(0, str(Path(__file__).parent))

from floorplan import FloorPlanProcessor, ProcessingResult


def example_basic_usage():
    """Basic example: process single image."""
    print("=" * 60)
    print("Example 1: Basic Usage")
    print("=" * 60)
    
    processor = FloorPlanProcessor(debug=False)
    
    # This would be your actual image
    image_path = "example_floor.jpg"
    
    # Check if image exists
    if not Path(image_path).exists():
        print(f"Note: Example image '{image_path}' not found.")
        print("To run, provide a floor plan image.")
        return
    
    try:
        result = processor.process(image_path)
        
        print(f"\nProcessing complete!")
        print(f"  Walls detected: {len(result.walls)}")
        print(f"  Openings detected: {len(result.openings)}")
        
        # Save results
        result.save_json("output/floor_result.json")
        print(f"  Result saved to: output/floor_result.json")
        
    except Exception as e:
        print(f"Error: {e}")


def example_with_debug():
    """Example with debug output."""
    print("\n" + "=" * 60)
    print("Example 2: With Debug Output")
    print("=" * 60)
    
    processor = FloorPlanProcessor(debug=True)
    
    image_path = "example_floor.jpg"
    
    if not Path(image_path).exists():
        print(f"Note: Example image '{image_path}' not found.")
        return
    
    try:
        result = processor.process(
            image_path,
            debug_dir="debug_output"
        )
        
        print(f"\nDebug images saved to: debug_output/")
        print("  01_preprocessed.png - after rectification & deskew")
        print("  02_binary.png - binarized image")
        print("  03_walls.png - detected walls")
        print("  04_gaps.png - detected gaps/openings")
        print("  05_overlay.png - final visualization")
        
    except Exception as e:
        print(f"Error: {e}")


def example_analyze_results():
    """Example: analyze processing results."""
    print("\n" + "=" * 60)
    print("Example 3: Analyze Results")
    print("=" * 60)
    
    processor = FloorPlanProcessor()
    
    image_path = "example_floor.jpg"
    
    if not Path(image_path).exists():
        print(f"Note: Example image '{image_path}' not found.")
        return
    
    try:
        result = processor.process(image_path)
        
        # Analyze walls
        print(f"\nWalls (total: {len(result.walls)}):")
        for wall in result.walls:
            print(f"  Wall #{wall.id}:")
            print(f"    - Position: ({wall.midline.x1:.0f}, {wall.midline.y1:.0f}) to ({wall.midline.x2:.0f}, {wall.midline.y2:.0f})")
            print(f"    - Thickness: {wall.thickness_px:.1f} px")
            print(f"    - Angle: {wall.angle_deg:.1f}°")
            print(f"    - Confidence: {wall.confidence:.2f}")
        
        # Analyze openings
        print(f"\nOpenings (total: {len(result.openings)}):")
        for opening in result.openings:
            print(f"  {opening.type.value.upper()}:")
            print(f"    - Wall: #{opening.wall_id}")
            print(f"    - BBox: {opening.bbox}")
            print(f"    - Center: ({opening.center[0]:.0f}, {opening.center[1]:.0f})")
            print(f"    - Confidence: {opening.confidence:.2f}")
        
        # Statistics
        doors = sum(1 for o in result.openings if o.type.value == "door")
        windows = sum(1 for o in result.openings if o.type.value == "window")
        
        print(f"\nSummary:")
        print(f"  Total walls: {len(result.walls)}")
        print(f"  Total openings: {len(result.openings)}")
        print(f"    - Doors: {doors}")
        print(f"    - Windows: {windows}")
        
    except Exception as e:
        print(f"Error: {e}")


def example_batch_processing():
    """Example: process multiple images."""
    print("\n" + "=" * 60)
    print("Example 4: Batch Processing")
    print("=" * 60)
    
    processor = FloorPlanProcessor(debug=False)
    
    # Process all jpg files in input directory
    input_dir = Path("input_images")
    if not input_dir.exists():
        print(f"Note: Directory '{input_dir}' not found.")
        print("Create a directory with floor plan images to demo batch processing.")
        return
    
    output_dir = Path("batch_output")
    output_dir.mkdir(exist_ok=True)
    
    images = list(input_dir.glob("*.jpg")) + list(input_dir.glob("*.png"))
    
    if not images:
        print(f"No images found in {input_dir}")
        return
    
    print(f"Found {len(images)} images to process:\n")
    
    results = []
    for i, image_path in enumerate(images, 1):
        try:
            result = processor.process(str(image_path))
            result.save_json(str(output_dir / f"{image_path.stem}.json"))
            results.append((image_path.name, len(result.walls), len(result.openings)))
            print(f"  {i}. {image_path.name}: {len(result.walls)} walls, {len(result.openings)} openings ✓")
        except Exception as e:
            print(f"  {i}. {image_path.name}: Error - {e}")
    
    print(f"\nResults saved to: {output_dir}/")


def example_programmatic_api():
    """Example: use as library with custom processing."""
    print("\n" + "=" * 60)
    print("Example 5: Programmatic API")
    print("=" * 60)
    
    processor = FloorPlanProcessor()
    
    image_path = "example_floor.jpg"
    
    if not Path(image_path).exists():
        print(f"Note: Example image '{image_path}' not found.")
        return
    
    try:
        # Process
        result = processor.process(image_path)
        
        # Convert to dict for custom processing
        data = result.to_dict()
        
        print("Result as dictionary:")
        print(f"  Image size: {data['image']['width']}x{data['image']['height']}")
        print(f"  Walls: {len(data['walls'])}")
        print(f"  Openings: {len(data['openings'])}")
        
        # Filter openings by confidence
        high_confidence = [o for o in data['openings'] if o['confidence'] > 0.7]
        print(f"  High confidence openings (>0.7): {len(high_confidence)}")
        
        # Calculate statistics
        if data['walls']:
            avg_thickness = sum(w['thickness_px'] for w in data['walls']) / len(data['walls'])
            print(f"  Average wall thickness: {avg_thickness:.1f} px")
        
        # Serialize to custom format if needed
        import json
        with open("custom_analysis.json", "w") as f:
            json.dump({
                "total_walls": len(data['walls']),
                "total_openings": len(data['openings']),
                "high_confidence_openings": high_confidence,
            }, f, indent=2)
        
        print("\n  Analysis saved to: custom_analysis.json")
        
    except Exception as e:
        print(f"Error: {e}")


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "=" * 58 + "╗")
    print("║" + " Floor Plan Analyzer - Usage Examples ".center(58) + "║")
    print("╚" + "=" * 58 + "╝")
    
    # Note: These are demonstration functions
    # To run, provide actual floor plan images
    
    example_basic_usage()
    example_with_debug()
    example_analyze_results()
    example_batch_processing()
    example_programmatic_api()
    
    print("\n" + "=" * 60)
    print("For more information, see floorplan/README.md")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
