# Floor Plan Module - Quick Start Guide

## Installation

```bash
pip install -r floorplan/requirements.txt
```

## Quick Start

### 1. Command Line Interface (CLI)

**Basic usage:**
```bash
python -m floorplan.main --input floor.jpg --out result.json
```

**With visualization:**
```bash
python -m floorplan.main \
  --input floor.jpg \
  --out result.json \
  --overlay result_visualization.png \
  --debug debug_images \
  --verbose
```

**Options:**
- `--input, -i FILE` - Input floor plan image (JPG/PNG) **[required]**
- `--out, -o FILE` - Output JSON file with results **[required]**
- `--debug, -d DIR` - Save intermediate processing images
- `--overlay FILE` - Save visualization with detected elements
- `--verbose, -v` - Show detailed output and JSON

### 2. Python API

```python
from floorplan import FloorPlanProcessor

# Create processor
processor = FloorPlanProcessor(debug=False)

# Process image
result = processor.process("floor.jpg", debug_dir="debug_output")

# Access results
print(f"Walls: {len(result.walls)}")
print(f"Openings: {len(result.openings)}")

# Save to JSON
result.save_json("output.json")

# Iterate through results
for wall in result.walls:
    print(f"Wall {wall.id}: {wall.thickness_px}px thick at {wall.angle_deg}°")

for opening in result.openings:
    print(f"{opening.type.value}: confidence={opening.confidence:.2f}")
```

## Output Format

Results are saved as JSON:

```json
{
  "image": {"width": 1024, "height": 768},
  "walls": [
    {
      "id": 0,
      "midline": [100, 200, 500, 200],
      "thickness_px": 20,
      "angle_deg": 0,
      "confidence": 0.95
    }
  ],
  "openings": [
    {
      "type": "door",
      "wall_id": 0,
      "bbox": [200, 180, 280, 220],
      "confidence": 0.85,
      "center": [240, 200]
    }
  ]
}
```

## Running Tests

```bash
python -m pytest floorplan/tests/ -v
```

All tests should pass: **10/10 ✓**

## Debug Images

When using `--debug`, you get:

1. **01_preprocessed.png** - After perspective correction and deskew
2. **02_binary.png** - Binarized image (walls in white)
3. **03_walls.png** - Detected walls with IDs
4. **04_gaps.png** - Detected gaps/openings
5. **05_overlay.png** - Final result on original image

## Key Features

✅ **Wall Detection**
- Finds parallel line pairs
- Extracts wall centerline and thickness
- Handles various angles (0-90°)

✅ **Opening Detection**
- Finds gaps in walls
- Classifies as doors or windows
- Confidence scoring

✅ **Door Markers**
- Detects perpendicular line in center
- Indicates door swing direction

✅ **Window Markers**
- Detects 2-3 parallel lines
- Indicates window frames/muntins

✅ **Image Preprocessing**
- Perspective correction (rectification)
- Auto-deskewing
- Adaptive binarization
- Handles poor lighting

## Configuration

Adjust detection parameters in source files:

- **preprocess.py** - Image processing thresholds
- **walls.py** - Wall detection (WallConfig)
- **openings.py** - Door/window detection (OpeningConfig)

## Example Workflow

```bash
# 1. Process image
python -m floorplan.main \
  --input my_floor.jpg \
  --out result.json \
  --debug debug \
  --overlay result_visual.png

# 2. Check results
cat result.json | python -m json.tool

# 3. View visualization
# Open result_visual.png in image viewer

# 4. Review debug images
# Check debug/*.png to understand detection steps
```

## Requirements

- **Python**: 3.10 or higher
- **OpenCV**: 4.6+ (included in requirements.txt)
- **NumPy**: 1.21+ (included in requirements.txt)
- **Memory**: ~100 MB for typical 1500px images
- **Time**: ~300-500 ms per image on modern CPU

## Limitations

- Works best with clear, high-contrast drawings
- Expects relatively straight walls
- Handles photos at angles up to ~45°
- May pick up handwritten notes as features
- No support for curved walls
- Best with grayscale or simple layouts

## Performance Tips

1. **Larger images** (>2000px) → May be slower but more accurate
2. **Poor quality** → Pre-process in Photoshop/GIMP first
3. **Multiple runs** → Create processor once, reuse for batch
4. **Memory** → Process images sequentially, not in parallel

## Troubleshooting

**Q: No walls detected**
- A: Check image contrast. Use `--debug` to see binarized result
- Image may be too light/dark → adjust preprocessing threshold

**Q: Too many false walls**
- A: Detected noise/grid lines. Adjust WallConfig thresholds
- Or pre-process image to remove non-essential marks

**Q: Openings not classified correctly**
- A: Use `--debug` to see ROI analysis
- May need to adjust OpeningConfig thresholds
- Complex marker patterns require manual review

**Q: Memory error with large image**
- A: Reduce image size before processing
- Or use downsampled version for testing

## Advanced Usage

See [floorplan/README.md](floorplan/README.md) for detailed documentation.

See [floorplan/examples.py](floorplan/examples.py) for code examples.
