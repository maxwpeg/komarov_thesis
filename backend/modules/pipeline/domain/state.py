"""Typed pipeline state used internally by the pipeline module."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.errors import AppError


PIPELINE_STEPS = ("walls", "openings", "rooms", "zkspc")
BRANCH_STEPS = ("fire_alarms", "devices_cables")
SIGNAL_BRANCHES = ("addressable", "non_addressable")
StepStatus = Literal["draft", "validated", "stale", "locked"]


class StepStateModel(BaseModel):
    """Typed state for an individual pipeline step."""

    model_config = ConfigDict(extra="ignore")

    status: StepStatus = "draft"
    revision: int = 0
    detected_at: datetime | None = None
    committed_at: datetime | None = None


class BranchStateModel(BaseModel):
    """Typed state for a signal-system branch."""

    model_config = ConfigDict(extra="ignore")

    active_step: str = "fire_alarms"
    steps: dict[str, StepStateModel] = Field(default_factory=dict)


class PipelineStateModel(BaseModel):
    """Typed model for the persisted pipeline JSON state."""

    model_config = ConfigDict(extra="ignore")

    active_step: str = "walls"
    active_signal_system_type: str = "non_addressable"
    steps: dict[str, StepStateModel] = Field(default_factory=dict)
    branches: dict[str, BranchStateModel] = Field(default_factory=dict)

    @classmethod
    def normalize(cls, raw_state: dict | None, active_signal_system_type: str | None = None) -> "PipelineStateModel":
        state = raw_state or {}
        source_steps = state.get("steps") or {}
        normalized_steps = {
            step_name: StepStateModel.model_validate(source_steps.get(step_name) or {})
            for step_name in PIPELINE_STEPS
        }
        source_branches = state.get("branches") or {}
        normalized_branches: dict[str, BranchStateModel] = {}
        for branch_name in SIGNAL_BRANCHES:
            branch = source_branches.get(branch_name) or {}
            branch_steps = branch.get("steps") or {}
            normalized_branches[branch_name] = BranchStateModel(
                active_step=branch.get("active_step", "fire_alarms"),
                steps={
                    step_name: StepStateModel.model_validate(
                        {
                            "status": (branch_steps.get(step_name) or {}).get("status", "locked"),
                            "revision": int((branch_steps.get(step_name) or {}).get("revision", 0) or 0),
                            "detected_at": (branch_steps.get(step_name) or {}).get("detected_at"),
                            "committed_at": (branch_steps.get(step_name) or {}).get("committed_at"),
                        }
                    )
                    for step_name in BRANCH_STEPS
                },
            )

        return cls(
            active_step=state.get("active_step", "walls"),
            active_signal_system_type=normalize_signal_system_type(
                active_signal_system_type or state.get("active_signal_system_type")
            ),
            steps=normalized_steps,
            branches=normalized_branches,
        )

    def to_storage_dict(self) -> dict[str, object]:
        return self.model_dump(mode="json")

    def to_read_payload(self, floor_plan_id: int) -> dict[str, object]:
        return {
            "floor_plan_id": floor_plan_id,
            **self.to_storage_dict(),
        }

    def set_step_status(
        self,
        step_name: str,
        status: str,
        *,
        detected: bool = False,
        committed: bool = False,
        bump_revision: bool = False,
    ) -> None:
        step = self.steps[step_name]
        step.status = status  # type: ignore[assignment]
        now = datetime.now(timezone.utc)
        if detected:
            step.detected_at = now
        if committed:
            step.committed_at = now
        if bump_revision:
            step.revision += 1

        if status == "validated":
            if step_name == "walls":
                self.active_step = "openings"
            elif step_name == "openings":
                self.active_step = "rooms"
            elif step_name == "rooms":
                self.active_step = "zkspc"
            else:
                self.active_step = "zkspc"
        else:
            self.active_step = step_name

    def mark_downstream_stale(self, from_step: str) -> None:
        start_idx = PIPELINE_STEPS.index(from_step)
        for step_name in PIPELINE_STEPS[start_idx + 1 :]:
            step = self.steps[step_name]
            if step.revision > 0 or step.status in {"validated", "stale"}:
                step.status = "stale"
        for branch_name in SIGNAL_BRANCHES:
            branch = self.branches[branch_name]
            for step_name in BRANCH_STEPS:
                step = branch.steps[step_name]
                if step.revision > 0 or step.status in {"validated", "stale"}:
                    step.status = "stale"

    def reset_branch_steps(self, status: str = "locked") -> None:
        for branch_name in SIGNAL_BRANCHES:
            branch = self.branches[branch_name]
            branch.active_step = "fire_alarms"
            for step_name in BRANCH_STEPS:
                branch.steps[step_name].status = status  # type: ignore[assignment]

    def activate_branch_steps(self) -> None:
        for branch_name in SIGNAL_BRANCHES:
            branch = self.branches[branch_name]
            if branch.steps["fire_alarms"].status == "locked":
                branch.steps["fire_alarms"].status = "draft"
            if branch.steps["devices_cables"].status == "locked":
                branch.steps["devices_cables"].status = "draft"

    def ensure_step_validated(self, step_name: str, error_detail: str) -> None:
        if self.steps[step_name].status != "validated":
            raise AppError(409, "pipeline_step_not_validated", error_detail)


def normalize_signal_system_type(value: str | None) -> str:
    """Normalize arbitrary input into a supported signal-system branch id."""
    return value if value in SIGNAL_BRANCHES else "non_addressable"
