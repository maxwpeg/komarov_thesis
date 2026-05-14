"""Centralized pipeline state management."""

from __future__ import annotations

from backend.modules.pipeline.domain.state import PipelineStateModel
from backend.schemas import PipelineStateRead


class PipelineStateManager:
    """Single entry point for reading and mutating pipeline state."""

    def load(self, raw_state: dict | None, active_signal_system_type: str | None = None) -> dict:
        return PipelineStateModel.normalize(raw_state, active_signal_system_type).to_storage_dict()

    def store(self, floor_plan, state: dict) -> dict:
        normalized = PipelineStateModel.normalize(state, floor_plan.active_signal_system_type).to_storage_dict()
        floor_plan.pipeline_state = normalized
        return normalized

    def read(self, floor_plan_id: int, state: dict) -> PipelineStateRead:
        return PipelineStateRead.model_validate(
            PipelineStateModel.normalize(state).to_read_payload(floor_plan_id)
        )

    def set_step_status(
        self,
        state: dict,
        step_name: str,
        status: str,
        *,
        detected: bool = False,
        committed: bool = False,
        bump_revision: bool = False,
    ) -> dict:
        model = PipelineStateModel.normalize(state)
        model.set_step_status(
            step_name,
            status,
            detected=detected,
            committed=committed,
            bump_revision=bump_revision,
        )
        return model.to_storage_dict()

    def mark_downstream_stale(self, state: dict, from_step: str) -> dict:
        model = PipelineStateModel.normalize(state)
        model.mark_downstream_stale(from_step)
        return model.to_storage_dict()

    def reset_branch_steps(self, state: dict, status: str = "locked") -> dict:
        model = PipelineStateModel.normalize(state)
        model.reset_branch_steps(status=status)
        return model.to_storage_dict()

    def activate_branch_steps(self, state: dict) -> dict:
        model = PipelineStateModel.normalize(state)
        model.activate_branch_steps()
        return model.to_storage_dict()

    def ensure_step_validated(self, state: dict, step_name: str, error_detail: str) -> None:
        PipelineStateModel.normalize(state).ensure_step_validated(step_name, error_detail)
