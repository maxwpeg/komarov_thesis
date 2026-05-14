"""Equipment catalog routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from backend.audit import record_audit_event
from backend.auth import AuthenticatedUser, require_current_user, require_developer, require_project_access
from backend.database import get_db
from backend.dependencies import get_equipment_use_cases
from backend.mappers import equipment_item_read, project_equipment_list_read, project_equipment_selections_read
from backend.modules.equipment.application.use_cases import EquipmentUseCases
from backend.schemas import (
    EquipmentItemCreate,
    EquipmentItemRead,
    EquipmentItemUpdate,
    MessageRead,
    ProjectEquipmentAttach,
    ProjectEquipmentListRead,
    ProjectEquipmentSelectionsRead,
    ProjectEquipmentSelectionsUpdate,
)


router = APIRouter(tags=["equipment"])


@router.get("/api/equipment", response_model=list[EquipmentItemRead])
def list_equipment(
    _: AuthenticatedUser = Depends(require_current_user),
    service: EquipmentUseCases = Depends(get_equipment_use_cases),
) -> list[EquipmentItemRead]:
    return [equipment_item_read(item) for item in service.list_items()]


@router.get("/api/equipment/{equipment_id}", response_model=EquipmentItemRead)
def get_equipment(
    equipment_id: int,
    _: AuthenticatedUser = Depends(require_current_user),
    service: EquipmentUseCases = Depends(get_equipment_use_cases),
) -> EquipmentItemRead:
    return equipment_item_read(service.get_item(equipment_id))


@router.post("/api/equipment", response_model=EquipmentItemRead)
def create_equipment(
    payload: EquipmentItemCreate,
    current_user: AuthenticatedUser = Depends(require_developer),
    db: Session = Depends(get_db),
    service: EquipmentUseCases = Depends(get_equipment_use_cases),
) -> EquipmentItemRead:
    item = service.create_item(payload)
    record_audit_event(
        db,
        "equipment_created",
        category="equipment",
        use_case="CreateEquipment",
        user_id=current_user.id,
        payload={"equipment_id": item.id, "category": item.category},
    )
    db.commit()
    return equipment_item_read(item)


@router.patch("/api/equipment/{equipment_id}", response_model=EquipmentItemRead)
def update_equipment(
    equipment_id: int,
    payload: EquipmentItemUpdate,
    current_user: AuthenticatedUser = Depends(require_developer),
    db: Session = Depends(get_db),
    service: EquipmentUseCases = Depends(get_equipment_use_cases),
) -> EquipmentItemRead:
    item = service.update_item(equipment_id, payload)
    record_audit_event(
        db,
        "equipment_updated",
        category="equipment",
        use_case="UpdateEquipment",
        user_id=current_user.id,
        payload={"equipment_id": equipment_id, "fields": sorted(payload.model_dump(exclude_unset=True).keys())},
    )
    db.commit()
    return equipment_item_read(item)


@router.delete("/api/equipment/{equipment_id}", response_model=MessageRead)
def delete_equipment(
    equipment_id: int,
    current_user: AuthenticatedUser = Depends(require_developer),
    db: Session = Depends(get_db),
    service: EquipmentUseCases = Depends(get_equipment_use_cases),
) -> MessageRead:
    service.delete_item(equipment_id)
    record_audit_event(
        db,
        "equipment_deleted",
        category="equipment",
        use_case="DeleteEquipment",
        user_id=current_user.id,
        payload={"equipment_id": equipment_id},
    )
    db.commit()
    return MessageRead(message="Equipment item deleted successfully")


@router.post("/api/equipment/{equipment_id}/image", response_model=EquipmentItemRead)
def upload_equipment_image(
    equipment_id: int,
    image: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(require_developer),
    db: Session = Depends(get_db),
    service: EquipmentUseCases = Depends(get_equipment_use_cases),
) -> EquipmentItemRead:
    item = service.set_item_image(equipment_id, image)
    record_audit_event(
        db,
        "equipment_image_uploaded",
        category="equipment",
        use_case="UploadEquipmentImage",
        user_id=current_user.id,
        payload={"equipment_id": equipment_id, "path": item.image_path},
    )
    db.commit()
    return equipment_item_read(item)


@router.post("/api/equipment/{equipment_id}/connection-diagram", response_model=EquipmentItemRead)
def upload_equipment_connection_diagram(
    equipment_id: int,
    image: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(require_developer),
    db: Session = Depends(get_db),
    service: EquipmentUseCases = Depends(get_equipment_use_cases),
) -> EquipmentItemRead:
    item = service.set_item_connection_diagram(equipment_id, image)
    record_audit_event(
        db,
        "equipment_connection_diagram_uploaded",
        category="equipment",
        use_case="UploadEquipmentConnectionDiagram",
        user_id=current_user.id,
        payload={"equipment_id": equipment_id, "path": item.connection_diagram_path},
    )
    db.commit()
    return equipment_item_read(item)


@router.post("/api/equipment/{equipment_id}/label-pdf", response_model=EquipmentItemRead)
def upload_equipment_label_pdf(
    equipment_id: int,
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(require_developer),
    db: Session = Depends(get_db),
    service: EquipmentUseCases = Depends(get_equipment_use_cases),
) -> EquipmentItemRead:
    item = service.set_item_label_pdf(equipment_id, file)
    record_audit_event(
        db,
        "equipment_label_pdf_uploaded",
        category="equipment",
        use_case="UploadEquipmentLabelPdf",
        user_id=current_user.id,
        payload={"equipment_id": equipment_id, "path": item.label_pdf_path},
    )
    db.commit()
    return equipment_item_read(item)


@router.post("/api/equipment/{equipment_id}/manual-pdf", response_model=EquipmentItemRead)
def upload_equipment_manual_pdf(
    equipment_id: int,
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(require_developer),
    db: Session = Depends(get_db),
    service: EquipmentUseCases = Depends(get_equipment_use_cases),
) -> EquipmentItemRead:
    item = service.set_item_manual_pdf(equipment_id, file)
    record_audit_event(
        db,
        "equipment_manual_pdf_uploaded",
        category="equipment",
        use_case="UploadEquipmentManualPdf",
        user_id=current_user.id,
        payload={"equipment_id": equipment_id, "path": item.manual_pdf_path},
    )
    db.commit()
    return equipment_item_read(item)


@router.get("/api/projects/{project_id}/equipment", response_model=ProjectEquipmentListRead)
def get_project_equipment(
    project_id: int,
    _: AuthenticatedUser = Depends(require_project_access),
    service: EquipmentUseCases = Depends(get_equipment_use_cases),
) -> ProjectEquipmentListRead:
    result = service.get_project_equipment(project_id)
    return project_equipment_list_read(result.project_id, result.items)


@router.post("/api/projects/{project_id}/equipment", response_model=ProjectEquipmentListRead)
def attach_project_equipment(
    project_id: int,
    payload: ProjectEquipmentAttach,
    _: AuthenticatedUser = Depends(require_project_access),
    service: EquipmentUseCases = Depends(get_equipment_use_cases),
) -> ProjectEquipmentListRead:
    result = service.attach_item_to_project(project_id, payload)
    return project_equipment_list_read(result.project_id, result.items)


@router.post("/api/projects/{project_id}/equipment/create", response_model=ProjectEquipmentListRead)
def create_and_attach_project_equipment(
    project_id: int,
    payload: EquipmentItemCreate,
    _: AuthenticatedUser = Depends(require_developer),
    service: EquipmentUseCases = Depends(get_equipment_use_cases),
) -> ProjectEquipmentListRead:
    result = service.create_and_attach_item(project_id, payload)
    return project_equipment_list_read(result.project_id, result.items)


@router.delete("/api/projects/{project_id}/equipment/{equipment_id}", response_model=ProjectEquipmentListRead)
def remove_project_equipment(
    project_id: int,
    equipment_id: int,
    _: AuthenticatedUser = Depends(require_project_access),
    service: EquipmentUseCases = Depends(get_equipment_use_cases),
) -> ProjectEquipmentListRead:
    result = service.remove_item_from_project(project_id, equipment_id)
    return project_equipment_list_read(result.project_id, result.items)


@router.get("/api/projects/{project_id}/equipment-selections", response_model=ProjectEquipmentSelectionsRead)
def get_project_equipment_selections(
    project_id: int,
    _: AuthenticatedUser = Depends(require_project_access),
    service: EquipmentUseCases = Depends(get_equipment_use_cases),
) -> ProjectEquipmentSelectionsRead:
    return project_equipment_selections_read(service.get_project_selections(project_id))


@router.patch("/api/projects/{project_id}/equipment-selections", response_model=ProjectEquipmentSelectionsRead)
def update_project_equipment_selections(
    project_id: int,
    payload: ProjectEquipmentSelectionsUpdate,
    _: AuthenticatedUser = Depends(require_project_access),
    service: EquipmentUseCases = Depends(get_equipment_use_cases),
) -> ProjectEquipmentSelectionsRead:
    return project_equipment_selections_read(service.update_project_selections(project_id, payload))
