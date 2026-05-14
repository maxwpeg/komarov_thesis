"""Typed pipeline state used internally by the pipeline module."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.errors import AppError


PIPELINE_STEPS = ("walls", "openings", "rooms", "zkspc")
BRANCH_STEPS = ("signal_instruments", "fire_alarms", "devices_cables", "soue_devices", "soue_cables")
SPS_SIGNAL_BRANCHES = ("addressable", "non_addressable")
COMMON_SIGNAL_BRANCH = "common"
SIGNAL_BRANCHES = SPS_SIGNAL_BRANCHES + (COMMON_SIGNAL_BRANCH,)
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

    active_step: str = "signal_instruments"
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
                active_step=branch.get("active_step", "signal_instruments"),
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

        cls._migrate_legacy_common_branch_state(normalized_branches)
        cls._unlock_branch_steps(normalized_steps, normalized_branches)

        return cls(
            active_step=state.get("active_step", "walls"),
            active_signal_system_type=normalize_active_signal_system_type(
                active_signal_system_type or state.get("active_signal_system_type")
            ),
            steps=normalized_steps,
            branches=normalized_branches,
        )

    @staticmethod
    def _clone_step_state(step: StepStateModel) -> StepStateModel:
        return StepStateModel.model_validate(step.model_dump(mode="python"))

    @classmethod
    def _migrate_legacy_common_branch_state(cls, branches: dict[str, BranchStateModel]) -> None:
        common_branch = branches[COMMON_SIGNAL_BRANCH]
        legacy_branch = branches["non_addressable"]
        legacy_steps = ("signal_instruments", "soue_devices", "soue_cables")
        for step_name in legacy_steps:
            common_step = common_branch.steps[step_name]
            legacy_step = legacy_branch.steps[step_name]
            if common_step.revision > 0 or common_step.status != "locked":
                continue
            if legacy_step.revision <= 0 and legacy_step.status == "locked":
                continue
            common_branch.steps[step_name] = cls._clone_step_state(legacy_step)
        if common_branch.active_step == "signal_instruments" and legacy_branch.active_step in legacy_steps:
            common_branch.active_step = legacy_branch.active_step

    @staticmethod
    def _unlock_branch_steps(
        normalized_steps: dict[str, StepStateModel],
        normalized_branches: dict[str, BranchStateModel],
    ) -> None:
        zkspc_validated = normalized_steps["zkspc"].status == "validated"
        common_branch = normalized_branches[COMMON_SIGNAL_BRANCH]

        common_steps = common_branch.steps
        if zkspc_validated and common_steps["signal_instruments"].status == "locked":
            common_steps["signal_instruments"].status = "draft"
        if common_steps["signal_instruments"].status == "validated":
            if common_steps["soue_devices"].status == "locked":
                common_steps["soue_devices"].status = "draft"
            for branch_name in SPS_SIGNAL_BRANCHES:
                sps_steps = normalized_branches[branch_name].steps
                if sps_steps["fire_alarms"].status == "locked":
                    sps_steps["fire_alarms"].status = "draft"
        if common_steps["soue_devices"].status == "validated" and common_steps["soue_cables"].status == "locked":
            common_steps["soue_cables"].status = "draft"

        for branch_name in SPS_SIGNAL_BRANCHES:
            branch_steps_model = normalized_branches[branch_name].steps
            if branch_steps_model["fire_alarms"].status == "validated" and branch_steps_model["devices_cables"].status == "locked":
                branch_steps_model["devices_cables"].status = "draft"

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
            branch.active_step = "signal_instruments"
            for step_name in BRANCH_STEPS:
                branch.steps[step_name].status = status  # type: ignore[assignment]

    def activate_branch_steps(self) -> None:
        self._unlock_branch_steps(self.steps, self.branches)
        for branch_name in SIGNAL_BRANCHES:
            branch = self.branches[branch_name]
            for step_name in BRANCH_STEPS:
                if branch.steps[step_name].status not in {"draft", "validated", "stale"}:
                    branch.steps[step_name].status = "locked"

    def ensure_step_validated(self, step_name: str, error_detail: str) -> None:
        if self.steps[step_name].status != "validated":
            raise AppError(409, "pipeline_step_not_validated", error_detail)


def normalize_signal_system_type(value: str | None) -> str:
    """Normalize arbitrary input into a supported signal-system branch id."""
    return value if value in SIGNAL_BRANCHES else "non_addressable"


def normalize_active_signal_system_type(value: str | None) -> str:
    """Normalize the active SPS selector value and keep it branch-specific."""
    return value if value in SPS_SIGNAL_BRANCHES else "non_addressable"
