"""PDF routes."""

from __future__ import annotations

import os

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from AdditionalInfoPage import AdditionalInfoPage
from ConventionalSymbolsPage import ConventionalSymbolsPage
from GeneralInstructionsPage import GeneralInstructionsPage
from PowerConsumptionCalculationPage import PowerConsumptionCalculationPage
from backend.assets import build_asset_url
from backend.auth import AuthenticatedUser, require_project_access
from backend.background_jobs import TASK_PROJECT_PDF_GENERATE, dedupe_key_for_task
from backend.database import get_db
from backend.dependencies import get_documents_use_cases
from backend.errors import AppError
from backend.mappers import (
    additional_info_read,
    background_task_read,
    equipment_specification_read,
    general_data_read,
    general_instructions_read,
    power_consumption_calculation_read,
)
from backend.models import BackgroundTask, Project
from backend.modules.documents.application.use_cases import DocumentsUseCases
from backend.schemas import (
    AdditionalInfoRead,
    AdditionalInfoUpdate,
    BackgroundTaskRead,
    EquipmentSpecificationRead,
    EquipmentSpecificationUpdate,
    GeneralDataRead,
    GeneralDataUpdate,
    GeneralInstructionsRead,
    GeneralInstructionsUpdate,
    ProjectPdfPreviewRead,
    PowerConsumptionCalculationRead,
    PowerConsumptionCalculationUpdate,
)
from backend.services.background_task_service import BackgroundTaskService


router = APIRouter(tags=["pdf"])


GENERAL_DATA_STAGE_KEY = "general_data"
GENERAL_INSTRUCTIONS_STAGE_KEY = "general_instructions"
POWER_CONSUMPTION_STAGE_KEY = "power_consumption_calculation"
EQUIPMENT_SPECIFICATION_STAGE_KEY = "equipment_specification"
ADDITIONAL_INFO_STAGE_KEY = "additional_info"
ZKSPC_STAGE_KEY = "zkspc"
SPS_STAGE_KEY = "sps"
SOUE_STAGE_KEY = "soue"


def _paginate_general_instructions(payload: dict | None) -> list[dict]:
    return GeneralInstructionsPage.paginate(payload or {}) if payload else []


def _paginate_conventional_symbols(payload: dict | None) -> list[dict]:
    return ConventionalSymbolsPage.paginate(payload or {}) if payload else []


def _paginate_power_consumption(payload: dict | None) -> list[dict]:
    return PowerConsumptionCalculationPage.paginate(payload or {}) if payload else []


def _paginate_additional_info(payload: dict | None) -> list[dict]:
    if not payload or bool(payload.get("is_empty")):
        return []
    return AdditionalInfoPage.paginate(payload)


