"""PDF routes."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from backend.dependencies import get_documents_use_cases
from backend.mappers import (
    additional_info_read,
    equipment_specification_read,
    general_data_read,
    general_instructions_read,
    power_consumption_calculation_read,
)
from backend.modules.documents.application.use_cases import DocumentsUseCases
from backend.schemas import (
    AdditionalInfoRead,
    AdditionalInfoUpdate,
    EquipmentSpecificationRead,
    EquipmentSpecificationUpdate,
    GeneralDataRead,
    GeneralDataUpdate,
    GeneralInstructionsRead,
    GeneralInstructionsUpdate,
    PowerConsumptionCalculationRead,
    PowerConsumptionCalculationUpdate,
)


router = APIRouter(tags=["pdf"])


@router.post("/api/projects/{project_id}/generate-pdf")
def generate_pdf(
    project_id: int,
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> FileResponse:
    pdf_path = service.generate_project_pdf(project_id)
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        filename=os.path.basename(pdf_path),
    )


@router.get("/api/projects/{project_id}/equipment-specification", response_model=EquipmentSpecificationRead)
def get_project_equipment_specification(
    project_id: int,
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> EquipmentSpecificationRead:
    return equipment_specification_read(service.get_project_equipment_specification(project_id))


@router.get("/api/projects/{project_id}/general-data", response_model=GeneralDataRead)
def get_project_general_data(
    project_id: int,
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> GeneralDataRead:
    return general_data_read(service.get_project_general_data(project_id))


@router.patch("/api/projects/{project_id}/general-data", response_model=GeneralDataRead)
def update_project_general_data(
    project_id: int,
    payload: GeneralDataUpdate,
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> GeneralDataRead:
    return general_data_read(service.update_project_general_data(project_id, payload))


@router.get("/api/projects/{project_id}/general-instructions", response_model=GeneralInstructionsRead)
def get_project_general_instructions(
    project_id: int,
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> GeneralInstructionsRead:
    return general_instructions_read(service.get_project_general_instructions(project_id))


@router.patch("/api/projects/{project_id}/general-instructions", response_model=GeneralInstructionsRead)
def update_project_general_instructions(
    project_id: int,
    payload: GeneralInstructionsUpdate,
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> GeneralInstructionsRead:
    return general_instructions_read(service.update_project_general_instructions(project_id, payload))


@router.patch("/api/projects/{project_id}/equipment-specification", response_model=EquipmentSpecificationRead)
def update_project_equipment_specification(
    project_id: int,
    payload: EquipmentSpecificationUpdate,
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> EquipmentSpecificationRead:
    return equipment_specification_read(service.update_project_equipment_specification(project_id, payload))


@router.get("/api/projects/{project_id}/power-consumption-calculation", response_model=PowerConsumptionCalculationRead)
def get_project_power_consumption_calculation(
    project_id: int,
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> PowerConsumptionCalculationRead:
    return power_consumption_calculation_read(service.get_project_power_consumption_calculation(project_id))


@router.patch("/api/projects/{project_id}/power-consumption-calculation", response_model=PowerConsumptionCalculationRead)
def update_project_power_consumption_calculation(
    project_id: int,
    payload: PowerConsumptionCalculationUpdate,
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> PowerConsumptionCalculationRead:
    return power_consumption_calculation_read(
        service.update_project_power_consumption_calculation(project_id, payload)
    )


@router.get("/api/projects/{project_id}/additional-info", response_model=AdditionalInfoRead)
def get_project_additional_info(
    project_id: int,
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> AdditionalInfoRead:
    return additional_info_read(service.get_project_additional_info(project_id))


@router.patch("/api/projects/{project_id}/additional-info", response_model=AdditionalInfoRead)
def update_project_additional_info(
    project_id: int,
    payload: AdditionalInfoUpdate,
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> AdditionalInfoRead:
    return additional_info_read(service.update_project_additional_info(project_id, payload))
