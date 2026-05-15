"""Administrative audit log routes."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse, Response
from sqlalchemy.orm import Session

from backend.auth import AuthenticatedUser, require_developer
from backend.database import get_db
from backend.mappers import audit_event_read
from backend.models import AuditEvent
from backend.schemas import AuditEventRead


router = APIRouter(tags=["system"], dependencies=[Depends(require_developer)])


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    return datetime.fromisoformat(normalized)


def _query_audit_events(
    db: Session,
    *,
    user_id: int | None = None,
    project_id: int | None = None,
    floor_plan_id: int | None = None,
    category: str | None = None,
    action: str | None = None,
    event_name: str | None = None,
    use_case: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = 500,
) -> list[AuditEvent]:
    query = db.query(AuditEvent)
    if user_id is not None:
        query = query.filter(AuditEvent.user_id == user_id)
    if project_id is not None:
        query = query.filter(AuditEvent.project_id == project_id)
    if floor_plan_id is not None:
        query = query.filter(AuditEvent.floor_plan_id == floor_plan_id)
    if category:
        query = query.filter(AuditEvent.category == category)
    selected_action = event_name or action
    if selected_action:
        query = query.filter(AuditEvent.event_name == selected_action)
    if use_case:
        query = query.filter(AuditEvent.use_case == use_case)
    parsed_from = _parse_datetime(date_from)
    if parsed_from is not None:
        query = query.filter(AuditEvent.created_at >= parsed_from)
    parsed_to = _parse_datetime(date_to)
    if parsed_to is not None:
        query = query.filter(AuditEvent.created_at <= parsed_to)
    return (
        query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc())
        .limit(max(1, min(int(limit), 5000)))
        .all()
    )


@router.get("/api/audit", response_model=list[AuditEventRead])
def list_audit_events(
    user_id: int | None = Query(None),
    project_id: int | None = Query(None),
    floor_plan_id: int | None = Query(None),
    category: str | None = Query(None),
    action: str | None = Query(None),
    event_name: str | None = Query(None),
    use_case: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_developer),
) -> list[AuditEventRead]:
    events = _query_audit_events(
        db,
        user_id=user_id,
        project_id=project_id,
        floor_plan_id=floor_plan_id,
        category=category,
        action=action,
        event_name=event_name,
        use_case=use_case,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return [audit_event_read(event) for event in events]


@router.get("/api/audit/export")
def export_audit_events(
    format: Literal["csv", "json"] = Query("csv"),
    user_id: int | None = Query(None),
    project_id: int | None = Query(None),
    floor_plan_id: int | None = Query(None),
    category: str | None = Query(None),
    action: str | None = Query(None),
    event_name: str | None = Query(None),
    use_case: str | None = Query(None),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    limit: int = Query(5000, ge=1, le=5000),
    db: Session = Depends(get_db),
    _: AuthenticatedUser = Depends(require_developer),
):
    events = _query_audit_events(
        db,
        user_id=user_id,
        project_id=project_id,
        floor_plan_id=floor_plan_id,
        category=category,
        action=action,
        event_name=event_name,
        use_case=use_case,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    rows = [audit_event_read(event).model_dump(mode="json") for event in events]
    if format == "json":
        return JSONResponse(
            rows,
            headers={"Content-Disposition": 'attachment; filename="audit-log.json"'},
        )

    output = io.StringIO()
    fieldnames = [
        "id",
        "created_at",
        "user_id",
        "category",
        "event_name",
        "use_case",
        "project_id",
        "floor_plan_id",
        "pipeline_step",
        "system_type",
        "request_id",
        "payload",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        csv_row = dict(row)
        csv_row["payload"] = json.dumps(row.get("payload") or {}, ensure_ascii=False)
        writer.writerow(csv_row)
    return Response(
        output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="audit-log.csv"'},
    )