def _resolve_preview_location(
    service: DocumentsUseCases,
    project_id: int,
    *,
    stage_key: str | None,
    floor_plan_id: int | None,
) -> tuple[int | None, str | None]:
    normalized_stage = str(stage_key or "").strip() or None
    floor_plans = service.repository.list_project_floor_plans(project_id)

    if normalized_stage is None and floor_plan_id is None:
        return None, None

    general_instructions_segments = _paginate_general_instructions(
        service.get_project_general_instructions(project_id)
    )
    conventional_symbols_segments = _paginate_conventional_symbols(
        service.repository.get_project_conventional_symbols(project_id)
    )
    power_consumption_segments = _paginate_power_consumption(
        service.get_project_power_consumption_calculation(project_id)
    )
    additional_info_segments = _paginate_additional_info(
        service.get_project_additional_info(project_id)
    )

    general_instructions_count = len(general_instructions_segments) if general_instructions_segments else 2
    conventional_symbols_count = len(conventional_symbols_segments) if conventional_symbols_segments else 1
    power_consumption_count = len(power_consumption_segments) if power_consumption_segments else 1
    additional_info_count = len(additional_info_segments)

    general_data_page = 3
    general_instructions_page = general_data_page + 1
    conventional_symbols_page = general_instructions_page + general_instructions_count
    structural_scheme_page = conventional_symbols_page + conventional_symbols_count
    floor_sections_page = structural_scheme_page + 1
    electrical_schemes_page = floor_sections_page + (len(floor_plans) * 3)
    equipment_specification_page = electrical_schemes_page + 1
    power_consumption_page = equipment_specification_page + 1
    additional_info_page = (
        power_consumption_page + power_consumption_count
        if additional_info_count > 0
        else None
    )

    page_map = {
        GENERAL_DATA_STAGE_KEY: (general_data_page, "Общие данные"),
        GENERAL_INSTRUCTIONS_STAGE_KEY: (general_instructions_page, "Общие указания"),
        EQUIPMENT_SPECIFICATION_STAGE_KEY: (equipment_specification_page, "Спецификация"),
        POWER_CONSUMPTION_STAGE_KEY: (power_consumption_page, "Расчёт токопотребления"),
        ADDITIONAL_INFO_STAGE_KEY: (
            additional_info_page,
            "Дополнительные сведения",
        ),
    }

    if floor_plan_id is not None:
        floor_plan_index = next(
            (index for index, floor_plan in enumerate(floor_plans) if floor_plan.id == floor_plan_id),
            None,
        )
        if floor_plan_index is None:
            raise AppError(404, "floor_plan_not_found", "Floor plan not found")
        floor_plan = floor_plans[floor_plan_index]
        floor_plan_title = floor_plan.name or f"Этаж {floor_plan.floor_number}"
        sheet_offset = {
            None: 0,
            ZKSPC_STAGE_KEY: 0,
            SPS_STAGE_KEY: 1,
            SOUE_STAGE_KEY: 2,
        }.get(normalized_stage)
        if sheet_offset is None:
            raise AppError(400, "unsupported_preview_stage", "Unsupported PDF preview stage")
        page_number = floor_sections_page + (floor_plan_index * 3) + sheet_offset
        page_title = {
            ZKSPC_STAGE_KEY: f"{floor_plan_title}: ЗКСПС",
            SPS_STAGE_KEY: f"{floor_plan_title}: СПС",
            SOUE_STAGE_KEY: f"{floor_plan_title}: СОУЭ",
            None: floor_plan_title,
        }[normalized_stage]
        return page_number, page_title

    return page_map.get(normalized_stage, (None, None))


