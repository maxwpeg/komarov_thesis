"""Equipment catalog application use cases."""

from __future__ import annotations

from fastapi import UploadFile

from backend.modules.equipment.domain.entities import EquipmentItemRecord, ProjectEquipmentListRecord, ProjectEquipmentSelectionsRecord
from backend.modules.equipment.ports.repositories import EquipmentRepository
from backend.modules.shared.application.unit_of_work import UnitOfWork
from backend.schemas import EquipmentItemCreate, EquipmentItemUpdate, ProjectEquipmentAttach, ProjectEquipmentSelectionsUpdate


class EquipmentUseCases:
    """Application facade for equipment catalog and project selections."""

    def __init__(self, repository: EquipmentRepository, uow: UnitOfWork):
        self.repository = repository
        self.uow = uow

    def list_items(self) -> list[EquipmentItemRecord]:
        return self.repository.list_items()

    def get_item(self, equipment_id: int) -> EquipmentItemRecord:
        return self.repository.get_item(equipment_id)

    def create_item(self, payload: EquipmentItemCreate) -> EquipmentItemRecord:
        return self._write(lambda: self.repository.create_item(payload))

    def update_item(self, equipment_id: int, payload: EquipmentItemUpdate) -> EquipmentItemRecord:
        return self._write(lambda: self.repository.update_item(equipment_id, payload))

    def delete_item(self, equipment_id: int) -> None:
        self._write(lambda: self.repository.delete_item(equipment_id))

    def set_item_image(self, equipment_id: int, upload_file: UploadFile) -> EquipmentItemRecord:
        return self._write(lambda: self.repository.set_item_image(equipment_id, upload_file))

    def set_item_connection_diagram(self, equipment_id: int, upload_file: UploadFile) -> EquipmentItemRecord:
        return self._write(lambda: self.repository.set_item_connection_diagram(equipment_id, upload_file))

    def set_item_label_pdf(self, equipment_id: int, upload_file: UploadFile) -> EquipmentItemRecord:
        return self._write(lambda: self.repository.set_item_label_pdf(equipment_id, upload_file))

    def set_item_manual_pdf(self, equipment_id: int, upload_file: UploadFile) -> EquipmentItemRecord:
        return self._write(lambda: self.repository.set_item_manual_pdf(equipment_id, upload_file))

    def get_project_equipment(self, project_id: int) -> ProjectEquipmentListRecord:
        return self.repository.get_project_equipment(project_id)

    def attach_item_to_project(self, project_id: int, payload: ProjectEquipmentAttach) -> ProjectEquipmentListRecord:
        return self._write(lambda: self.repository.attach_item_to_project(project_id, payload))

    def create_and_attach_item(self, project_id: int, payload: EquipmentItemCreate) -> ProjectEquipmentListRecord:
        return self._write(lambda: self.repository.create_and_attach_item(project_id, payload))

    def remove_item_from_project(self, project_id: int, equipment_id: int) -> ProjectEquipmentListRecord:
        return self._write(lambda: self.repository.remove_item_from_project(project_id, equipment_id))

    def get_project_selections(self, project_id: int) -> ProjectEquipmentSelectionsRecord:
        return self.repository.get_project_selections(project_id)

    def update_project_selections(
        self,
        project_id: int,
        payload: ProjectEquipmentSelectionsUpdate,
    ) -> ProjectEquipmentSelectionsRecord:
        return self._write(lambda: self.repository.update_project_selections(project_id, payload))

    def _write(self, operation):
        try:
            result = operation()
            self.uow.commit()
            return result
        except Exception:
            self.uow.rollback()
            raise
