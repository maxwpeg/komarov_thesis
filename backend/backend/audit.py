"""Helpers for persisting security-relevant audit events."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.modules.shared.infrastructure.persistence.models import AuditEvent
from backend.modules.shared.observability.context import get_request_id


def record_audit_event(
    db: Session,
    event_name: str,
    *,
    category: str = "security",
    use_case: str,
    user_id: int | None = None,
    project_id: int | None = None,
    floor_plan_id: int | None = None,
    pipeline_step: str | None = None,
    system_type: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    event_payload = dict(payload or {})
    if user_id is not None:
        event_payload.setdefault("user_id", user_id)
    db.add(
        AuditEvent(
            event_name=event_name,
            category=category,
            use_case=use_case,
            user_id=user_id,
            request_id=get_request_id(),
            project_id=project_id,
            floor_plan_id=floor_plan_id,
            pipeline_step=pipeline_step,
            system_type=system_type,
            payload=event_payload,
        )
    )
