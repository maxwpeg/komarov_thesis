"""Helpers for mutating branch-specific pipeline state."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.modules.pipeline.domain.state import (
    COMMON_SIGNAL_BRANCH,
    PipelineStateModel,
    SPS_SIGNAL_BRANCHES,
    normalize_active_signal_system_type,
    normalize_signal_system_type,
)


def normalize_pipeline_state(raw_state: dict | None, active_signal_system_type: str | None = None) -> dict:
    """Normalize persisted state into the canonical storage shape."""
    return PipelineStateModel.normalize(raw_state, active_signal_system_type).to_storage_dict()


def update_signal_branch_state(
    floor_plan,
    system_type: str,
    *,
    signal_instruments_status: str | None = None,
    fire_alarms_status: str | None = None,
    devices_cables_status: str | None = None,
    soue_devices_status: str | None = None,
    soue_cables_status: str | None = None,
    active_step: str | None = None,
) -> dict:
    """Update the branch-specific state for a floor plan."""
    normalized_system = normalize_signal_system_type(system_type)
    state = PipelineStateModel.normalize(floor_plan.pipeline_state, floor_plan.active_signal_system_type)
    if normalized_system != COMMON_SIGNAL_BRANCH:
        state.active_signal_system_type = normalize_active_signal_system_type(normalized_system)
    branch = state.branches[normalized_system]
    now = datetime.now(timezone.utc)

    if signal_instruments_status is not None:
        step = branch.steps["signal_instruments"]
        step.status = signal_instruments_status
        if signal_instruments_status == "validated":
            step.revision = max(1, int(step.revision or 0))
            step.committed_at = now
            if normalized_system == COMMON_SIGNAL_BRANCH:
                if branch.steps["soue_devices"].status == "locked":
                    branch.steps["soue_devices"].status = "draft"
                for sps_branch_name in SPS_SIGNAL_BRANCHES:
                    if state.branches[sps_branch_name].steps["fire_alarms"].status == "locked":
                        state.branches[sps_branch_name].steps["fire_alarms"].status = "draft"
            elif branch.steps["fire_alarms"].status == "locked":
                branch.steps["fire_alarms"].status = "draft"
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
            if branch.steps["soue_devices"].status == "locked":
                branch.steps["soue_devices"].status = "draft"
    if soue_devices_status is not None:
        step = branch.steps["soue_devices"]
        step.status = soue_devices_status
        if soue_devices_status == "validated":
            step.revision = max(1, int(step.revision or 0))
            step.committed_at = now
            if branch.steps["soue_cables"].status == "locked":
                branch.steps["soue_cables"].status = "draft"
    if soue_cables_status is not None:
        step = branch.steps["soue_cables"]
        step.status = soue_cables_status
        if soue_cables_status == "validated":
            step.revision = max(1, int(step.revision or 0))
            step.committed_at = now
    if active_step is not None:
        branch.active_step = active_step

    if normalized_system != COMMON_SIGNAL_BRANCH:
        floor_plan.active_signal_system_type = normalize_active_signal_system_type(normalized_system)
    floor_plan.pipeline_state = state.to_storage_dict()
    return floor_plan.pipeline_state
