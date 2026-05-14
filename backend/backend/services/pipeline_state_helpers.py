"""Compatibility shim for branch-state helpers."""

from backend.modules.pipeline.application.branch_state import normalize_pipeline_state, update_signal_branch_state

__all__ = ["normalize_pipeline_state", "update_signal_branch_state"]
