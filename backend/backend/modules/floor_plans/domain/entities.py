"""Floor plan domain entities."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class FloorPlanRecord:
    """Stable floor-plan snapshot decoupled from SQLAlchemy models."""

    id: int
    project_id: int
    floor_number: int
    name: str | None = None
    original_image_path: str | None = None
    processed_image_path: str | None = None
    image_width: int | None = None
    image_height: int | None = None
    scale_factor: float = 1.0
    ceiling_height_mm: float = 3000.0
    active_signal_system_type: str = "non_addressable"
    pipeline_state: dict[str, Any] | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    walls: list[dict[str, Any]] = field(default_factory=list)
    stairs: list[dict[str, Any]] = field(default_factory=list)
    doors: list[dict[str, Any]] = field(default_factory=list)
    windows: list[dict[str, Any]] = field(default_factory=list)
    rooms: list[dict[str, Any]] = field(default_factory=list)
    dimensions: list[dict[str, Any]] = field(default_factory=list)
    fire_alarms: list[dict[str, Any]] = field(default_factory=list)
    soue_devices: list[dict[str, Any]] = field(default_factory=list)
    zkspc_zones: list[dict[str, Any]] = field(default_factory=list)
    signal_instruments: list[dict[str, Any]] = field(default_factory=list)
    cable_routes: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_model(cls, floor_plan, *, include_elements: bool = False) -> "FloorPlanRecord":
        return cls(
            id=floor_plan.id,
            project_id=floor_plan.project_id,
            floor_number=floor_plan.floor_number,
            name=floor_plan.name,
            original_image_path=floor_plan.original_image_path,
            processed_image_path=floor_plan.processed_image_path,
            image_width=floor_plan.image_width,
            image_height=floor_plan.image_height,
            scale_factor=floor_plan.scale_factor,
            ceiling_height_mm=floor_plan.ceiling_height_mm,
            active_signal_system_type=floor_plan.active_signal_system_type,
            pipeline_state=floor_plan.pipeline_state,
            created_at=floor_plan.created_at,
            updated_at=floor_plan.updated_at,
            walls=[item.to_dict() for item in floor_plan.walls] if include_elements else [],
            stairs=[item.to_dict() for item in floor_plan.stairs] if include_elements else [],
            doors=[item.to_dict() for item in floor_plan.doors] if include_elements else [],
            windows=[item.to_dict() for item in floor_plan.windows] if include_elements else [],
            rooms=[item.to_dict() for item in floor_plan.rooms] if include_elements else [],
            dimensions=[item.to_dict() for item in floor_plan.dimensions] if include_elements else [],
            fire_alarms=[item.to_dict() for item in floor_plan.fire_alarms] if include_elements else [],
            soue_devices=[item.to_dict() for item in floor_plan.soue_devices] if include_elements else [],
            zkspc_zones=[item.to_dict() for item in floor_plan.zkspc_zones] if include_elements else [],
            signal_instruments=[item.to_dict() for item in floor_plan.signal_instruments] if include_elements else [],
            cable_routes=[item.to_dict() for item in floor_plan.cable_routes] if include_elements else [],
        )

    def to_dict(self, include_elements: bool = False) -> dict[str, Any]:
        data = asdict(self)
        if not include_elements:
            data["walls"] = []
            data["stairs"] = []
            data["doors"] = []
            data["windows"] = []
            data["rooms"] = []
            data["dimensions"] = []
            data["fire_alarms"] = []
            data["soue_devices"] = []
            data["zkspc_zones"] = []
            data["signal_instruments"] = []
            data["cable_routes"] = []
        return data
