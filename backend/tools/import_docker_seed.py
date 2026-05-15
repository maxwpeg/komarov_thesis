"""Import Docker first-run seed data from SQLite into the configured database."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import sys
from typing import Any
from urllib.parse import quote

from sqlalchemy import DateTime, JSON, Boolean, func, select, text


BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from backend.database import engine  # noqa: E402
from backend.modules.shared.infrastructure.persistence.models import Base  # noqa: E402


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _sqlite_tables(connection: sqlite3.Connection) -> set[str]:
    rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {str(row[0]) for row in rows}


def _database_has_rows() -> bool:
    with engine.begin() as connection:
        Base.metadata.create_all(bind=connection)
        for table in Base.metadata.sorted_tables:
            count = connection.execute(select(func.count()).select_from(table)).scalar_one()
            if int(count) > 0:
                return True
    return False


def _parse_datetime(value: str) -> datetime | str:
    raw = value.strip()
    if not raw:
        return value
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return value


def _coerce_value(column, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(column.type, JSON):
        if isinstance(value, str):
            if not value.strip():
                return None
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value
    if isinstance(column.type, DateTime) and isinstance(value, str):
        return _parse_datetime(value)
    if isinstance(column.type, Boolean):
        return bool(value)
    return value


def _read_seed_rows(
    sqlite_connection: sqlite3.Connection,
    table_name: str,
    target_columns: dict[str, Any],
) -> list[dict[str, Any]]:
    sqlite_connection.row_factory = sqlite3.Row
    rows = sqlite_connection.execute(f"SELECT * FROM {_quote_identifier(table_name)}").fetchall()
    payload: list[dict[str, Any]] = []
    for row in rows:
        item: dict[str, Any] = {}
        for column_name, column in target_columns.items():
            if column_name in row.keys():
                item[column_name] = _coerce_value(column, row[column_name])
        payload.append(item)
    return payload


def _reset_postgres_sequences(connection) -> None:
    if engine.dialect.name != "postgresql":
        return
    for table in Base.metadata.sorted_tables:
        primary_keys = list(table.primary_key.columns)
        if len(primary_keys) != 1:
            continue
        column = primary_keys[0]
        sequence_name = connection.execute(
            text("SELECT pg_get_serial_sequence(:table_name, :column_name)"),
            {"table_name": table.name, "column_name": column.name},
        ).scalar()
        if not sequence_name:
            continue
        max_value = connection.execute(select(func.max(column))).scalar()
        if max_value is None:
            connection.execute(
                text("SELECT setval(CAST(:sequence_name AS regclass), 1, false)"),
                {"sequence_name": sequence_name},
            )
        else:
            connection.execute(
                text("SELECT setval(CAST(:sequence_name AS regclass), :sequence_value, true)"),
                {"sequence_name": sequence_name, "sequence_value": int(max_value)},
            )


def import_seed(seed_db: Path, *, force: bool = False) -> None:
    if not seed_db.exists():
        raise FileNotFoundError(f"Seed database was not found: {seed_db}")

    if force:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
    elif _database_has_rows():
        print("Target database already contains rows; seed import skipped.")
        return
    else:
        Base.metadata.create_all(bind=engine)

    seed_uri = f"file:{quote(seed_db.as_posix())}?mode=ro&immutable=1"
    sqlite_connection = sqlite3.connect(seed_uri, uri=True)
    try:
        sqlite_tables = _sqlite_tables(sqlite_connection)
        imported_tables = 0
        imported_rows = 0
        with engine.begin() as connection:
            for table in Base.metadata.sorted_tables:
                if table.name not in sqlite_tables:
                    continue
                target_columns = {column.name: column for column in table.columns}
                rows = _read_seed_rows(sqlite_connection, table.name, target_columns)
                if not rows:
                    continue
                connection.execute(table.insert(), rows)
                imported_tables += 1
                imported_rows += len(rows)
            _reset_postgres_sequences(connection)
        print(f"Imported seed tables: {imported_tables}")
        print(f"Imported seed rows: {imported_rows}")
    finally:
        sqlite_connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-db", type=Path, required=True, help="Path to floor_plans_seed.db")
    parser.add_argument("--force", action="store_true", help="Drop and re-import the configured database")
    args = parser.parse_args()
    import_seed(args.seed_db, force=args.force)


if __name__ == "__main__":
    main()
