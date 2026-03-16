"""Floor plan routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile

from backend.dependencies import get_floor_plan_use_cases
from backend.mappers import floor_plan_read
from backend.modules.floor_plans.application.use_cases import FloorPlanUseCases
from backend.schemas import FloorPlanCreate, FloorPlanRead, FloorPlanUpdate, MessageRead


router = APIRouter(tags=["floor-plans"])


@router.post("/api/floor-plans", response_model=FloorPlanRead)
async def create_floor_plan(
    project_id: int = Form(...),
    floor_number: int = Form(...),
    name: str | None = Form(None),
    scale_factor: float = Form(1.0),
    ceiling_height_mm: float = Form(3000.0),
    file: UploadFile | None = File(None),
    service: FloorPlanUseCases = Depends(get_floor_plan_use_cases),
) -> FloorPlanRead:
    payload = FloorPlanCreate(
        project_id=project_id,
        floor_number=floor_number,
        name=name,
        scale_factor=scale_factor,
        ceiling_height_mm=ceiling_height_mm,
    )
    return floor_plan_read(service.create_floor_plan(payload, upload_file=file), include_elements=True)


@router.get("/api/floor-plans/{floor_plan_id}", response_model=FloorPlanRead)
def get_floor_plan(
    floor_plan_id: int,
    include_elements: bool = True,
    service: FloorPlanUseCases = Depends(get_floor_plan_use_cases),
) -> FloorPlanRead:
    return floor_plan_read(service.get_floor_plan(floor_plan_id, include_elements=include_elements), include_elements=include_elements)


@router.get("/api/projects/{project_id}/floor-plans", response_model=list[FloorPlanRead])
def list_project_floor_plans(
    project_id: int,
    service: FloorPlanUseCases = Depends(get_floor_plan_use_cases),
) -> list[FloorPlanRead]:
    return [floor_plan_read(item, include_elements=False) for item in service.list_project_floor_plans(project_id)]


@router.patch("/api/floor-plans/{floor_plan_id}", response_model=FloorPlanRead)
def update_floor_plan(
    floor_plan_id: int,
    payload: FloorPlanUpdate,
    service: FloorPlanUseCases = Depends(get_floor_plan_use_cases),
) -> FloorPlanRead:
    return floor_plan_read(service.update_floor_plan(floor_plan_id, payload), include_elements=True)


@router.delete("/api/floor-plans/{floor_plan_id}", response_model=MessageRead)
def delete_floor_plan(
    floor_plan_id: int,
    service: FloorPlanUseCases = Depends(get_floor_plan_use_cases),
) -> MessageRead:
    service.delete_floor_plan(floor_plan_id)
    return MessageRead(message="Floor plan deleted successfully")
