"""Regression tests for the standalone recognition training runner script."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_runner_module():
    script_path = Path(__file__).resolve().parents[1] / "tools" / "run_recognition_training.py"
    spec = importlib.util.spec_from_file_location("run_recognition_training_script", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_runner_bootstrap_adds_project_root_to_sys_path(monkeypatch):
    module = _load_runner_module()
    project_root = str(Path(__file__).resolve().parents[1])
    normalized = str(Path(project_root).resolve())
    monkeypatch.setattr(sys, "path", [item for item in sys.path if str(Path(item).resolve()) != normalized])

    resolved = module._ensure_project_root_on_path()

    assert str(resolved.resolve()) == normalized
    assert str(Path(sys.path[0]).resolve()) == normalized
