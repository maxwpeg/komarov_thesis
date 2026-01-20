# Floor Plan Management System

A comprehensive web application for parsing floor plan images, editing architectural elements, calculating room areas, and generating fire alarm system PDFs compliant with GOST standards.

## Features

### 🏗️ Core Functionality
- **Image Upload & Processing**: Upload floor plan images (JPG, PNG) and automatically detect:
  - Walls and structural elements using computer vision
  - Dimensions and measurements using OCR
  - Room boundaries and areas
  
- **Interactive Floor Plan Editor**:
  - Drag and reposition architectural elements
  - Add/remove/modify walls, doors, windows
  - Edit dimension annotations
  - Label and categorize rooms
  - Real-time area calculations

- **Room Management**:
  - Automatic room segmentation from floor plans
  - Area calculation (m²) using shoelace formula
  - Perimeter calculations
  - Room naming and categorization

- **Fire Alarm System Design**:
  - Automatic placement of fire detection devices
  - Smoke detector and heat detector distribution
  - Manual call point placement near exits
  - Sounder/beacon positioning
  - Zone assignment and device addressing
  
- **PDF Generation**:
  - GOST-compliant technical documentation
  - Title pages with project information
  - Floor plan drawings with fire alarm overlay
  - Professional formatting with signature blocks

## Technology Stack

### Backend
- **FastAPI**: Modern Python web framework
- **SQLAlchemy**: ORM for database management
- **SQLite**: Database (easily switchable to PostgreSQL)
- **OpenCV**: Computer vision for line detection
- **Pytesseract**: OCR for dimension text extraction
- **YOLOv8**: Object detection for architectural elements
- **ReportLab**: PDF generation
- **PIL (Pillow)**: Image processing

### Frontend
- **React 19**: UI framework
- **React Router**: Client-side routing
- **Konva & React-Konva**: Canvas-based drawing and editing
- **Axios**: HTTP client

## Installation

### Prerequisites
- Python 3.10 or higher
- Node.js 16 or higher
- Tesseract OCR installed on your system
  - **Windows**: Download from https://github.com/UB-Mannheim/tesseract/wiki
  - **Linux**: `sudo apt-get install tesseract-ocr`
  - **macOS**: `brew install tesseract`

### Backend Setup

1. **Navigate to project root**:
   ```bash
   cd komarov_thesis
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r backend/requirements.txt
   ```

3. **Configure Tesseract** (Windows only):
   Edit `backend/image_processor.py` and set the tesseract path:
   ```python
   pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
   ```

4. **Initialize database**:
   The database will be automatically created when you first run the server.

5. **Start the backend server**:
   ```bash
   python main.py
   ```
   Backend will run on http://localhost:8000

### Frontend Setup

1. **Navigate to frontend directory**:
   ```bash
   cd floorplan-ui
   ```

2. **Install Node.js dependencies**:
   ```bash
   npm install
   ```

3. **Start the development server**:
   ```bash
   npm start
   ```
   Frontend will run on http://localhost:3000

## Usage Guide

### Creating a Project

1. Navigate to http://localhost:3000
2. Click "New Project"
3. Fill in project details:
   - Project name and facility information
   - Contractor, engineer, and checker names
   - Project description
   - Number of floors
4. Click "Create Project"

### Uploading Floor Plans

1. Open your project
2. Click "Upload Floor Plan"
3. Select a floor plan image (JPG or PNG)
4. The system will automatically:
   - Detect walls using line detection
   - Extract dimensions using OCR
   - Identify room boundaries
   - Create room objects with area calculations

### Editing Floor Plans

1. Click on a floor plan to open the editor
2. Use the toolbar to:
   - **Select**: Click elements to select/move
   - **Draw Wall**: Add new walls
   - **Add Door/Window**: Place doors and windows
   - **Add Dimension**: Annotate measurements
   - **Add Fire Alarm**: Manually place devices

3. Sidebar shows all elements:
   - Click to select
   - Click × to delete
   - View room areas and properties

### Calculating Fire Alarms

The system can automatically calculate fire alarm device placement:

1. In the floor plan editor, process the floor plan
2. Use the API endpoint or add a button to trigger:
   ```
   POST /api/floor-plans/{floor_plan_id}/calculate-fire-alarms
   ```
3. The system will:
   - Calculate required smoke/heat detectors based on room areas
   - Place manual call points near exits
   - Position sounders for alarm notification
   - Assign zones and addresses to all devices

**Placement Rules** (customizable in `backend/fire_alarm_placement.py`):
- Smoke detectors: 7.5m radius coverage
- Heat detectors: 5m radius coverage (kitchens)
- Manual call points: Near all exits
- Sounders: 30m radius coverage
- Device addressing: Sequential (D001, M001, S001, etc.)
- Zone assignment: 32 devices per zone

### Generating PDFs

1. In the project detail view, click "Generate PDF"
2. The system creates a GOST-compliant PDF with:
   - Unsigned title page
   - Signed title page (with signature lines)
   - Floor plan drawings with fire alarm overlay
   - Room labels and areas
   - Device symbols and addresses

3. PDF automatically downloads

## API Documentation

