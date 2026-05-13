"""Repository contracts for the equipment catalog module."""

from __future__ import annotations

from typing import Protocol

from fastapi import UploadFile

from backend.modules.equipment.domain.entities import EquipmentItemRecord, ProjectEquipmentListRecord, ProjectEquipmentSelectionsRecord
from backend.schemas import EquipmentItemCreate, EquipmentItemUpdate, ProjectEquipmentAttach, ProjectEquipmentSelectionsUpdate


class EquipmentRepository(Protocol):
    """Persistence contract for equipment catalog and project selections."""

    def list_items(self) -> list[EquipmentItemRecord]:
        """List all equipment items."""

    def get_item(self, equipment_id: int) -> EquipmentItemRecord:
        """Return one equipment item."""

    def create_item(self, payload: EquipmentItemCreate) -> EquipmentItemRecord:
        """Create an equipment item."""

    def update_item(self, equipment_id: int, payload: EquipmentItemUpdate) -> EquipmentItemRecord:
        """Update an equipment item."""

    def delete_item(self, equipment_id: int) -> None:
        """Delete an equipment item."""

    def set_item_image(self, equipment_id: int, upload_file: UploadFile) -> EquipmentItemRecord:
        """Persist and attach an uploaded image to an equipment item."""

    def set_item_connection_diagram(self, equipment_id: int, upload_file: UploadFile) -> EquipmentItemRecord:
        """Persist and attach an uploaded connection diagram image to an equipment item."""

    def set_item_label_pdf(self, equipment_id: int, upload_file: UploadFile) -> EquipmentItemRecord:
        """Persist and attach an uploaded label PDF to an equipment item."""

    def set_item_manual_pdf(self, equipment_id: int, upload_file: UploadFile) -> EquipmentItemRecord:
        """Persist and attach an uploaded manual PDF to an equipment item."""

    def get_project_equipment(self, project_id: int) -> ProjectEquipmentListRecord:
        """Read project-linked equipment."""

    def attach_item_to_project(self, project_id: int, payload: ProjectEquipmentAttach) -> ProjectEquipmentListRecord:
        """Attach existing catalog equipment to a project."""

    def create_and_attach_item(self, project_id: int, payload: EquipmentItemCreate) -> ProjectEquipmentListRecord:
        """Create catalog equipment and attach it to a project."""

    def remove_item_from_project(self, project_id: int, equipment_id: int) -> ProjectEquipmentListRecord:
        """Detach equipment from a project."""

    def get_project_selections(self, project_id: int) -> ProjectEquipmentSelectionsRecord:
        """Read project equipment selections."""

    def update_project_selections(
        self,
        project_id: int,
        payload: ProjectEquipmentSelectionsUpdate,
    ) -> ProjectEquipmentSelectionsRecord:
        """Replace project equipment selections."""
