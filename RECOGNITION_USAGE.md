# Floor Plan Recognition Usage Guide

## Quick Start

### 1. Upload a Floor Plan

```bash
curl -X POST "http://localhost:8000/api/floor-plans" \
  -F "project_id=1" \
  -F "floor_number=1" \
  -F "name=Ground Floor" \
  -F "scale_factor=1.0" \
  -F "file=@floor_plan.jpg"
```

**Response:**
```json
{
  "id": 5,
  "project_id": 1,
  "floor_number": 1,
  "name": "Ground Floor",
  "original_image_path": "uploads/floor_plan_1_1_1768307886.144434.jpeg",
  "image_width": 1500,
  "image_height": 1200,
  "scale_factor": 1.0,
  "created_at": "2024-01-15T10:00:00"
}
```

**Note the `id` from the response** - you'll use it for recognition.

### 2. Trigger Recognition

Use the `floor_plan_id` from the upload response:

```bash
curl -X POST "http://localhost:8000/api/floor-plans/5/process"
```

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

The system will:
- Analyze the uploaded image using computer vision
- Detect all walls, doors, and windows
- Save results to the database
- Automatically create Wall, Door, and Window records

### 3. Retrieve Recognition Results

```bash
curl -X GET "http://localhost:8000/api/floor-plans/5/recognition"
```

**Response includes:**
- Detailed wall coordinates and properties
- Door and window locations
- Confidence scores for each detection
- Original image dimensions and scale

### 4. Access Recognized Elements

Individual element endpoints:

```bash
# Get walls
curl "http://localhost:8000/api/floor-plans/5/walls"

# Get doors
curl "http://localhost:8000/api/floor-plans/5/doors"

# Get windows
curl "http://localhost:8000/api/floor-plans/5/windows"
```

## Python Example

```python
import requests
import json

BASE_URL = "http://localhost:8000/api"

# Upload floor plan
with open("floor_plan.jpg", "rb") as f:
    response = requests.post(
        f"{BASE_URL}/floor-plans",
        data={"project_id": 1, "floor_number": 1},
        files={"file": f}
    )
    floor_plan_id = response.json()["id"]
    print(f"Created floor plan: {floor_plan_id}")

# Trigger recognition
response = requests.post(f"{BASE_URL}/floor-plans/{floor_plan_id}/process")
print(f"Recognition response: {response.json()}")

# Retrieve results
response = requests.get(f"{BASE_URL}/floor-plans/{floor_plan_id}/recognition")
results = response.json()

# Process recognized elements
print(f"Walls detected: {len(results['recognition_result']['walls'])}")
print(f"Doors detected: {len(results['recognition_result']['openings'])} doors")

# Get individual elements
walls = requests.get(f"{BASE_URL}/floor-plans/{floor_plan_id}/walls").json()
doors = requests.get(f"{BASE_URL}/floor-plans/{floor_plan_id}/doors").json()
windows = requests.get(f"{BASE_URL}/floor-plans/{floor_plan_id}/windows").json()

print(f"Database walls: {len(walls)}")
print(f"Database doors: {len(doors)}")
print(f"Database windows: {len(windows)}")
```

## Frontend Integration (React)

### Display Results in FloorPlanEditor

