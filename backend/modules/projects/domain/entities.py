"""Project domain entities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from backend.project_codes import normalize_project_code


@dataclass(slots=True)
class ProjectRecord:
    """Stable project snapshot used outside the persistence layer."""

    id: int
    name: str
    project_type: str
    number: int
    year: int
    code: str
    contractor: str
    engineer: str
    cpe: str
    checker: str
    facility: str
    facility_address: str | None = None
    project_description: str | None = None
    stage: str = "R"
    number_of_floors: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def from_model(cls, project) -> "ProjectRecord":
        return cls(
            id=project.id,
            name=project.name,
            project_type=project.project_type,
            number=project.number,
            year=project.year,
            code=normalize_project_code(project.code),
            contractor=project.contractor,
            engineer=project.engineer,
            cpe=project.cpe,
            checker=project.checker,
            facility=project.facility,
            facility_address=project.facility_address,
            project_description=project.project_description,
            stage=project.stage,
            number_of_floors=project.number_of_floors,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