@router.post(
    "/api/projects/{project_id}/generate-pdf",
    response_model=BackgroundTaskRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def generate_pdf(
    project_id: int,
    current_user: AuthenticatedUser = Depends(require_project_access),
    db: Session = Depends(get_db),
) -> BackgroundTaskRead:
    task = BackgroundTaskService(db).enqueue(
        task_type=TASK_PROJECT_PDF_GENERATE,
        requested_by_user_id=current_user.id,
        project_id=project_id,
        payload={"project_id": project_id},
        dedupe_key=dedupe_key_for_task(TASK_PROJECT_PDF_GENERATE, project_id=project_id),
        resource_path=f"/projects/{project_id}/preview",
    )
    return background_task_read(task)


@router.get("/api/projects/{project_id}/pdf-preview", response_model=ProjectPdfPreviewRead)
def get_project_pdf_preview(
    project_id: int,
    stage_key: str | None = None,
    floor_plan_id: int | None = None,
    _: AuthenticatedUser = Depends(require_project_access),
    db: Session = Depends(get_db),
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> ProjectPdfPreviewRead:
    project = db.query(Project).filter(Project.id == project_id).first()
    current_task = (
        db.query(BackgroundTask)
        .filter(
            BackgroundTask.project_id == project_id,
            BackgroundTask.task_type == TASK_PROJECT_PDF_GENERATE,
            BackgroundTask.status.in_(("queued", "running")),
        )
        .order_by(BackgroundTask.created_at.desc(), BackgroundTask.id.desc())
        .first()
    )
    page_number, page_title = _resolve_preview_location(
        service,
        project_id,
        stage_key=stage_key,
        floor_plan_id=floor_plan_id,
    )
    return ProjectPdfPreviewRead(
        project_id=project_id,
        pdf_path=project.latest_pdf_path if project is not None else None,
        pdf_url=build_asset_url(project.latest_pdf_path if project is not None else None),
        generated_at=project.latest_pdf_generated_at if project is not None else None,
        stage_key=stage_key,
        floor_plan_id=floor_plan_id,
        page_number=page_number,
        page_title=page_title,
        current_task=background_task_read(current_task) if current_task is not None else None,
    )


@router.get("/api/projects/{project_id}/equipment-specification", response_model=EquipmentSpecificationRead)
def get_project_equipment_specification(
    project_id: int,
    _: AuthenticatedUser = Depends(require_project_access),
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> EquipmentSpecificationRead:
    return equipment_specification_read(service.get_project_equipment_specification(project_id))


@router.get("/api/projects/{project_id}/general-data", response_model=GeneralDataRead)
def get_project_general_data(
    project_id: int,
    _: AuthenticatedUser = Depends(require_project_access),
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> GeneralDataRead:
    return general_data_read(service.get_project_general_data(project_id))


@router.patch("/api/projects/{project_id}/general-data", response_model=GeneralDataRead)
def update_project_general_data(
    project_id: int,
    payload: GeneralDataUpdate,
    _: AuthenticatedUser = Depends(require_project_access),
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> GeneralDataRead:
    return general_data_read(service.update_project_general_data(project_id, payload))


@router.get("/api/projects/{project_id}/general-instructions", response_model=GeneralInstructionsRead)
def get_project_general_instructions(
    project_id: int,
    _: AuthenticatedUser = Depends(require_project_access),
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> GeneralInstructionsRead:
    return general_instructions_read(service.get_project_general_instructions(project_id))


@router.patch("/api/projects/{project_id}/general-instructions", response_model=GeneralInstructionsRead)
def update_project_general_instructions(
    project_id: int,
    payload: GeneralInstructionsUpdate,
    _: AuthenticatedUser = Depends(require_project_access),
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> GeneralInstructionsRead:
    return general_instructions_read(service.update_project_general_instructions(project_id, payload))


@router.patch("/api/projects/{project_id}/equipment-specification", response_model=EquipmentSpecificationRead)
def update_project_equipment_specification(
    project_id: int,
    payload: EquipmentSpecificationUpdate,
    _: AuthenticatedUser = Depends(require_project_access),
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> EquipmentSpecificationRead:
    return equipment_specification_read(service.update_project_equipment_specification(project_id, payload))


@router.get("/api/projects/{project_id}/power-consumption-calculation", response_model=PowerConsumptionCalculationRead)
def get_project_power_consumption_calculation(
    project_id: int,
    _: AuthenticatedUser = Depends(require_project_access),
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> PowerConsumptionCalculationRead:
    return power_consumption_calculation_read(service.get_project_power_consumption_calculation(project_id))


@router.patch("/api/projects/{project_id}/power-consumption-calculation", response_model=PowerConsumptionCalculationRead)
def update_project_power_consumption_calculation(
    project_id: int,
    payload: PowerConsumptionCalculationUpdate,
    _: AuthenticatedUser = Depends(require_project_access),
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> PowerConsumptionCalculationRead:
    return power_consumption_calculation_read(
        service.update_project_power_consumption_calculation(project_id, payload)
    )


@router.get("/api/projects/{project_id}/additional-info", response_model=AdditionalInfoRead)
def get_project_additional_info(
    project_id: int,
    _: AuthenticatedUser = Depends(require_project_access),
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> AdditionalInfoRead:
    return additional_info_read(service.get_project_additional_info(project_id))


@router.patch("/api/projects/{project_id}/additional-info", response_model=AdditionalInfoRead)
def update_project_additional_info(
    project_id: int,
    payload: AdditionalInfoUpdate,
    _: AuthenticatedUser = Depends(require_project_access),
    service: DocumentsUseCases = Depends(get_documents_use_cases),
) -> AdditionalInfoRead:
    return additional_info_read(service.update_project_additional_info(project_id, payload))
