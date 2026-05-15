"""Export the current local runtime state as Docker first-run seed data."""

from __future__ import annotations

import argparse
import re
import shutil
import sqlite3
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_ROOT.parent
sys.path.insert(0, str(BACKEND_ROOT))

from backend.config import settings  # noqa: E402


DEFAULT_SEED_ROOT = REPOSITORY_ROOT / "docker" / "seed"
PATH_COLUMN_RE = re.compile(r"(^path$|_path$|_dir$)")


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _copy_tree_contents(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        return
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            shutil.copytree(child, target, dirs_exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(child, target)


def _managed_roots() -> list[tuple[Path, str | None]]:
    roots: list[tuple[Path, str | None]] = [
        (settings.object_storage_dir, None),
        (settings.uploads_dir, "uploads"),
        (settings.outputs_dir, "outputs"),
        (settings.debug_output_dir, "debug_output"),
    ]
    for base in {settings.data_dir, settings.project_root, REPOSITORY_ROOT}:
        roots.extend(
            [
                (base / "storage_objects", None),
                (base / "uploads", "uploads"),
                (base / "outputs", "outputs"),
                (base / "debug_output", "debug_output"),
            ]
        )
    unique: list[tuple[Path, str | None]] = []
    seen: set[tuple[str, str | None]] = set()
    for root, prefix in roots:
        key = (str(root.resolve(strict=False)).lower(), prefix)
        if key not in seen:
            seen.add(key)
            unique.append((root, prefix))
    return unique


def _absolute_to_asset_path(raw_value: str) -> str | None:
    candidate = Path(raw_value)
    if not candidate.is_absolute():
        return None
    resolved = candidate.resolve(strict=False)
    for root, prefix in _managed_roots():
        resolved_root = root.resolve(strict=False)
        try:
            relative = resolved.relative_to(resolved_root)
        except ValueError:
            continue
        normalized = relative.as_posix()
        return f"{prefix}/{normalized}" if prefix else normalized
    return None


def _normalize_asset_reference(value: object) -> object:
    if not isinstance(value, str):
        return value
    raw = value.strip()
    if not raw:
        return value
    if "://" in raw or raw.startswith("//"):
        return value
    absolute = _absolute_to_asset_path(raw)
    if absolute is not None:
        return absolute
    normalized = raw.replace("\\", "/")
    if normalized.startswith("/api/assets/"):
        normalized = normalized[len("/api/assets/") :]
    normalized = normalized.lstrip("/")
    if normalized.startswith("backend/"):
        normalized = normalized[len("backend/") :]
    if normalized.startswith("storage_objects/"):
        normalized = normalized[len("storage_objects/") :]
    return normalized or value


def _path_columns(connection: sqlite3.Connection, table_name: str) -> list[str]:
    rows = connection.execute(f"PRAGMA table_info({_quote_identifier(table_name)})").fetchall()
    columns = []
    for row in rows:
        name = str(row[1])
        if name == "resource_path":
            continue
        if PATH_COLUMN_RE.search(name):
            columns.append(name)
    return columns


def normalize_seed_database(database_path: Path) -> int:
    changed = 0
    connection = sqlite3.connect(database_path)
    try:
        tables = [
            str(row[0])
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for table_name in tables:
            columns = _path_columns(connection, table_name)
            if not columns:
                continue
            select_columns = ", ".join(["rowid", *(_quote_identifier(column) for column in columns)])
            rows = connection.execute(f"SELECT {select_columns} FROM {_quote_identifier(table_name)}").fetchall()
            for row in rows:
                rowid = row[0]
                updates: dict[str, object] = {}
                for index, column in enumerate(columns, start=1):
                    old_value = row[index]
                    new_value = _normalize_asset_reference(old_value)
                    if new_value != old_value:
                        updates[column] = new_value
                if not updates:
                    continue
                assignments = ", ".join(f"{_quote_identifier(column)} = ?" for column in updates)
                values = [*updates.values(), rowid]
                connection.execute(
                    f"UPDATE {_quote_identifier(table_name)} SET {assignments} WHERE rowid = ?",
                    values,
                )
                changed += len(updates)
        connection.commit()
    finally:
        connection.close()
    return changed


def export_seed(seed_root: Path) -> None:
    database_dir = seed_root / "database"
    files_dir = seed_root / "files"
    database_dir.mkdir(parents=True, exist_ok=True)
    if files_dir.exists():
        shutil.rmtree(files_dir)
    files_dir.mkdir(parents=True, exist_ok=True)

    source_db = settings.database_file
    if not source_db.exists():
        raise FileNotFoundError(f"Current database was not found: {source_db}")
    seed_db = database_dir / "floor_plans_seed.db"
    shutil.copy2(source_db, seed_db)
    normalized = normalize_seed_database(seed_db)

    runtime_dirs = {
        "uploads": settings.uploads_dir,
        "outputs": settings.outputs_dir,
        "debug_output": settings.debug_output_dir,
        "storage_objects": settings.object_storage_dir,
    }
    for target_name, source_dir in runtime_dirs.items():
        _copy_tree_contents(source_dir, files_dir / target_name)

    for source_file in (settings.feedback_file, settings.data_dir / "project_counter.json"):
        if source_file.exists():
            shutil.copy2(source_file, files_dir / source_file.name)

    print(f"Seed database: {seed_db}")
    print(f"Seed files: {files_dir}")
    print(f"Normalized path references: {normalized}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed-root",
        type=Path,
        default=DEFAULT_SEED_ROOT,
        help="Target seed root. Defaults to docker/seed.",
    )
    args = parser.parse_args()
    export_seed(args.seed_root.resolve())


if __name__ == "__main__":
    main()
