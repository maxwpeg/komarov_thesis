# Floor Plan Recognition API Integration

## Overview

The floor plan recognition module has been integrated into the FastAPI backend. This enables automatic detection of walls, doors, and windows from floor plan images using classical computer vision techniques.

## New API Endpoints

### POST `/api/floor-plans/{floor_plan_id}/process`

Recognizes walls and openings in a floor plan image using OpenCV-based computer vision.

**Parameters:**
- `floor_plan_id` (path parameter): ID of the floor plan to process

**Response:**
```json
{
  "message": "Floor plan recognized successfully",
  "walls_detected": 12,
  "doors_detected": 4,
  "windows_detected": 8,
  "recognition_id": 42
}
```

**Error Responses:**
- `404`: Floor plan not found
- `400`: Floor plan image not found
- `500`: Error during processing

### GET `/api/floor-plans/{floor_plan_id}/recognition`

Retrieves the recognition result for a floor plan.

**Parameters:**
- `floor_plan_id` (path parameter): ID of the floor plan

**Response - If recognized:**
```json
{
  "id": 42,
  "floor_plan_id": 5,
  "status": "completed",
  "recognition_result": {
    "image": {
      "width": 1500,
      "height": 1200
    },
    "walls": [
      {
        "id": 1,
        "midline": [100, 200, 500, 400],
        "thickness_px": 15,
        "angle_deg": 45.0,
        "confidence": 0.95
      }
    ],
    "openings": [
      {
        "type": "door",
        "wall_id": 1,
        "bbox": [250, 300, 280, 350],
        "confidence": 0.85,
        "center": [265, 325],
        "marker": null,
        "lines": [],
        "metadata": {}
      }
    ]
  },
  "error_message": null,
  "processed_at": "2024-01-15T10:30:00"
}
```

**Response - If not recognized:**
```json
{
  "recognition_id": null,
  "status": "not_processed",
  "recognition_result": null,
  "error_message": null
}
```

## Architecture

### Database Model: FloorplanRecognition

Stores recognition results for each floor plan:

```python
class FloorplanRecognition(Base):
    __tablename__ = 'floorplan_recognitions'
    
    id = Column(Integer, primary_key=True)
    floor_plan_id = Column(Integer, ForeignKey('floor_plans.id'), unique=True)
    recognition_result = Column(JSON)  # Full result from floorplan module
    status = Column(String(20))  # "pending", "processing", "completed", "failed"
    error_message = Column(Text)
    processed_at = Column(DateTime)
    debug_artifacts_dir = Column(String(500))  # Path to debug images if debug=true
```

### Integration Layer: FloorplanRecognitionIntegrator

Located in `backend/floorplan_integration.py`, provides:

- `recognize_floor_plan(image_path)` - Calls floorplan module's processor
- `convert_to_database_models(result, floor_plan_id)` - Converts recognition result to Wall/Door/Window ORM objects
- `result_to_dict(result)` - Serializes result to JSON for storage
- `get_integrator()` - Global singleton accessor

## Recognition Algorithm

The floorplan module uses classical computer vision approach:

1. **Preprocessing**: Image rectification, deskew, binarization
2. **Wall Detection**: HoughLines algorithm to detect linear segments
3. **Wall Pairing**: Identify parallel line pairs as wall boundaries
4. **Opening Detection**: Find gaps in walls and classify as doors/windows
5. **Output**: Walls with centerline + thickness, openings with coordinates and type

### Output Format

Walls include:
- `id`: Unique wall identifier
- `midline`: [x1, y1, x2, y2] centerline coordinates
- `thickness_px`: Wall thickness in pixels
- `angle_deg`: Wall angle 0-180 degrees
- `confidence`: Detection confidence 0-1

Openings include:
- `type`: "door" or "window"
- `wall_id`: Parent wall ID
- `bbox`: [x1, y1, x2, y2] bounding box
- `confidence`: Detection confidence 0-1
- `center`: [cx, cy] center point
- `marker`: Door swing marker info (if found)
- `lines`: Window line segments (if found)
- `metadata`: Additional info

## Frontend Integration

### React Component: FloorPlanEditor.jsx

To integrate recognition results with the canvas editor:

```javascript
// Add "Recognize" button
const handleRecognize = async () => {
  const response = await axios.post(
    `/api/floor-plans/${floorPlanId}/process`
  );
  // Fetch results
  const result = await axios.get(
    `/api/floor-plans/${floorPlanId}/recognition`
  );
  // Update canvas with recognized elements
  updateCanvasFromRecognition(result.data.recognition_result);
};
```

### Element Rendering

Recognized elements from `recognition_result`:
- **Walls**: Render as lines using wall midline and thickness
- **Doors**: Render as rectangles at specified bbox coordinates
- **Windows**: Render as rectangles at specified bbox coordinates

## Testing

Run integration tests:

```bash
python test_recognition_api.py
```

Tests verify:
- Integrator creation and methods
- FloorplanRecognition model structure
- Result format and conversion
- Database model generation

## Performance

- **Processing Time**: ~300ms per 1500px image on modern CPU
- **Database Storage**: Recognition result stored as JSON (typically 5-50 KB)
- **Memory**: ~50-100 MB per processing operation

## Error Handling

- If processing fails, `status` is set to "failed"
- `error_message` contains the exception text
- User receives 500 error with descriptive message
- Can retry the same floor plan to re-process

## Future Enhancements

1. **Debug Mode**: Add `?debug=true` parameter to save intermediate images
2. **Confidence Filtering**: Filter results by confidence threshold
3. **Room Detection**: Extend to detect enclosed rooms from walls
4. **Dimension Extraction**: OCR-based text/dimension detection
5. **Machine Learning**: Train models to improve accuracy on specific floor plan styles
