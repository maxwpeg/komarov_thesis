"""Architecture boundary checks for the modular monolith."""

from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"


def _python_files(root: Path) -> list[Path]:
    return [path for path in root.rglob("*.py") if "__pycache__" not in path.parts]


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module)
    return imports


def test_routers_do_not_import_legacy_services():
    forbidden = []
    for path in _python_files(BACKEND / "routers"):
        imports = _imports(path)
        if any(name == "backend.services" or name.startswith("backend.services.") for name in imports):
            forbidden.append(path.relative_to(ROOT).as_posix())
    assert forbidden == []


def test_domain_layer_does_not_depend_on_fastapi_sqlalchemy_or_api_schemas():
    forbidden = []
    for path in _python_files(BACKEND / "modules"):
        if "domain" not in path.parts:
            continue
        imports = _imports(path)
        bad = [
            name
            for name in imports
            if name.startswith("fastapi")
            or name.startswith("sqlalchemy")
            or name == "backend.schemas"
            or name.startswith("backend.schemas.")
            or name == "backend.services"
            or name.startswith("backend.services.")
        ]
        if bad:
            forbidden.append((path.relative_to(ROOT).as_posix(), sorted(set(bad))))
    assert forbidden == []


def test_application_layer_does_not_import_legacy_services_directly():
    allowed = {
        "backend.modules.pipeline.infrastructure.legacy_orchestrator",
        "backend.modules.shared.infrastructure.storage",
    }
    forbidden = []
    for path in _python_files(BACKEND / "modules"):
        if "application" not in path.parts:
            continue
        imports = _imports(path)
        bad = [
            name
            for name in imports
            if (name == "backend.services" or name.startswith("backend.services."))
            and name not in allowed
        ]
        if bad:
            forbidden.append((path.relative_to(ROOT).as_posix(), sorted(set(bad))))
    assert forbidden == []


def test_application_layer_does_not_import_persistence_models_directly():
    forbidden = []
    for path in _python_files(BACKEND / "modules"):
        if "application" not in path.parts:
            continue
        imports = _imports(path)
        bad = [
            name
            for name in imports
            if name == "backend.models"
            or name.startswith("backend.models.")
            or name == "backend.modules.shared.infrastructure.persistence.models"
            or name.startswith("backend.modules.shared.infrastructure.persistence.models.")
        ]
        if bad:
            forbidden.append((path.relative_to(ROOT).as_posix(), sorted(set(bad))))
    assert forbidden == []


def test_modular_code_uses_canonical_persistence_imports():
    forbidden = []
    for path in _python_files(BACKEND / "modules"):
        imports = _imports(path)
        bad = [name for name in imports if name == "backend.models" or name.startswith("backend.models.")]
        if bad and "shared" not in path.parts:
            forbidden.append((path.relative_to(ROOT).as_posix(), sorted(set(bad))))
    assert forbidden == []
