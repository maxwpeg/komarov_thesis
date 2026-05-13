"""SQLAlchemy-backed repository for the equipment catalog."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import UploadFile
from sqlalchemy import or_
from sqlalchemy.orm import Session

from backend.errors import AppError
from backend.modules.equipment.domain.constants import (
    EQUIPMENT_CATEGORIES,
    FIRE_ALARM_DEVICE_CATEGORY_MAP,
    PROJECT_EQUIPMENT_ROLE_CATEGORY_MAP,
    PROJECT_EQUIPMENT_ROLES,
    SIGNAL_INSTRUMENT_CATEGORY_MAP,
    SMOKE_ADDRESSING_VALUES,
    SOUE_DEVICE_CATEGORY_MAP,
)
from backend.modules.equipment.domain.entities import EquipmentItemRecord, ProjectEquipmentListRecord, ProjectEquipmentSelectionsRecord
from backend.modules.equipment.domain.specs import EquipmentSpecsValidationError, coerce_current_specs, normalize_specs
from backend.modules.equipment.ports.repositories import EquipmentRepository
from backend.modules.shared.infrastructure.persistence.models import (
    EquipmentCompatibilityLink,
    EquipmentItem,
    FireAlarm,
    FloorPlan,
    Project,
    ProjectEquipmentLink,
    ProjectEquipmentSelection,
    SignalInstrument,
    SoueDevice,
)
from backend.modules.shared.infrastructure.storage import StorageService
from backend.storage_metadata import record_managed_file, remove_managed_file
from backend.schemas import EquipmentItemCreate, EquipmentItemUpdate, ProjectEquipmentAttach, ProjectEquipmentSelectionsUpdate


class SqlAlchemyEquipmentRepository(EquipmentRepository):
    """Repository implementation for equipment catalog and project selections."""

    def __init__(self, session: Session, storage: StorageService):
        self.session = session
        self.storage = storage

    def list_items(self) -> list[EquipmentItemRecord]:
        items = (
            self.session.query(EquipmentItem)
            .order_by(EquipmentItem.updated_at.desc(), EquipmentItem.id.desc())
            .all()
        )
        compatibility_map = self._get_compatibility_map([item.id for item in items])
        return [
            EquipmentItemRecord.from_model(item, compatible_equipment_ids=compatibility_map.get(item.id, []))
            for item in items
        ]

    def get_item(self, equipment_id: int) -> EquipmentItemRecord:
        item = self._get_item_model(equipment_id)
        compatibility_map = self._get_compatibility_map([equipment_id])
        return EquipmentItemRecord.from_model(
            item,
            compatible_equipment_ids=compatibility_map.get(equipment_id, []),
        )

    def create_item(self, payload: EquipmentItemCreate) -> EquipmentItemRecord:
        item = self._create_item_model(payload.model_dump())
        return self.get_item(item.id)

    def update_item(self, equipment_id: int, payload: EquipmentItemUpdate) -> EquipmentItemRecord:
        item = self._get_item_model(equipment_id)
        data = payload.model_dump(exclude_unset=True)
        previous_category = item.category
        target_category = self._validate_category(data.get("category", item.category))
        self._validate_category_assignments(item.id, target_category)
        self._validate_element_assignments(item.id, target_category)

        if "name" in data:
            item.name = self._normalize_required_text(data["name"], field_name="name")
        if "category" in data:
            item.category = target_category
        if "description" in data:
            item.description = self._normalize_text(data.get("description"))
        if "price" in data:
            item.price = self._normalize_price(data.get("price"))
        if "manufacturer" in data:
            item.manufacturer = self._normalize_text(data.get("manufacturer"))
        if "service_life_years" in data:
            item.service_life_years = self._normalize_optional_int(data.get("service_life_years"), field_name="service_life_years")
        if "notes" in data:
            item.notes = self._normalize_text(data.get("notes"))
        if "coverage_summary" in data:
            item.coverage_summary = self._normalize_text(data.get("coverage_summary"))
        if "standby_current_ma" in data:
            item.standby_current_ma = self._normalize_number(data.get("standby_current_ma"))
        if "alarm_current_ma" in data:
            item.alarm_current_ma = self._normalize_number(data.get("alarm_current_ma"))
        if "connection_diagram_path" in data:
            item.connection_diagram_path = self._normalize_text(data.get("connection_diagram_path"))
        if "label_pdf_path" in data:
            item.label_pdf_path = self._normalize_text(data.get("label_pdf_path"))
        if "manual_pdf_path" in data:
            item.manual_pdf_path = self._normalize_text(data.get("manual_pdf_path"))

        try:
            legacy_smoke_addressing = (
                self._validate_smoke_addressing(
                    target_category,
                    data.get("smoke_addressing"),
                    allow_implicit_clear=False,
                )
                if "smoke_addressing" in data
                else item.smoke_addressing
            )
            should_revalidate_specs = any(
                key in data
                for key in ("category", "specs", "smoke_addressing", "standby_current_ma", "alarm_current_ma")
            )
            if should_revalidate_specs:
                existing_specs = coerce_current_specs(
                    previous_category,
                    item.specs,
                    smoke_addressing=item.smoke_addressing,
                    standby_current_ma=item.standby_current_ma,
                    alarm_current_ma=item.alarm_current_ma,
                )
                merged_specs = {} if ("category" in data and "specs" not in data and previous_category != target_category) else dict(existing_specs)
                if "specs" in data:
                    if data.get("specs") not in (None, "") and not isinstance(data.get("specs"), dict):
                        raise AppError(400, "equipment_item_invalid_specs_payload", "Field specs must be an object")
                    merged_specs.update(data.get("specs") or {})
                if "smoke_addressing" in data:
                    if legacy_smoke_addressing is None:
                        merged_specs.pop("addressing_mode", None)
                    else:
                        merged_specs["addressing_mode"] = legacy_smoke_addressing
                if "standby_current_ma" in data:
                    if data.get("standby_current_ma") in (None, ""):
                        merged_specs.pop("standby_current_a", None)
                    else:
                        merged_specs["standby_current_a"] = float(data["standby_current_ma"]) / 1000.0
                if "alarm_current_ma" in data:
                    if data.get("alarm_current_ma") in (None, ""):
                        merged_specs.pop("alarm_current_a", None)
                    else:
                        merged_specs["alarm_current_a"] = float(data["alarm_current_ma"]) / 1000.0
                item.specs = normalize_specs(
                    target_category,
                    merged_specs,
                    smoke_addressing=legacy_smoke_addressing,
                    standby_current_ma=data.get("standby_current_ma", item.standby_current_ma),
                    alarm_current_ma=data.get("alarm_current_ma", item.alarm_current_ma),
                    require_complete=True,
                )
                item.smoke_addressing = item.specs.get("addressing_mode") if target_category == "smoke" else None
            elif previous_category != target_category and target_category != "smoke":
                item.smoke_addressing = None
        except EquipmentSpecsValidationError as exc:
            raise AppError(400, exc.code, exc.detail) from exc

        if "compatible_equipment_ids" in data:
            compatible_equipment_ids = self._normalize_compatible_ids(
                data.get("compatible_equipment_ids") or [],
                equipment_id=equipment_id,
            )
            self._replace_compatibility_links(equipment_id, compatible_equipment_ids)

        item.updated_at = self._now()
        self.session.flush()
        return self.get_item(equipment_id)

    def delete_item(self, equipment_id: int) -> None:
        item = self._get_item_model(equipment_id)
        selection_count = (
            self.session.query(ProjectEquipmentSelection)
            .filter(ProjectEquipmentSelection.equipment_id == equipment_id)
            .count()
        )
        link_count = (
            self.session.query(ProjectEquipmentLink)
            .filter(ProjectEquipmentLink.equipment_id == equipment_id)
            .count()
        )
        element_usage_count = self._count_equipment_usage_globally(equipment_id)
        if selection_count or link_count or element_usage_count:
            raise AppError(409, "equipment_item_in_use", "Equipment is assigned to at least one project")

        compatibility_count = (
            self.session.query(EquipmentCompatibilityLink)
            .filter(
                or_(
                    EquipmentCompatibilityLink.equipment_id == equipment_id,
                    EquipmentCompatibilityLink.compatible_equipment_id == equipment_id,
                )
            )
            .count()
        )
        if compatibility_count:
            raise AppError(409, "equipment_item_has_compatibility_links", "Remove compatibility links before deleting equipment")

        image_path = item.image_path
        connection_diagram_path = item.connection_diagram_path
        label_pdf_path = item.label_pdf_path
        manual_pdf_path = item.manual_pdf_path
        remove_managed_file(self.session, image_path)
        remove_managed_file(self.session, connection_diagram_path)
        remove_managed_file(self.session, label_pdf_path)
        remove_managed_file(self.session, manual_pdf_path)
        self.session.delete(item)
        self.session.flush()
        self.storage.delete_relative_path(image_path)
        self.storage.delete_relative_path(connection_diagram_path)
        self.storage.delete_relative_path(label_pdf_path)
        self.storage.delete_relative_path(manual_pdf_path)

    def set_item_image(self, equipment_id: int, upload_file: UploadFile) -> EquipmentItemRecord:
        item = self._get_item_model(equipment_id)
        saved_upload = self.storage.save_equipment_upload(upload_file, equipment_id)
        previous_image_path = item.image_path
        item.image_path = saved_upload.relative_path
        item.updated_at = self._now()
        self.session.flush()
        record_managed_file(self.session, saved_upload, equipment_id=equipment_id)
        if previous_image_path and previous_image_path != saved_upload.relative_path:
            remove_managed_file(self.session, previous_image_path)
            self.storage.delete_relative_path(previous_image_path)
        return self.get_item(equipment_id)

    def set_item_connection_diagram(self, equipment_id: int, upload_file: UploadFile) -> EquipmentItemRecord:
        item = self._get_item_model(equipment_id)
        saved_upload = self.storage.save_equipment_connection_diagram_upload(upload_file, equipment_id)
        previous_path = item.connection_diagram_path
        item.connection_diagram_path = saved_upload.relative_path
        item.updated_at = self._now()
        self.session.flush()
        record_managed_file(self.session, saved_upload, equipment_id=equipment_id)
        if previous_path and previous_path != saved_upload.relative_path:
            remove_managed_file(self.session, previous_path)
            self.storage.delete_relative_path(previous_path)
        return self.get_item(equipment_id)

    def set_item_label_pdf(self, equipment_id: int, upload_file: UploadFile) -> EquipmentItemRecord:
        item = self._get_item_model(equipment_id)
        saved_path = self.storage.save_equipment_document_upload(upload_file, equipment_id, "label")
        previous_path = item.label_pdf_path
        item.label_pdf_path = saved_path
        item.updated_at = self._now()
        self.session.flush()
        record_managed_file(
            self.session,
            saved_path,
            storage=self.storage,
            equipment_id=equipment_id,
            content_type=upload_file.content_type,
        )
        if previous_path and previous_path != saved_path:
            remove_managed_file(self.session, previous_path)
            self.storage.delete_relative_path(previous_path)
        return self.get_item(equipment_id)

    def set_item_manual_pdf(self, equipment_id: int, upload_file: UploadFile) -> EquipmentItemRecord:
        item = self._get_item_model(equipment_id)
        saved_path = self.storage.save_equipment_document_upload(upload_file, equipment_id, "manual")
        previous_path = item.manual_pdf_path
        item.manual_pdf_path = saved_path
        item.updated_at = self._now()
        self.session.flush()
        record_managed_file(
            self.session,
            saved_path,
            storage=self.storage,
            equipment_id=equipment_id,
            content_type=upload_file.content_type,
        )
        if previous_path and previous_path != saved_path:
            remove_managed_file(self.session, previous_path)
            self.storage.delete_relative_path(previous_path)
        return self.get_item(equipment_id)

    def get_project_equipment(self, project_id: int) -> ProjectEquipmentListRecord:
        self._get_project_model(project_id)
        return self._build_project_equipment_list(project_id)

    def attach_item_to_project(self, project_id: int, payload: ProjectEquipmentAttach) -> ProjectEquipmentListRecord:
        self._get_project_model(project_id)
        equipment = self._get_item_model(int(payload.equipment_id))
        self._ensure_project_equipment_link(project_id, equipment.id)
        self.session.flush()
        return self._build_project_equipment_list(project_id)

    def create_and_attach_item(self, project_id: int, payload: EquipmentItemCreate) -> ProjectEquipmentListRecord:
        self._get_project_model(project_id)
        item = self._create_item_model(payload.model_dump())
        self._ensure_project_equipment_link(project_id, item.id)
        self.session.flush()
        return self._build_project_equipment_list(project_id)

    def remove_item_from_project(self, project_id: int, equipment_id: int) -> ProjectEquipmentListRecord:
        self._get_project_model(project_id)
        link = (
            self.session.query(ProjectEquipmentLink)
            .filter(
                ProjectEquipmentLink.project_id == project_id,
                ProjectEquipmentLink.equipment_id == equipment_id,
            )
            .first()
        )
        if link is None:
            raise AppError(404, "project_equipment_not_found", "Equipment is not linked to the project")
        if self._count_project_item_usage(project_id, equipment_id):
            raise AppError(409, "project_equipment_in_use", "Equipment is used by floor plan elements in this project")
        (
            self.session.query(ProjectEquipmentSelection)
            .filter(
                ProjectEquipmentSelection.project_id == project_id,
                ProjectEquipmentSelection.equipment_id == equipment_id,
            )
            .delete(synchronize_session=False)
        )
        self.session.delete(link)
        self.session.flush()
        return self._build_project_equipment_list(project_id)

    def get_project_selections(self, project_id: int) -> ProjectEquipmentSelectionsRecord:
        self._get_project_model(project_id)
        selections = {role_key: None for role_key in PROJECT_EQUIPMENT_ROLES}
        rows = (
            self.session.query(ProjectEquipmentSelection)
            .filter(ProjectEquipmentSelection.project_id == project_id)
            .all()
        )
        for row in rows:
            selections[row.role_key] = row.equipment_id
        return ProjectEquipmentSelectionsRecord(project_id=project_id, selections=selections)

    def update_project_selections(
        self,
        project_id: int,
        payload: ProjectEquipmentSelectionsUpdate,
    ) -> ProjectEquipmentSelectionsRecord:
        self._get_project_model(project_id)
        selections = self._normalize_project_selections(payload.selections)

        (
            self.session.query(ProjectEquipmentSelection)
            .filter(ProjectEquipmentSelection.project_id == project_id)
            .delete(synchronize_session=False)
        )
        for role_key, equipment_id in selections.items():
            if equipment_id is None:
                continue
            self.session.add(
                ProjectEquipmentSelection(
                    project_id=project_id,
                    role_key=role_key,
                    equipment_id=equipment_id,
                )
            )
            self._ensure_project_equipment_link(project_id, equipment_id)
        self.session.flush()
        return ProjectEquipmentSelectionsRecord(project_id=project_id, selections=selections)

    def _get_item_model(self, equipment_id: int) -> EquipmentItem:
        item = self.session.query(EquipmentItem).filter(EquipmentItem.id == equipment_id).first()
        if item is None:
            raise AppError(404, "equipment_item_not_found", "Equipment item not found")
        return item

    def _get_project_model(self, project_id: int) -> Project:
        project = self.session.query(Project).filter(Project.id == project_id).first()
        if project is None:
            raise AppError(404, "project_not_found", "Project not found")
        return project

    def _create_item_model(self, data: dict) -> EquipmentItem:
        category = self._validate_category(data.get("category"))
        compatible_equipment_ids = self._normalize_compatible_ids(data.get("compatible_equipment_ids") or [], equipment_id=None)
        legacy_smoke_addressing = self._validate_smoke_addressing(
            category,
            data.get("smoke_addressing"),
            allow_implicit_clear=False,
        )
        try:
            specs = normalize_specs(
                category,
                data.get("specs"),
                smoke_addressing=legacy_smoke_addressing,
                standby_current_ma=data.get("standby_current_ma"),
                alarm_current_ma=data.get("alarm_current_ma"),
                require_complete=True,
            )
        except EquipmentSpecsValidationError as exc:
            raise AppError(400, exc.code, exc.detail) from exc

        item = EquipmentItem(
            name=self._normalize_required_text(data["name"], field_name="name"),
            category=category,
            description=self._normalize_text(data.get("description")),
            price=self._normalize_price(data.get("price")),
            manufacturer=self._normalize_text(data.get("manufacturer")),
            service_life_years=self._normalize_optional_int(data.get("service_life_years"), field_name="service_life_years"),
            notes=self._normalize_text(data.get("notes")),
            specs=specs,
            coverage_summary=self._normalize_text(data.get("coverage_summary")),
            standby_current_ma=self._normalize_number(data.get("standby_current_ma")),
            alarm_current_ma=self._normalize_number(data.get("alarm_current_ma")),
            smoke_addressing=specs.get("addressing_mode") if category == "smoke" else None,
            connection_diagram_path=self._normalize_text(data.get("connection_diagram_path")),
            label_pdf_path=self._normalize_text(data.get("label_pdf_path")),
            manual_pdf_path=self._normalize_text(data.get("manual_pdf_path")),
        )
        self.session.add(item)
        self.session.flush()
        self._replace_compatibility_links(item.id, compatible_equipment_ids)
        self.session.flush()
        return item

    def _ensure_project_equipment_link(self, project_id: int, equipment_id: int) -> None:
        existing = (
            self.session.query(ProjectEquipmentLink)
            .filter(
                ProjectEquipmentLink.project_id == project_id,
                ProjectEquipmentLink.equipment_id == equipment_id,
            )
            .first()
        )
        if existing is None:
            self.session.add(ProjectEquipmentLink(project_id=project_id, equipment_id=equipment_id))

    def _build_project_equipment_list(self, project_id: int) -> ProjectEquipmentListRecord:
        items = (
            self.session.query(EquipmentItem)
            .join(ProjectEquipmentLink, ProjectEquipmentLink.equipment_id == EquipmentItem.id)
            .filter(ProjectEquipmentLink.project_id == project_id)
            .order_by(EquipmentItem.category.asc(), EquipmentItem.name.asc(), EquipmentItem.id.asc())
            .all()
        )
        compatibility_map = self._get_compatibility_map([item.id for item in items])
        return ProjectEquipmentListRecord(
            project_id=project_id,
            items=[
                EquipmentItemRecord.from_model(item, compatible_equipment_ids=compatibility_map.get(item.id, []))
                for item in items
            ],
        )

    def _normalize_project_selections(self, raw_selections: dict[str, int | None]) -> dict[str, int | None]:
        provided_roles = set(raw_selections.keys())
        expected_roles = set(PROJECT_EQUIPMENT_ROLES)
        if provided_roles != expected_roles:
            raise AppError(
                400,
                "invalid_project_equipment_roles",
                "Project equipment selections must include the full role map",
            )

        normalized: dict[str, int | None] = {}
        for role_key, equipment_id in raw_selections.items():
            expected_category = PROJECT_EQUIPMENT_ROLE_CATEGORY_MAP.get(role_key)
            if expected_category is None:
                raise AppError(400, "unknown_project_equipment_role", f"Unknown project equipment role: {role_key}")
            if equipment_id is None:
                normalized[role_key] = None
                continue
            equipment = self._get_item_model(int(equipment_id))
            if equipment.category != expected_category:
                raise AppError(
                    400,
                    "project_equipment_category_mismatch",
                    f"Equipment for role {role_key} must belong to category {expected_category}",
                )
            normalized[role_key] = equipment.id
        return normalized

    def _validate_category_assignments(self, equipment_id: int, target_category: str) -> None:
        rows = (
            self.session.query(ProjectEquipmentSelection)
            .filter(ProjectEquipmentSelection.equipment_id == equipment_id)
            .all()
        )
        for row in rows:
            expected_category = PROJECT_EQUIPMENT_ROLE_CATEGORY_MAP.get(row.role_key)
            if expected_category != target_category:
                raise AppError(
                    409,
                    "equipment_item_category_incompatible_with_project_selection",
                    "Equipment category cannot be changed while the item is assigned to incompatible project roles",
                )

    def _validate_element_assignments(self, equipment_id: int, target_category: str) -> None:
        for fire_alarm in self.session.query(FireAlarm).filter(FireAlarm.equipment_id == equipment_id).all():
            allowed_categories = FIRE_ALARM_DEVICE_CATEGORY_MAP.get(str(fire_alarm.device_type or ""), ())
            if allowed_categories and target_category not in allowed_categories:
                raise AppError(
                    409,
                    "equipment_item_category_incompatible_with_element_usage",
                    "Equipment category cannot be changed while it is used by incompatible fire alarm elements",
                )
        for device in self.session.query(SoueDevice).filter(SoueDevice.equipment_id == equipment_id).all():
            allowed_categories = SOUE_DEVICE_CATEGORY_MAP.get(str(device.device_type or ""), ())
            if allowed_categories and target_category not in allowed_categories:
                raise AppError(
                    409,
                    "equipment_item_category_incompatible_with_element_usage",
                    "Equipment category cannot be changed while it is used by incompatible SOUE elements",
                )
        for instrument in self.session.query(SignalInstrument).filter(SignalInstrument.equipment_id == equipment_id).all():
            allowed_categories = SIGNAL_INSTRUMENT_CATEGORY_MAP.get(str(instrument.instrument_type or ""), ())
            if allowed_categories and target_category not in allowed_categories:
                raise AppError(
                    409,
                    "equipment_item_category_incompatible_with_element_usage",
                    "Equipment category cannot be changed while it is used by incompatible instruments",
                )

    def _normalize_compatible_ids(self, values: list[int], equipment_id: int | None) -> list[int]:
        normalized_ids = sorted({int(value) for value in values})
        if equipment_id is not None and equipment_id in normalized_ids:
            raise AppError(400, "equipment_item_self_compatibility", "Equipment item cannot be compatible with itself")
        if not normalized_ids:
            return []
        existing_ids = {
            item_id
            for (item_id,) in (
                self.session.query(EquipmentItem.id)
                .filter(EquipmentItem.id.in_(normalized_ids))
                .all()
            )
        }
        missing = [item_id for item_id in normalized_ids if item_id not in existing_ids]
        if missing:
            raise AppError(400, "equipment_item_compatibility_not_found", "Compatible equipment item not found")
        return normalized_ids

    def _replace_compatibility_links(self, equipment_id: int, compatible_equipment_ids: list[int]) -> None:
        (
            self.session.query(EquipmentCompatibilityLink)
            .filter(
                or_(
                    EquipmentCompatibilityLink.equipment_id == equipment_id,
                    EquipmentCompatibilityLink.compatible_equipment_id == equipment_id,
                )
            )
            .delete(synchronize_session=False)
        )
        for compatible_equipment_id in compatible_equipment_ids:
            left_id, right_id = self._ordered_pair(equipment_id, compatible_equipment_id)
            self.session.add(
                EquipmentCompatibilityLink(
                    equipment_id=left_id,
                    compatible_equipment_id=right_id,
                )
            )

    def _get_compatibility_map(self, equipment_ids: list[int]) -> dict[int, list[int]]:
        if not equipment_ids:
            return {}
        result = {equipment_id: [] for equipment_id in equipment_ids}
        links = (
            self.session.query(EquipmentCompatibilityLink)
            .filter(
                or_(
                    EquipmentCompatibilityLink.equipment_id.in_(equipment_ids),
                    EquipmentCompatibilityLink.compatible_equipment_id.in_(equipment_ids),
                )
            )
            .all()
        )
        for link in links:
            if link.equipment_id in result:
                result[link.equipment_id].append(link.compatible_equipment_id)
            if link.compatible_equipment_id in result:
                result[link.compatible_equipment_id].append(link.equipment_id)
        return {
            equipment_id: sorted(set(compatible_ids))
            for equipment_id, compatible_ids in result.items()
        }

    def _count_equipment_usage_globally(self, equipment_id: int) -> int:
        return (
            self.session.query(FireAlarm).filter(FireAlarm.equipment_id == equipment_id).count()
            + self.session.query(SoueDevice).filter(SoueDevice.equipment_id == equipment_id).count()
            + self.session.query(SignalInstrument).filter(SignalInstrument.equipment_id == equipment_id).count()
        )

    def _count_project_item_usage(self, project_id: int, equipment_id: int) -> int:
        return (
            self.session.query(FireAlarm)
            .join(FloorPlan, FloorPlan.id == FireAlarm.floor_plan_id)
            .filter(FloorPlan.project_id == project_id, FireAlarm.equipment_id == equipment_id)
            .count()
            + self.session.query(SoueDevice)
            .join(FloorPlan, FloorPlan.id == SoueDevice.floor_plan_id)
            .filter(FloorPlan.project_id == project_id, SoueDevice.equipment_id == equipment_id)
            .count()
            + self.session.query(SignalInstrument)
            .join(FloorPlan, FloorPlan.id == SignalInstrument.floor_plan_id)
            .filter(FloorPlan.project_id == project_id, SignalInstrument.equipment_id == equipment_id)
            .count()
        )

    @staticmethod
    def _normalize_text(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None

    @staticmethod
    def _normalize_required_text(value: str | None, *, field_name: str) -> str:
        normalized = SqlAlchemyEquipmentRepository._normalize_text(value)
        if normalized is None:
            raise AppError(400, "equipment_item_required_field_missing", f"Field {field_name} is required")
        return normalized

    @staticmethod
    def _normalize_number(value: float | int | None) -> float | None:
        if value is None or value == "":
            return None
        return float(value)

    @staticmethod
    def _normalize_price(value: float | int | None) -> float | None:
        normalized = SqlAlchemyEquipmentRepository._normalize_number(value)
        return round(normalized, 2) if normalized is not None else None

    @staticmethod
    def _normalize_optional_int(value: float | int | None, *, field_name: str) -> int | None:
        if value is None or value == "":
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError) as exc:
            raise AppError(400, "equipment_item_invalid_integer_field", f"Field {field_name} must be an integer") from exc
        if not numeric.is_integer():
            raise AppError(400, "equipment_item_invalid_integer_field", f"Field {field_name} must be an integer")
        return int(numeric)

    @staticmethod
    def _validate_category(category: str) -> str:
        normalized = str(category).strip()
        if normalized not in EQUIPMENT_CATEGORIES:
            raise AppError(400, "invalid_equipment_category", f"Unsupported equipment category: {category}")
        return normalized

    @staticmethod
    def _validate_smoke_addressing(
        category: str,
        smoke_addressing: str | None,
        *,
        allow_implicit_clear: bool,
    ) -> str | None:
        if category != "smoke":
            if smoke_addressing not in (None, ""):
                raise AppError(
                    400,
                    "smoke_addressing_only_for_smoke_equipment",
                    "Smoke addressing is only supported for smoke equipment",
                )
            return None

        if smoke_addressing in (None, "") and allow_implicit_clear:
            return None
        if smoke_addressing in (None, ""):
            return None
        normalized = str(smoke_addressing).strip()
        if normalized not in SMOKE_ADDRESSING_VALUES:
            raise AppError(400, "invalid_smoke_addressing", f"Unsupported smoke addressing value: {smoke_addressing}")
        return normalized

    @staticmethod
    def _ordered_pair(left_id: int, right_id: int) -> tuple[int, int]:
        return (left_id, right_id) if left_id < right_id else (right_id, left_id)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)
