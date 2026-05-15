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
    facility_genitive: str | None = None
    facility_instrumental: str | None = None
    facility_address: str | None = None
    project_description: str | None = None
    stage: str = "R"
    number_of_floors: int = 1
    owner_user_id: int | None = None
    owner_user: dict[str, object] | None = None
    deleted_at: datetime | None = None
    deleted_by_user_id: int | None = None
    deleted_by_user: dict[str, object] | None = None
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
            facility_genitive=getattr(project, "facility_genitive", None),
            facility_instrumental=getattr(project, "facility_instrumental", None),
            facility_address=project.facility_address,
            project_description=project.project_description,
            stage=project.stage,
            number_of_floors=project.number_of_floors,
            owner_user_id=getattr(project, "owner_user_id", None),
            owner_user=(
                project.owner_user.to_summary_dict()
                if getattr(project, "owner_user", None) is not None
                else None
            ),
            deleted_at=getattr(project, "deleted_at", None),
            deleted_by_user_id=getattr(project, "deleted_by_user_id", None),
            deleted_by_user=(
                project.deleted_by_user.to_summary_dict()
                if getattr(project, "deleted_by_user", None) is not None
                else None
            ),
            created_at=project.created_at,
            updated_at=project.updated_at,
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)
