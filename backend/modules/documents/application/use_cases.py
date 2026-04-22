"""Explicit application use cases for documents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.config import settings
from backend.errors import AppError
from backend.modules.documents.infrastructure.pdf_adapter import PdfGeneratorAdapter
from backend.modules.documents.infrastructure.sqlalchemy_repository import SqlAlchemyDocumentReadRepository
from backend.modules.shared.application.unit_of_work import UnitOfWork
from backend.modules.shared.infrastructure.runtime import NoOpEventPublisher
from backend.schemas import (
    AdditionalInfoUpdate,
    EquipmentSpecificationUpdate,
    GeneralDataUpdate,
    GeneralInstructionsUpdate,
    PowerConsumptionCalculationUpdate,
)


@dataclass(slots=True)
class DocumentsUseCases:
    """Document generation use cases."""

    repository: SqlAlchemyDocumentReadRepository
    uow: UnitOfWork
    pdf_port: PdfGeneratorAdapter
    events: Any | None = None

    def __post_init__(self) -> None:
        if self.events is None:
            self.events = NoOpEventPublisher()

    def generate_project_pdf(self, project_id: int) -> str:
        project = self.repository.get_project(project_id)
        floor_plans = self.repository.list_project_floor_plans(project_id)
        if not floor_plans:
            raise AppError(400, "floor_plans_missing", "No floor plans found for this project")
        general_data = self.repository.get_project_general_data(project_id)
        general_instructions = self.repository.get_project_general_instructions(project_id)
        conventional_symbols = self.repository.get_project_conventional_symbols(project_id)
        specification = self.repository.get_project_equipment_specification(project_id)
        power_consumption_calculation = self.repository.get_project_power_consumption_calculation(project_id)
        additional_info = self.repository.get_project_additional_info(project_id)
        pdf_path = self.pdf_port.generate(
            project_data=project.to_dict(),
            floor_plans_data=[floor_plan.to_dict(include_elements=True) for floor_plan in floor_plans],
            general_data=general_data,
            general_instructions=general_instructions,
            conventional_symbols=conventional_symbols,
            equipment_specification=specification,
            power_consumption_calculation=power_consumption_calculation,
            additional_info=additional_info,
            output_dir=str(settings.outputs_dir),
        )
        self.events.publish(
            "project_pdf_generated",
            {"category": "documents", "use_case": "GenerateProjectPdf", "project_id": project_id},
        )
        return pdf_path

    def get_project_equipment_specification(self, project_id: int) -> dict[str, Any]:
        return self.repository.get_project_equipment_specification(project_id)

    def get_project_general_data(self, project_id: int) -> dict[str, Any]:
        return self.repository.get_project_general_data(project_id)

    def get_project_general_instructions(self, project_id: int) -> dict[str, Any]:
        return self.repository.get_project_general_instructions(project_id)

    def get_project_power_consumption_calculation(self, project_id: int) -> dict[str, Any]:
        return self.repository.get_project_power_consumption_calculation(project_id)

    def get_project_additional_info(self, project_id: int) -> dict[str, Any]:
        return self.repository.get_project_additional_info(project_id)

    def update_project_equipment_specification(
        self,
        project_id: int,
        payload: EquipmentSpecificationUpdate,
    ) -> dict[str, Any]:
        return self._write(lambda: self.repository.update_project_equipment_specification(project_id, payload))

    def update_project_general_data(
        self,
        project_id: int,
        payload: GeneralDataUpdate,
    ) -> dict[str, Any]:
        return self._write(lambda: self.repository.update_project_general_data(project_id, payload))

    def update_project_general_instructions(
        self,
        project_id: int,
        payload: GeneralInstructionsUpdate,
    ) -> dict[str, Any]:
        return self._write(lambda: self.repository.update_project_general_instructions(project_id, payload))

    def update_project_power_consumption_calculation(
        self,
        project_id: int,
        payload: PowerConsumptionCalculationUpdate,
    ) -> dict[str, Any]:
        return self._write(lambda: self.repository.update_project_power_consumption_calculation(project_id, payload))

    def update_project_additional_info(
        self,
        project_id: int,
        payload: AdditionalInfoUpdate,
    ) -> dict[str, Any]:
        return self._write(lambda: self.repository.update_project_additional_info(project_id, payload))

    def _write(self, operation):
        try:
            result = operation()
            self.uow.commit()
            return result
        except Exception:
            self.uow.rollback()
            raise