Access interactive API docs at http://localhost:8000/docs when the backend is running.

### Key Endpoints

**Projects**:
- `POST /api/projects` - Create project
- `GET /api/projects` - List all projects
- `GET /api/projects/{id}` - Get project details
- `PATCH /api/projects/{id}` - Update project
- `DELETE /api/projects/{id}` - Delete project

**Floor Plans**:
- `POST /api/floor-plans` - Upload floor plan with image
- `GET /api/floor-plans/{id}` - Get floor plan with elements
- `POST /api/floor-plans/{id}/process` - Process image (detect walls, OCR)
- `POST /api/floor-plans/{id}/calculate-fire-alarms` - Calculate fire alarm layout
- `DELETE /api/floor-plans/{id}` - Delete floor plan

**Elements** (Walls, Doors, Windows, Rooms, Dimensions, Fire Alarms):
- `POST /api/{element_type}` - Create element
- `GET /api/floor-plans/{id}/{element_type}` - List elements
- `PATCH /api/{element_type}/{id}` - Update element
- `DELETE /api/{element_type}/{id}` - Delete element

**PDF Generation**:
- `POST /api/projects/{id}/generate-pdf` - Generate complete PDF

## Project Structure

```
komarov_thesis/
├── backend/
│   ├── models.py              # SQLAlchemy database models
│   ├── database.py            # Database configuration
│   ├── image_processor.py     # Computer vision & OCR
│   ├── fire_alarm_placement.py # Fire alarm algorithm
│   ├── pdf_generator.py       # PDF generation service
│   └── requirements.txt       # Python dependencies
├── floorplan-ui/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── ProjectList.jsx
│   │   │   ├── ProjectDetail.jsx
│   │   │   ├── CreateProject.jsx
│   │   │   └── FloorPlanEditor.jsx
│   │   ├── App.jsx
│   │   └── App.css
│   └── package.json
├── main.py                    # FastAPI backend server
├── Page.py                    # Base page class (GOST)
├── TitlePage.py               # Title page generator
├── DrawingPage.py             # Drawing page class
├── Project.py                 # PDF project orchestrator
├── consts.py                  # GOST constants
├── yolov8n-seg.pt            # YOLO model weights
└── README_APP.md             # This file
```

## Configuration

### Fire Alarm Parameters

Edit `backend/fire_alarm_placement.py` to customize:

```python
DEFAULT_SMOKE_DETECTOR_RADIUS = 7500  # mm (7.5m)
DEFAULT_HEAT_DETECTOR_RADIUS = 5000   # mm (5m)
DEFAULT_MANUAL_CALL_POINT_DISTANCE = 45000  # mm (45m)
DEFAULT_SOUNDER_RADIUS = 30000  # mm (30m)
DEFAULT_CEILING_HEIGHT = 3000  # mm (3m)
```

### Scale Factor

When uploading floor plans, set the scale factor (mm per pixel):
- Default: 10 mm/pixel
- Adjust based on your floor plan scale

### GOST Constants

Modify `consts.py` to change:
- Default contractor/engineer names
- Border sizes and margins
- Title box configurations
- Font sizes and styles

## Troubleshooting

### Tesseract OCR Not Found
**Error**: `TesseractNotFoundError`
**Solution**: Install Tesseract and set the path in `backend/image_processor.py`:
```python
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
```

### Database Errors
**Solution**: Delete `floor_plans.db` and restart the server to recreate the database.

### CORS Errors
**Solution**: Ensure the backend CORS middleware is configured to allow `http://localhost:3000`.

### YOLOv8 Model Not Found
**Solution**: The model file `yolov8n-seg.pt` should be in the project root. Download from:
```bash
pip install ultralytics
# Model will auto-download on first use
```

### Image Upload Fails
**Solution**: Check that the `uploads/` directory exists and has write permissions.

## Development

### Adding New Room Types

Edit `backend/fire_alarm_placement.py`:
```python
if room_type in ["kitchen", "cooking", "boiler_room"]:
    detector_type = "heat_detector"
```

### Customizing PDF Layout

Modify `backend/pdf_generator.py` to change:
- Page sizes (A3, A4, landscape)
- Title box types
- Drawing area dimensions

### Training Custom YOLO Model

1. Collect floor plan images
2. Annotate with labels: wall, door, window, room
3. Train YOLOv8:
   ```python
   from ultralytics import YOLO
   model = YOLO('yolov8n-seg.pt')
   model.train(data='floor_plans.yaml', epochs=100)
   ```
4. Replace `yolov8n-seg.pt` with trained model

## License

This project uses existing GOST-compliant PDF generation classes and extends them with computer vision and fire alarm placement capabilities.

## Support

For issues or questions, refer to the code documentation or check the API docs at `/docs`.

## Future Enhancements

- [ ] Multi-floor navigation in UI
- [ ] Advanced room editing (polygon drawing)
- [ ] Fire alarm wiring diagrams
- [ ] Export to DWG/DXF formats
- [ ] 3D floor plan visualization
- [ ] Integration with fire alarm equipment databases
- [ ] Compliance checking against building codes
- [ ] Mobile-responsive editor
- [ ] Real-time collaboration
- [ ] Cloud deployment guide