```javascript
import axios from 'axios';

const FloorPlanEditor = ({ floorPlanId }) => {
  const [recognition, setRecognition] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleRecognize = async () => {
    try {
      setLoading(true);
      
      // Trigger recognition
      const response = await axios.post(
        `/api/floor-plans/${floorPlanId}/process`
      );
      console.log('Recognition started:', response.data);
      
      // Fetch recognition results
      const result = await axios.get(
        `/api/floor-plans/${floorPlanId}/recognition`
      );
      
      setRecognition(result.data.recognition_result);
      
      // Load elements into editor
      await loadElementsFromRecognition(floorPlanId);
      
    } catch (error) {
      console.error('Recognition failed:', error);
      alert('Failed to recognize floor plan');
    } finally {
      setLoading(false);
    }
  };

  const loadElementsFromRecognition = async (floorPlanId) => {
    const [walls, doors, windows] = await Promise.all([
      axios.get(`/api/floor-plans/${floorPlanId}/walls`),
      axios.get(`/api/floor-plans/${floorPlanId}/doors`),
      axios.get(`/api/floor-plans/${floorPlanId}/windows`),
    ]);
    
    // Update canvas with recognized elements
    // (Implementation depends on your Konva setup)
    updateCanvasElements(walls.data, doors.data, windows.data);
  };

  return (
    <div>
      <button 
        onClick={handleRecognize}
        disabled={loading}
      >
        {loading ? 'Recognizing...' : 'Auto-Recognize'}
      </button>
      
      {recognition && (
        <div className="recognition-stats">
          <p>Walls: {recognition.walls.length}</p>
          <p>Openings: {recognition.openings.length}</p>
        </div>
      )}
      
      {/* Canvas and other editor content */}
    </div>
  );
};
```

## Workflow

```
1. User uploads floor plan image (POST /api/floor-plans)
   ↓
2. System saves image and creates FloorPlan record
   ↓
3. User clicks "Auto-Recognize" button
   ↓
4. Backend processes image with CV (POST /api/floor-plans/{id}/process)
   ↓
5. Recognizer detects walls, doors, windows
   ↓
6. Results saved to DB (FloorplanRecognition + Wall + Door + Window)
   ↓
7. Frontend fetches results (GET /api/floor-plans/{id}/recognition)
   ↓
8. User can view/edit recognized elements on canvas
   ↓
9. User can manually adjust positions, add/remove elements
   ↓
10. Save to database (existing endpoints)
```

## Supported Image Formats

- JPEG (`.jpg`, `.jpeg`)
- PNG (`.png`)
- TIFF (`.tif`, `.tiff`)
- BMP (`.bmp`)

**Recommended:** JPG or PNG for floor plans (typical size: 1000-2000 pixels width)

## Recognition Performance

| Image Size | Processing Time | Accuracy |
|-----------|-----------------|----------|
| ≤500px    | ~50ms           | Good     |
| 500-1500px| ~200-300ms      | Excellent|
| 1500-3000px| ~500-800ms     | Excellent|
| >3000px   | >1s             | Good*    |

*Larger images may need downsampling before processing.

## Troubleshooting

### "Floor plan image not found"
- Check that the upload succeeded and file path is correct
- Verify the image file exists in the `uploads/` directory

### Recognition produces no results
- Image may not be a clear floor plan
- Try rotating or adjusting contrast beforehand
- Manual editing is always available

### Many false positives/negatives
- Algorithm works best with standard architectural floor plans
- Hand-drawn or low-quality scans may not work as well
- Consider preprocessing the image (contrast enhancement, rotation)

### Recognition takes too long
- For very large images (>2000px), consider resizing first
- Server performance depends on CPU capability
- Results are cached in database after first run

## Advanced: Debug Mode

(Future feature) To save intermediate processing images:

```bash
curl "http://localhost:8000/api/floor-plans/5/process?debug=true"
```

This will:
- Save binarized image
- Save detected edges
- Save detected lines
- Save final wall traces
- Save opening detection results

All saved to `debug_artifacts_dir` in the database record.

## Limitations & Future Work

### Current Limitations
- Works with axis-aligned walls (0°, 90°, 180°, 270°)
- Diagonal walls detected but may have lower accuracy
- Small or merged rooms may not be detected separately
- Dimensions/text not OCR'd (could be added in future)

### Planned Improvements
- [ ] Room detection and perimeter calculation
- [ ] Dimension text OCR
- [ ] Fire alarm placement assistance
- [ ] Machine learning models for custom styles
- [ ] Batch processing multiple floor plans
- [ ] Confidence filtering UI
- [ ] Undo/redo for recognition corrections
