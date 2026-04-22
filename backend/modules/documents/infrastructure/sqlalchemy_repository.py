"""SQLAlchemy repository for document generation and specification editing."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from AdditionalInfoPage import AdditionalInfoPage
from ConventionalSymbolsPage import ConventionalSymbolsPage
from GeneralInstructionsPage import GeneralInstructionsPage
from PowerConsumptionCalculationPage import PowerConsumptionCalculationPage
from backend.errors import AppError
from backend.modules.documents.additional_info import build_project_additional_info
from backend.modules.documents.conventional_symbols import build_project_conventional_symbols
from backend.modules.documents.general_data import (
    apply_general_data_overrides,
    build_project_general_data,
    extract_general_data_overrides,
)
from backend.modules.documents.general_instructions import (
    apply_general_instructions_overrides,
    build_project_general_instructions,
    extract_general_instructions_overrides,
)
from backend.modules.documents.power_consumption import (
    apply_power_consumption_overrides,
    build_project_power_consumption_calculation,
    extract_power_consumption_overrides,
)
from backend.modules.documents.specification import (
    apply_equipment_specification_overrides,
    build_project_equipment_specification,
    extract_equipment_specification_overrides,
)
from backend.modules.shared.infrastructure.persistence.models import FloorPlan as FloorPlanModel
from backend.modules.shared.infrastructure.persistence.models import Project as ProjectModel
from backend.schemas import (
    AdditionalInfoUpdate,
    EquipmentSpecificationUpdate,
    GeneralDataUpdate,
    GeneralInstructionsUpdate,
    PowerConsumptionCalculationUpdate,
)


class SqlAlchemyDocumentReadRepository:
    """Repository for project documents and editable specification state."""

    def __init__(self, session: Session):
        self.session = session

    def get_project(self, project_id: int) -> ProjectModel:
        project = self.session.query(ProjectModel).filter(ProjectModel.id == project_id).first()
        if project is None:
            raise AppError(404, "project_not_found", "Project not found")
        return project

    def list_project_floor_plans(self, project_id: int) -> list[FloorPlanModel]:
        return (
            self.session.query(FloorPlanModel)
            .filter(FloorPlanModel.project_id == project_id)
            .order_by(FloorPlanModel.floor_number.asc(), FloorPlanModel.id.asc())
            .all()
        )

    def get_project_equipment_specification(self, project_id: int) -> dict:
        project = self.get_project(project_id)
        floor_plans = self.list_project_floor_plans(project_id)
        base_specification = build_project_equipment_specification(project, floor_plans)
        return apply_equipment_specification_overrides(
            base_specification,
            getattr(project, "equipment_specification_overrides", None),
        )

    def get_project_power_consumption_calculation(self, project_id: int) -> dict:
        project = self.get_project(project_id)
        floor_plans = self.list_project_floor_plans(project_id)
        base_calculation = build_project_power_consumption_calculation(project, floor_plans)
        return apply_power_consumption_overrides(
            base_calculation,
            getattr(project, "power_consumption_overrides", None),
        )

    def _build_general_data_base(self, project: ProjectModel, floor_plans: list[FloorPlanModel]) -> dict:
        general_instructions = self.get_project_general_instructions(project.id)
        conventional_symbols = self.get_project_conventional_symbols(project.id)
        power_consumption = self.get_project_power_consumption_calculation(project.id)
        additional_info = self.get_project_additional_info(project.id)
        general_instructions_sheet_count = max(1, len(GeneralInstructionsPage.paginate(general_instructions)))
        conventional_symbols_sheet_count = max(1, len(ConventionalSymbolsPage.paginate(conventional_symbols)))
        power_consumption_sheet_count = max(
            1,
            len(PowerConsumptionCalculationPage.paginate(power_consumption)),
        )
        additional_info_sheet_count = (
            len(AdditionalInfoPage.paginate(additional_info))
            if additional_info and not bool(additional_info.get("is_empty"))
            else 0
        )
        return build_project_general_data(
            project,
            floor_plans,
            general_instructions_sheet_count=general_instructions_sheet_count,
            conventional_symbols_sheet_count=conventional_symbols_sheet_count,
            equipment_specification_included=True,
            power_consumption_sheet_count=power_consumption_sheet_count,
            additional_info_sheet_count=additional_info_sheet_count,
        )

    def get_project_general_data(self, project_id: int) -> dict:
        project = self.get_project(project_id)
        floor_plans = self.list_project_floor_plans(project_id)
        base_payload = self._build_general_data_base(project, floor_plans)
        return apply_general_data_overrides(
            base_payload,
            getattr(project, "general_data_overrides", None),
        )

    def get_project_general_instructions(self, project_id: int) -> dict:
        project = self.get_project(project_id)
        floor_plans = self.list_project_floor_plans(project_id)
        base_payload = build_project_general_instructions(project, floor_plans)
        return apply_general_instructions_overrides(
            base_payload,
            getattr(project, "general_instructions_overrides", None),
        )

    def get_project_conventional_symbols(self, project_id: int) -> dict:
        project = self.get_project(project_id)
        floor_plans = self.list_project_floor_plans(project_id)
        return build_project_conventional_symbols(project, floor_plans)

    def get_project_additional_info(self, project_id: int) -> dict:
        project = self.get_project(project_id)
        return build_project_additional_info(project)

    def update_project_equipment_specification(
        self,
        project_id: int,
        payload: EquipmentSpecificationUpdate,
    ) -> dict:
        project = self.get_project(project_id)
        floor_plans = self.list_project_floor_plans(project_id)
        base_specification = build_project_equipment_specification(project, floor_plans)
        overrides = extract_equipment_specification_overrides(
            base_specification,
            payload.model_dump(),
        )
        project.equipment_specification_overrides = overrides or None
        project.updated_at = datetime.now(timezone.utc)
        self.session.flush()
        return apply_equipment_specification_overrides(base_specification, project.equipment_specification_overrides)

    def update_project_general_data(
        self,
        project_id: int,
        payload: GeneralDataUpdate,
    ) -> dict:
        project = self.get_project(project_id)
        floor_plans = self.list_project_floor_plans(project_id)
        base_payload = self._build_general_data_base(project, floor_plans)
        overrides = extract_general_data_overrides(
            base_payload,
            payload.model_dump(),
        )
        project.general_data_overrides = overrides or None
        project.updated_at = datetime.now(timezone.utc)
        self.session.flush()
        return apply_general_data_overrides(base_payload, project.general_data_overrides)

    def update_project_general_instructions(
        self,
        project_id: int,
        payload: GeneralInstructionsUpdate,
    ) -> dict:
        project = self.get_project(project_id)
        floor_plans = self.list_project_floor_plans(project_id)
        base_payload = build_project_general_instructions(project, floor_plans)
        overrides = extract_general_instructions_overrides(
            base_payload,
            payload.model_dump(),
        )
        project.general_instructions_overrides = overrides or None
        project.updated_at = datetime.now(timezone.utc)
        self.session.flush()
        return apply_general_instructions_overrides(base_payload, project.general_instructions_overrides)

    def update_project_power_consumption_calculation(
        self,
        project_id: int,
        payload: PowerConsumptionCalculationUpdate,
    ) -> dict:
        project = self.get_project(project_id)
        floor_plans = self.list_project_floor_plans(project_id)
        base_calculation = build_project_power_consumption_calculation(project, floor_plans)
        overrides = extract_power_consumption_overrides(
            base_calculation,
            payload.model_dump(),
        )
        project.power_consumption_overrides = overrides or None
        project.updated_at = datetime.now(timezone.utc)
        self.session.flush()
        return apply_power_consumption_overrides(base_calculation, project.power_consumption_overrides)

    def update_project_additional_info(
        self,
        project_id: int,
        payload: AdditionalInfoUpdate,
    ) -> dict:
        project = self.get_project(project_id)
        project.additional_info_text = str(payload.text or "")
        project.updated_at = datetime.now(timezone.utc)
        self.session.flush()
        return build_project_additional_info(project)
