"""Helpers for mutating branch-specific pipeline state."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.modules.pipeline.domain.state import PipelineStateModel, normalize_signal_system_type


def normalize_pipeline_state(raw_state: dict | None, active_signal_system_type: str | None = None) -> dict:
    """Normalize persisted state into the canonical storage shape."""
    return PipelineStateModel.normalize(raw_state, active_signal_system_type).to_storage_dict()


def update_signal_branch_state(
    floor_plan,
    system_type: str,
    *,
    fire_alarms_status: str | None = None,
    devices_cables_status: str | None = None,
    active_step: str | None = None,
) -> dict:
    """Update the branch-specific state for a floor plan."""
    normalized_system = normalize_signal_system_type(system_type)
    state = PipelineStateModel.normalize(floor_plan.pipeline_state, floor_plan.active_signal_system_type)
    state.active_signal_system_type = normalized_system
    branch = state.branches[normalized_system]
    now = datetime.now(timezone.utc)

    if fire_alarms_status is not None:
        step = branch.steps["fire_alarms"]
        step.status = fire_alarms_status
        if fire_alarms_status == "validated":
            step.revision = max(1, int(step.revision or 0))
            step.committed_at = now
    if devices_cables_status is not None:
        step = branch.steps["devices_cables"]
        step.status = devices_cables_status
        if devices_cables_status == "validated":
            step.revision = max(1, int(step.revision or 0))
            step.committed_at = now
    if active_step is not None:
        branch.active_step = active_step

    floor_plan.active_signal_system_type = normalized_system
    floor_plan.pipeline_state = state.to_storage_dict()
    return floor_plan.pipeline_state

