"""Tests for the centralized pipeline state manager."""

from __future__ import annotations

from backend.modules.pipeline.application.state_manager import PipelineStateManager


def test_state_manager_validates_step_and_marks_only_downstream_stale():
    manager = PipelineStateManager()
    state = manager.load(None, "non_addressable")

    state = manager.set_step_status(state, "walls", "validated", committed=True, bump_revision=True)
    assert state["steps"]["walls"]["status"] == "validated"
    assert state["active_step"] == "openings"

    state = manager.set_step_status(state, "openings", "validated", committed=True, bump_revision=True)
    state = manager.mark_downstream_stale(state, "walls")

    assert state["steps"]["walls"]["status"] == "validated"
    assert state["steps"]["openings"]["status"] == "stale"
    assert state["steps"]["rooms"]["status"] == "draft"


def test_state_manager_unlocks_branch_steps_after_zkspc():
    manager = PipelineStateManager()
    state = manager.load(None, "addressable")

    state = manager.set_step_status(state, "zkspc", "validated", committed=True, bump_revision=True)
    state = manager.activate_branch_steps(state)

    assert state["branches"]["addressable"]["steps"]["fire_alarms"]["status"] == "draft"
    assert state["branches"]["addressable"]["steps"]["devices_cables"]["status"] == "draft"
    assert state["branches"]["non_addressable"]["steps"]["fire_alarms"]["status"] == "draft"
