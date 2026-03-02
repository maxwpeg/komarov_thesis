from fastapi import FastAPI, UploadFile, File, Depends, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
import uvicorn
import json
import io
import os
import shutil
from datetime import datetime
from PIL import Image
from ultralytics import YOLO
import sys

# Add backend directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from backend.database import get_db, init_db
from backend.models import (
    Project as ProjectModel,
    FloorPlan as FloorPlanModel,
    Wall as WallModel,
    Door as DoorModel,
    Window as WindowModel,
    Room as RoomModel,
    Dimension as DimensionModel,
    FireAlarm as FireAlarmModel
)
from backend.image_processor import FloorPlanProcessor
from backend.pdf_generator import generate_project_pdf
from backend.fire_alarm_placement import calculate_fire_alarm_layout

# Import for PDF font registration
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

app = FastAPI(title="Floor Plan API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
def on_startup():
    init_db()
    
    # Register PDF fonts
    try:
        pdfmetrics.registerFont(TTFont("GOST Type A", "./GOST_A.TTF"))
        pdfmetrics.registerFont(TTFont("GOST Type A Bold", "./GOST_A_BOLD.TTF"))
        print("✓ PDF fonts registered successfully")
    except Exception as e:
        print(f"⚠ Warning: Could not register PDF fonts: {e}")
    
    # Create uploads directory
    os.makedirs("uploads", exist_ok=True)
    os.makedirs("outputs", exist_ok=True)

# Mount static files for serving uploaded images
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# Load YOLO model
model = YOLO("yolov8n-seg.pt")

# Initialize floor plan processor
floor_plan_processor = FloorPlanProcessor()

# ==================== Pydantic Schemas ====================

class ProjectCreate(BaseModel):
    name: str
    project_type: str = "ПС"
    contractor: str
    engineer: str
    cpe: str
    checker: str
    facility: str
    facility_address: Optional[str] = None
    project_description: Optional[str] = None
    stage: str = "«Р»"
    number_of_floors: int = 1

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    contractor: Optional[str] = None
    engineer: Optional[str] = None
    cpe: Optional[str] = None
    checker: Optional[str] = None
    facility: Optional[str] = None
    facility_address: Optional[str] = None
    project_description: Optional[str] = None
    stage: Optional[str] = None
    number_of_floors: Optional[int] = None

class FloorPlanCreate(BaseModel):
    project_id: int
    floor_number: int
    name: Optional[str] = None
    scale_factor: float = 1.0

class WallCreate(BaseModel):
    floor_plan_id: int
    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float = 200.0
    is_load_bearing: bool = False
    material: Optional[str] = None

class DoorCreate(BaseModel):
    floor_plan_id: int
    x: float
    y: float
    width: float
    height: float
    door_type: str = "standard"
    swing_angle: float = 90.0
    swing_direction: Optional[str] = None

class WindowCreate(BaseModel):
    floor_plan_id: int
    x: float
    y: float
    width: float
    height: float
    window_type: str = "standard"

class RoomCreate(BaseModel):
    floor_plan_id: int
    name: Optional[str] = None
    room_type: Optional[str] = None
    room_number: Optional[str] = None
    boundary_points: Optional[List[List[float]]] = None

class DimensionCreate(BaseModel):
    floor_plan_id: int
    x: float
    y: float
    value: float
    unit: str = "mm"
    text: Optional[str] = None
    line_x1: Optional[float] = None
    line_y1: Optional[float] = None
    line_x2: Optional[float] = None
    line_y2: Optional[float] = None
    dimension_type: str = "linear"

class FireAlarmCreate(BaseModel):
    floor_plan_id: int
    x: float
    y: float
    device_type: str
    device_model: Optional[str] = None
    coverage_radius: Optional[float] = None
    mounting_height: Optional[float] = None
    zone: Optional[str] = None
    address: Optional[str] = None

class Annotation(BaseModel):
    objects: list

# ==================== Helper Functions ====================

def get_next_project_number(db: Session) -> int:
    """Get next available project number."""
    try:
        with open("project_counter.json", "r") as f:
            data = json.load(f)
            number = int(data.get("number_of_projects", 1))
    except:
        number = 1
    
    # Save incremented value
    with open("project_counter.json", "w") as f:
        json.dump({"number_of_projects": number + 1}, f)
    
    return number

# ==================== Project Endpoints ====================

@app.post("/api/projects", response_model=dict)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project."""
    number = get_next_project_number(db)
    year = datetime.now().year
    code = f"РП-ЗК-{number}/{year % 100}-{project.project_type}"
    
    db_project = ProjectModel(
        name=project.name,
        project_type=project.project_type,
        number=number,
        year=year,
        code=code,
        contractor=project.contractor,
        engineer=project.engineer,
        cpe=project.cpe,
        checker=project.checker,
        facility=project.facility,
        facility_address=project.facility_address,
        project_description=project.project_description,
        stage=project.stage,
        number_of_floors=project.number_of_floors
    )
    
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    
    return db_project.to_dict()

@app.get("/api/projects", response_model=List[dict])
def list_projects(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """List all projects."""
    projects = db.query(ProjectModel).offset(skip).limit(limit).all()
    return [p.to_dict() for p in projects]

@app.get("/api/projects/{project_id}", response_model=dict)
def get_project(project_id: int, db: Session = Depends(get_db)):
    """Get a specific project."""
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project.to_dict()

@app.patch("/api/projects/{project_id}", response_model=dict)
def update_project(project_id: int, project_update: ProjectUpdate, db: Session = Depends(get_db)):
    """Update a project."""
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    update_data = project_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(project, field, value)
    
    project.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(project)
    
    return project.to_dict()

@app.delete("/api/projects/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """Delete a project."""
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    db.delete(project)
    db.commit()
    
    return {"message": "Project deleted successfully"}

# ==================== Floor Plan Endpoints ====================

@app.post("/api/floor-plans", response_model=dict)
async def create_floor_plan(
    project_id: int = Form(...),
    floor_number: int = Form(...),
    name: Optional[str] = Form(None),
    scale_factor: float = Form(1.0),
    file: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db)
):
    """Create a new floor plan with optional image upload."""
    # Verify project exists
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Create floor plan
    db_floor_plan = FloorPlanModel(
        project_id=project_id,
        floor_number=floor_number,
        name=name or f"Floor {floor_number}",
        scale_factor=scale_factor
    )
    
    # Handle image upload
    if file:
        # Save original image
        file_extension = os.path.splitext(file.filename)[1]
        filename = f"floor_plan_{project_id}_{floor_number}_{datetime.now().timestamp()}{file_extension}"
        filepath = os.path.join("uploads", filename)
        
        with open(filepath, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Get image dimensions
        img = Image.open(filepath)
        db_floor_plan.original_image_path = filepath
        db_floor_plan.image_width = img.width
        db_floor_plan.image_height = img.height
    
    db.add(db_floor_plan)
    db.commit()
    db.refresh(db_floor_plan)
    
    return db_floor_plan.to_dict(include_elements=True)

@app.get("/api/floor-plans/{floor_plan_id}", response_model=dict)
def get_floor_plan(floor_plan_id: int, include_elements: bool = True, db: Session = Depends(get_db)):
    """Get a specific floor plan."""
    floor_plan = db.query(FloorPlanModel).filter(FloorPlanModel.id == floor_plan_id).first()
    if not floor_plan:
        raise HTTPException(status_code=404, detail="Floor plan not found")
    return floor_plan.to_dict(include_elements=include_elements)

@app.get("/api/projects/{project_id}/floor-plans", response_model=List[dict])
def list_project_floor_plans(project_id: int, db: Session = Depends(get_db)):
    """List all floor plans for a project."""
    floor_plans = db.query(FloorPlanModel).filter(FloorPlanModel.project_id == project_id).all()
    return [fp.to_dict(include_elements=False) for fp in floor_plans]

@app.delete("/api/floor-plans/{floor_plan_id}")
def delete_floor_plan(floor_plan_id: int, db: Session = Depends(get_db)):
    """Delete a floor plan."""
    floor_plan = db.query(FloorPlanModel).filter(FloorPlanModel.id == floor_plan_id).first()
    if not floor_plan:
        raise HTTPException(status_code=404, detail="Floor plan not found")
    
    # Delete associated image file
    if floor_plan.original_image_path and os.path.exists(floor_plan.original_image_path):
        os.remove(floor_plan.original_image_path)
    
    db.delete(floor_plan)
    db.commit()
    
    return {"message": "Floor plan deleted successfully"}

@app.post("/api/floor-plans/{floor_plan_id}/process")
async def process_floor_plan_image(floor_plan_id: int, db: Session = Depends(get_db)):
    """Process floor plan image to detect walls, dimensions, and rooms."""
    floor_plan = db.query(FloorPlanModel).filter(FloorPlanModel.id == floor_plan_id).first()
    if not floor_plan:
        raise HTTPException(status_code=404, detail="Floor plan not found")
    
    if not floor_plan.original_image_path or not os.path.exists(floor_plan.original_image_path):
        raise HTTPException(status_code=400, detail="Floor plan image not found")
    
    try:
        # Process the image
        results = floor_plan_processor.process_floor_plan(
            floor_plan.original_image_path,
            detect_text=True,
            detect_rooms=True
        )
        
        # Save detected walls
        for wall_data in results['walls']:
            wall = WallModel(
                floor_plan_id=floor_plan_id,
                x1=wall_data['x1'],
                y1=wall_data['y1'],
                x2=wall_data['x2'],
                y2=wall_data['y2'],
                thickness=200.0  # Default thickness
            )
            db.add(wall)
        
        # Save detected dimensions
        for dim_data in results['dimensions']:
            dimension = DimensionModel(
                floor_plan_id=floor_plan_id,
                x=dim_data['x'],
                y=dim_data['y'],
                value=dim_data['value'],
                unit=dim_data['unit'],
                text=dim_data['text']
            )
            db.add(dimension)
        
        # Save detected rooms
        for room_data in results['rooms']:
            room = RoomModel(
                floor_plan_id=floor_plan_id,
                boundary_points=room_data['boundary_points'],
                center_x=room_data['center_x'],
                center_y=room_data['center_y']
            )
            # Calculate area
            room.calculate_area(floor_plan.scale_factor)
            room.calculate_perimeter(floor_plan.scale_factor)
            db.add(room)
        
        db.commit()
        
        return {
            "message": "Floor plan processed successfully",
            "walls_detected": len(results['walls']),
            "dimensions_detected": len(results['dimensions']),
            "rooms_detected": len(results['rooms'])
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing floor plan: {str(e)}")
    db.commit()
    
    return {"message": "Floor plan deleted successfully"}

# ==================== Legacy Prediction Endpoint (Updated) ====================

@app.post("/predict")
async def predict(file: UploadFile = File(...)):
    """Legacy endpoint: Predict objects from uploaded floor plan image using YOLO."""
    contents = await file.read()
    img = Image.open(io.BytesIO(contents)).convert("RGB")

    results = model.predict(img, imgsz=640)
    objects = []

    for result in results:
        boxes = result.boxes
        for i, box in enumerate(boxes):
            xyxy = box.xyxy[0].tolist()
            cls = int(box.cls)
            label = model.names[cls]
            objects.append({
                "id": i,
                "type": label,
                "x": xyxy[0],
                "y": xyxy[1],
                "width": xyxy[2] - xyxy[0],
                "height": xyxy[3] - xyxy[1],
            })
    
    return {"objects": objects}

@app.post("/feedback")
async def feedback(annotation: Annotation):
    """Legacy endpoint: Save user feedback on annotations."""
    with open("user_feedback.json", "w") as f:
        json.dump(annotation.dict(), f, indent=2)
    return {"status": "saved"}

# ==================== Walls CRUD ====================

@app.post("/api/walls", response_model=dict)
def create_wall(wall: WallCreate, db: Session = Depends(get_db)):
    """Create a wall."""
    db_wall = WallModel(**wall.dict())
    db.add(db_wall)
    db.commit()
    db.refresh(db_wall)
    return db_wall.to_dict()

@app.get("/api/floor-plans/{floor_plan_id}/walls", response_model=List[dict])
def list_walls(floor_plan_id: int, db: Session = Depends(get_db)):
    """List all walls for a floor plan."""
    walls = db.query(WallModel).filter(WallModel.floor_plan_id == floor_plan_id).all()
    return [w.to_dict() for w in walls]

@app.patch("/api/walls/{wall_id}", response_model=dict)
def update_wall(wall_id: int, wall_update: WallCreate, db: Session = Depends(get_db)):
    """Update a wall."""
    wall = db.query(WallModel).filter(WallModel.id == wall_id).first()
    if not wall:
        raise HTTPException(status_code=404, detail="Wall not found")
    
    for field, value in wall_update.dict(exclude_unset=True).items():
        setattr(wall, field, value)
    
    db.commit()
    db.refresh(wall)
    return wall.to_dict()

@app.delete("/api/walls/{wall_id}")
def delete_wall(wall_id: int, db: Session = Depends(get_db)):
    """Delete a wall."""
    wall = db.query(WallModel).filter(WallModel.id == wall_id).first()
    if not wall:
        raise HTTPException(status_code=404, detail="Wall not found")
    
    db.delete(wall)
    db.commit()
    return {"message": "Wall deleted"}

# ==================== Doors CRUD ====================

@app.post("/api/doors", response_model=dict)
def create_door(door: DoorCreate, db: Session = Depends(get_db)):
    """Create a door."""
    db_door = DoorModel(**door.dict())
    db.add(db_door)
    db.commit()
    db.refresh(db_door)
    return db_door.to_dict()

@app.get("/api/floor-plans/{floor_plan_id}/doors", response_model=List[dict])
def list_doors(floor_plan_id: int, db: Session = Depends(get_db)):
    """List all doors for a floor plan."""
    doors = db.query(DoorModel).filter(DoorModel.floor_plan_id == floor_plan_id).all()
    return [d.to_dict() for d in doors]

@app.delete("/api/doors/{door_id}")
def delete_door(door_id: int, db: Session = Depends(get_db)):
    """Delete a door."""
    door = db.query(DoorModel).filter(DoorModel.id == door_id).first()
    if not door:
        raise HTTPException(status_code=404, detail="Door not found")
    
    db.delete(door)
    db.commit()
    return {"message": "Door deleted"}

# ==================== Windows CRUD ====================

@app.post("/api/windows", response_model=dict)
def create_window(window: WindowCreate, db: Session = Depends(get_db)):
    """Create a window."""
    db_window = WindowModel(**window.dict())
    db.add(db_window)
    db.commit()
    db.refresh(db_window)
    return db_window.to_dict()

@app.get("/api/floor-plans/{floor_plan_id}/windows", response_model=List[dict])
def list_windows(floor_plan_id: int, db: Session = Depends(get_db)):
    """List all windows for a floor plan."""
    windows = db.query(WindowModel).filter(WindowModel.floor_plan_id == floor_plan_id).all()
    return [w.to_dict() for w in windows]

@app.delete("/api/windows/{window_id}")
def delete_window(window_id: int, db: Session = Depends(get_db)):
    """Delete a window."""
    window = db.query(WindowModel).filter(WindowModel.id == window_id).first()
    if not window:
        raise HTTPException(status_code=404, detail="Window not found")
    
    db.delete(window)
    db.commit()
    return {"message": "Window deleted"}

# ==================== Rooms CRUD ====================

@app.post("/api/rooms", response_model=dict)
def create_room(room: RoomCreate, db: Session = Depends(get_db)):
    """Create a room and calculate its area."""
    floor_plan = db.query(FloorPlanModel).filter(FloorPlanModel.id == room.floor_plan_id).first()
    if not floor_plan:
        raise HTTPException(status_code=404, detail="Floor plan not found")
    
    db_room = RoomModel(**room.dict())
    
    # Calculate area and center if boundary points provided
    if db_room.boundary_points:
        db_room.calculate_area(floor_plan.scale_factor)
        db_room.calculate_perimeter(floor_plan.scale_factor)
        db_room.calculate_center()
    
    db.add(db_room)
    db.commit()
    db.refresh(db_room)
    return db_room.to_dict()

@app.get("/api/floor-plans/{floor_plan_id}/rooms", response_model=List[dict])
def list_rooms(floor_plan_id: int, db: Session = Depends(get_db)):
    """List all rooms for a floor plan."""
    rooms = db.query(RoomModel).filter(RoomModel.floor_plan_id == floor_plan_id).all()
    return [r.to_dict() for r in rooms]

@app.patch("/api/rooms/{room_id}", response_model=dict)
def update_room(room_id: int, room_update: RoomCreate, db: Session = Depends(get_db)):
    """Update a room."""
    room = db.query(RoomModel).filter(RoomModel.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    floor_plan = db.query(FloorPlanModel).filter(FloorPlanModel.id == room.floor_plan_id).first()
    
    for field, value in room_update.dict(exclude_unset=True).items():
        setattr(room, field, value)
    
    # Recalculate if boundary changed
    if room.boundary_points:
        room.calculate_area(floor_plan.scale_factor)
        room.calculate_perimeter(floor_plan.scale_factor)
        room.calculate_center()
    
    db.commit()
    db.refresh(room)
    return room.to_dict()

@app.delete("/api/rooms/{room_id}")
def delete_room(room_id: int, db: Session = Depends(get_db)):
    """Delete a room."""
    room = db.query(RoomModel).filter(RoomModel.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="Room not found")
    
    db.delete(room)
    db.commit()
    return {"message": "Room deleted"}

# ==================== Dimensions CRUD ====================

@app.post("/api/dimensions", response_model=dict)
def create_dimension(dimension: DimensionCreate, db: Session = Depends(get_db)):
    """Create a dimension annotation."""
    db_dimension = DimensionModel(**dimension.dict())
    db.add(db_dimension)
    db.commit()
    db.refresh(db_dimension)
    return db_dimension.to_dict()

@app.get("/api/floor-plans/{floor_plan_id}/dimensions", response_model=List[dict])
def list_dimensions(floor_plan_id: int, db: Session = Depends(get_db)):
    """List all dimensions for a floor plan."""
    dimensions = db.query(DimensionModel).filter(DimensionModel.floor_plan_id == floor_plan_id).all()
    return [d.to_dict() for d in dimensions]

@app.delete("/api/dimensions/{dimension_id}")
def delete_dimension(dimension_id: int, db: Session = Depends(get_db)):
    """Delete a dimension."""
    dimension = db.query(DimensionModel).filter(DimensionModel.id == dimension_id).first()
    if not dimension:
        raise HTTPException(status_code=404, detail="Dimension not found")
    
    db.delete(dimension)
    db.commit()
    return {"message": "Dimension deleted"}

# ==================== Fire Alarms CRUD ====================

@app.post("/api/fire-alarms", response_model=dict)
def create_fire_alarm(fire_alarm: FireAlarmCreate, db: Session = Depends(get_db)):
    """Create a fire alarm device."""
    db_fire_alarm = FireAlarmModel(**fire_alarm.dict())
    db.add(db_fire_alarm)
    db.commit()
    db.refresh(db_fire_alarm)
    return db_fire_alarm.to_dict()

@app.get("/api/floor-plans/{floor_plan_id}/fire-alarms", response_model=List[dict])
def list_fire_alarms(floor_plan_id: int, db: Session = Depends(get_db)):
    """List all fire alarms for a floor plan."""
    fire_alarms = db.query(FireAlarmModel).filter(FireAlarmModel.floor_plan_id == floor_plan_id).all()
    return [fa.to_dict() for fa in fire_alarms]

@app.delete("/api/fire-alarms/{fire_alarm_id}")
def delete_fire_alarm(fire_alarm_id: int, db: Session = Depends(get_db)):
    """Delete a fire alarm."""
    fire_alarm = db.query(FireAlarmModel).filter(FireAlarmModel.id == fire_alarm_id).first()
    if not fire_alarm:
        raise HTTPException(status_code=404, detail="Fire alarm not found")
    
    db.delete(fire_alarm)
    db.commit()
    return {"message": "Fire alarm deleted"}

@app.post("/api/floor-plans/{floor_plan_id}/calculate-fire-alarms")
async def calculate_fire_alarms(floor_plan_id: int, db: Session = Depends(get_db)):
    """Calculate and place fire alarm devices for a floor plan."""
    floor_plan = db.query(FloorPlanModel).filter(FloorPlanModel.id == floor_plan_id).first()
    if not floor_plan:
        raise HTTPException(status_code=404, detail="Floor plan not found")
    
    try:
        # Get floor plan data with all elements
        floor_plan_data = floor_plan.to_dict(include_elements=True)
        
        # Calculate fire alarm layout
        fire_alarm_layout = calculate_fire_alarm_layout(
            floor_plan_data,
            scale_factor=floor_plan.scale_factor
        )
        
        # Delete existing fire alarms for this floor plan
        db.query(FireAlarmModel).filter(FireAlarmModel.floor_plan_id == floor_plan_id).delete()
        
        # Add new fire alarms
        for device in fire_alarm_layout["all_devices"]:
            fire_alarm = FireAlarmModel(
                floor_plan_id=floor_plan_id,
                x=device["x"],
                y=device["y"],
                device_type=device["device_type"],
                coverage_radius=device.get("coverage_radius"),
                mounting_height=device.get("mounting_height"),
                zone=device.get("zone"),
                address=device.get("address")
            )
            db.add(fire_alarm)
        
        db.commit()
        
        return {
            "message": "Fire alarm devices calculated and placed successfully",
            "summary": fire_alarm_layout["summary"]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating fire alarms: {str(e)}")

# ==================== Health Check ====================

@app.get("/")
def root():
    """API health check."""
    return {"status": "ok", "message": "Floor Plan API is running"}

# ==================== PDF Generation ====================

@app.post("/api/projects/{project_id}/generate-pdf")
async def generate_pdf(project_id: int, db: Session = Depends(get_db)):
    """Generate PDF for a project with all floor plans."""
    # Get project
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get all floor plans with elements
    floor_plans = db.query(FloorPlanModel).filter(FloorPlanModel.project_id == project_id).all()
    
    if not floor_plans:
        raise HTTPException(status_code=400, detail="No floor plans found for this project")
    
    # Prepare floor plans data
    floor_plans_data = []
    for fp in floor_plans:
        floor_plans_data.append(fp.to_dict(include_elements=True))
    
    try:
        # Generate PDF
        pdf_path = generate_project_pdf(
            project.to_dict(),
            floor_plans_data,
            output_dir="outputs"
        )
        
        # Return PDF file
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename=os.path.basename(pdf_path)
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

