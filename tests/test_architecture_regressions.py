"""Regression tests for architectural seams introduced during decomposition."""

from __future__ import annotations

import sqlite3

from sqlalchemy import event

import backend.database as database
from backend.composition import build_elements_geometry_use_cases, build_floor_plan_use_cases
from backend.models import AuditEvent, FloorPlan, Project, Room, Wall, ZkspcZone, ZkspcZoneRoom
from backend.schemas import WallCreate
from backend.services.storage_service import StorageService


def test_init_db_backfills_missing_floor_plan_scale_source_column(tmp_path):
    database_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(database_path)
    try:
        connection.executescript(
            """
            CREATE TABLE projects (
                id INTEGER PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                project_type VARCHAR(50),
                number INTEGER NOT NULL,
                year INTEGER NOT NULL,
                code VARCHAR(100) NOT NULL UNIQUE,
                contractor VARCHAR(255) NOT NULL,
                engineer VARCHAR(255) NOT NULL,
                cpe VARCHAR(255) NOT NULL,
                checker VARCHAR(255) NOT NULL,
                facility VARCHAR(255) NOT NULL,
                facility_address TEXT,
                project_description TEXT,
                stage VARCHAR(50),
                number_of_floors INTEGER,
                created_at DATETIME,
                updated_at DATETIME
            );
            CREATE TABLE floor_plans (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                floor_number INTEGER NOT NULL,
                name VARCHAR(255),
                original_image_path VARCHAR(500),
                processed_image_path VARCHAR(500),
                image_width INTEGER,
                image_height INTEGER,
                scale_factor FLOAT,
                created_at DATETIME,
                updated_at DATETIME,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );
            INSERT INTO projects (
                id, name, project_type, number, year, code, contractor, engineer, cpe, checker, facility
            ) VALUES (
                1, 'Legacy Project', 'PS', 1, 2026, 'PRJ-LEGACY', 'Contractor', 'Engineer', 'CPE', 'Checker', 'Facility'
            );
            INSERT INTO floor_plans (id, project_id, floor_number, name, scale_factor)
            VALUES (1, 1, 1, 'Floor 1', 12.5);
            """
        )
        connection.commit()
    finally:
        connection.close()

    database.configure_database(f"sqlite:///{database_path.as_posix()}")
    database.init_db()

    connection = sqlite3.connect(database_path)
    try:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(floor_plans)")}
        scale_source = connection.execute("SELECT scale_source FROM floor_plans WHERE id = 1").fetchone()
    finally:
        connection.close()

    assert "scale_source" in columns
    assert scale_source == ("auto",)


def test_elements_use_case_persists_audit_event(isolated_database):
    db = database.SessionLocal()
    try:
        project = Project(
            name="Project",
            project_type="PS",
            number=1,
            year=2026,
            code="PRJ-1",
            contractor="Contractor",
            engineer="Engineer",
            cpe="CPE",
            checker="Checker",
            facility="Facility",
            facility_address="Address",
            project_description="Description",
            stage="R",
            number_of_floors=1,
        )
        db.add(project)
        db.flush()
        floor_plan = FloorPlan(
            project_id=project.id,
            floor_number=1,
            name="Floor 1",
            scale_factor=10.0,
        )
        db.add(floor_plan)
        db.commit()

        use_cases = build_elements_geometry_use_cases(db)
        wall = use_cases.create_wall(
            WallCreate(
                floor_plan_id=floor_plan.id,
                x1=0,
                y1=0,
                x2=100,
                y2=0,
                thickness=200,
                is_load_bearing=False,
                material="manual",
                length_m=1.0,
                length_source="manual",
            )
        )

        event_row = db.query(AuditEvent).filter(AuditEvent.event_name == "wall_created").one()
        assert event_row.floor_plan_id == floor_plan.id
        assert event_row.payload == {"wall_id": wall.to_dict()["id"]}
    finally:
        db.close()


def test_floor_plan_read_query_count_stays_bounded(isolated_database):
    db = database.SessionLocal()
    try:
        project = Project(
            name="Project",
            project_type="PS",
            number=2,
            year=2026,
            code="PRJ-2",
            contractor="Contractor",
            engineer="Engineer",
            cpe="CPE",
            checker="Checker",
            facility="Facility",
            facility_address="Address",
            project_description="Description",
            stage="R",
            number_of_floors=1,
        )
        db.add(project)
        db.flush()
        floor_plan = FloorPlan(
            project_id=project.id,
            floor_number=1,
            name="Floor 1",
            scale_factor=10.0,
        )
        db.add(floor_plan)
        db.flush()
        room = Room(
            floor_plan_id=floor_plan.id,
            name="Room A",
            room_type="office",
            boundary_points=[[0, 0], [100, 0], [100, 100], [0, 100]],
        )
        room.calculate_center()
        room.calculate_length_width(10.0)
        room.calculate_area(10.0)
        room.calculate_perimeter(10.0)
        db.add(room)
        db.add(
            Wall(
                floor_plan_id=floor_plan.id,
                x1=0,
                y1=0,
                x2=100,
                y2=0,
                thickness=200,
                is_load_bearing=False,
                material="manual",
                length_m=1.0,
                length_source="manual",
            )
        )
        db.flush()
        zone = ZkspcZone(
            floor_plan_id=floor_plan.id,
            zone_number=1,
            name="Zone 1",
            area_sqm=10.0,
            room_count=1,
        )
        db.add(zone)
        db.flush()
        db.add(ZkspcZoneRoom(zone_id=zone.id, room_id=room.id))
        db.commit()

        use_cases = build_floor_plan_use_cases(db, StorageService())
        engine = db.get_bind()
        statements: list[str] = []

        def _count_queries(_conn, _cursor, statement, _parameters, _context, _executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", _count_queries)
        try:
            result = use_cases.get_floor_plan(floor_plan.id, include_elements=True)
        finally:
            event.remove(engine, "before_cursor_execute", _count_queries)

        assert result.id == floor_plan.id
        assert len(statements) <= 13
    finally:
        db.close()
