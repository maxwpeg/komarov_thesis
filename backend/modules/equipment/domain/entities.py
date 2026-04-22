"""Domain entities for the equipment catalog."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime

from backend.modules.equipment.domain.specs import coerce_current_specs


@dataclass(slots=True)
class EquipmentItemRecord:
    """Stable equipment snapshot used outside persistence."""

    id: int
    name: str
    category: str
    description: str | None = None
    price: float | None = None
    manufacturer: str | None = None
    service_life_years: int | None = None
    notes: str | None = None
    specs: dict[str, object] = field(default_factory=dict)
    coverage_summary: str | None = None
    standby_current_ma: float | None = None
    alarm_current_ma: float | None = None
    smoke_addressing: str | None = None
    image_path: str | None = None
    label_pdf_path: str | None = None
    manual_pdf_path: str | None = None
    compatible_equipment_ids: list[int] = field(default_factory=list)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_model(
        cls,
        equipment_item,
        *,
        compatible_equipment_ids: list[int] | None = None,
    ) -> "EquipmentItemRecord":
        return cls(
            id=equipment_item.id,
            name=equipment_item.name,
            category=equipment_item.category,
            description=equipment_item.description,
            price=round(float(equipment_item.price), 2) if equipment_item.price is not None else None,
            manufacturer=equipment_item.manufacturer,
            service_life_years=equipment_item.service_life_years,
            notes=equipment_item.notes,
            specs=coerce_current_specs(
                equipment_item.category,
                getattr(equipment_item, "specs", None),
                smoke_addressing=equipment_item.smoke_addressing,
                standby_current_ma=equipment_item.standby_current_ma,
                alarm_current_ma=equipment_item.alarm_current_ma,
            ),
            coverage_summary=equipment_item.coverage_summary,
            standby_current_ma=equipment_item.standby_current_ma,
            alarm_current_ma=equipment_item.alarm_current_ma,
            smoke_addressing=equipment_item.smoke_addressing,
            image_path=equipment_item.image_path,
            label_pdf_path=equipment_item.label_pdf_path,
            manual_pdf_path=equipment_item.manual_pdf_path,
            compatible_equipment_ids=sorted(set(compatible_equipment_ids or [])),
            created_at=equipment_item.created_at,
            updated_at=equipment_item.updated_at,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class ProjectEquipmentSelectionsRecord:
    """Equipment choices assigned to a project by semantic role."""

    project_id: int
    selections: dict[str, int | None]

    def to_dict(self) -> dict[str, object]:
        return {
            "project_id": self.project_id,
            "selections": dict(self.selections),
        }


@dataclass(slots=True)
class ProjectEquipmentListRecord:
    """Equipment linked to a project."""

    project_id: int
    items: list[EquipmentItemRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "project_id": self.project_id,
            "items": [item.to_dict() for item in self.items],
        }
