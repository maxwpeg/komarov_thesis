"""Database configuration and session management."""

from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import settings
from backend.modules.shared.infrastructure.persistence.models import Base


def create_db_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for the configured database."""
    url = database_url or settings.database_url
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True)


engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def configure_database(database_url: str) -> None:
    """Reconfigure the global engine/session factory, primarily for tests."""
    global engine, SessionLocal
    engine.dispose()
    engine = create_db_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db() -> None:
    """Initialize the current schema for fresh environments."""
    Base.metadata.create_all(bind=engine)
    _ensure_backward_compatible_columns()
    _ensure_performance_indexes()


def get_db() -> Generator[Session, None, None]:
    """Dependency for FastAPI to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def reset_db() -> None:
    """Drop all tables and recreate them."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    _ensure_backward_compatible_columns()
    _ensure_performance_indexes()


def _ensure_backward_compatible_columns() -> None:
    """
    Add new nullable columns for legacy databases that were created before schema updates.
    """
    with engine.begin() as connection:
        inspector = inspect(connection)
        table_names = set(inspector.get_table_names())
        if "dimensions" not in table_names:
            dimensions_columns = set()
        else:
            dimensions_columns = {column["name"] for column in inspector.get_columns("dimensions")}

        if "wall_id" not in dimensions_columns:
            connection.exec_driver_sql("ALTER TABLE dimensions ADD COLUMN wall_id INTEGER")
        if "room_id" not in dimensions_columns:
            connection.exec_driver_sql("ALTER TABLE dimensions ADD COLUMN room_id INTEGER")

        if "floor_plans" in table_names:
            floor_plan_columns = {column["name"] for column in inspector.get_columns("floor_plans")}
            if "pipeline_state" not in floor_plan_columns:
                connection.exec_driver_sql("ALTER TABLE floor_plans ADD COLUMN pipeline_state JSON")
            if "ceiling_height_mm" not in floor_plan_columns:
                connection.exec_driver_sql("ALTER TABLE floor_plans ADD COLUMN ceiling_height_mm FLOAT DEFAULT 3000")
            if "scale_source" not in floor_plan_columns:
                connection.exec_driver_sql("ALTER TABLE floor_plans ADD COLUMN scale_source VARCHAR(20) DEFAULT 'auto'")
            if "active_signal_system_type" not in floor_plan_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE floor_plans ADD COLUMN active_signal_system_type VARCHAR(32) DEFAULT 'non_addressable'"
                )
            connection.exec_driver_sql(
                """
                UPDATE floor_plans
                SET scale_source = 'auto'
                WHERE scale_source IS NULL OR scale_source = ''
                """
            )
            connection.exec_driver_sql(
                """
                UPDATE floor_plans
                SET active_signal_system_type = 'non_addressable'
                WHERE active_signal_system_type IS NULL OR active_signal_system_type = ''
                """
            )

        if "walls" in table_names:
            wall_columns = {column["name"] for column in inspector.get_columns("walls")}
            if "length_m" not in wall_columns:
                connection.exec_driver_sql("ALTER TABLE walls ADD COLUMN length_m FLOAT")
            if "length_source" not in wall_columns:
                connection.exec_driver_sql("ALTER TABLE walls ADD COLUMN length_source VARCHAR(20)")
            if "alignment" not in wall_columns:
                connection.exec_driver_sql("ALTER TABLE walls ADD COLUMN alignment VARCHAR(10) DEFAULT 'center'")
            connection.exec_driver_sql(
                """
                UPDATE walls
                SET alignment = 'center'
                WHERE alignment IS NULL OR alignment = ''
                """
            )

        if "doors" in table_names:
            door_columns = {column["name"] for column in inspector.get_columns("doors")}
            if "wall_id" not in door_columns:
                connection.exec_driver_sql("ALTER TABLE doors ADD COLUMN wall_id INTEGER")
            if "rotation_deg" not in door_columns:
                connection.exec_driver_sql("ALTER TABLE doors ADD COLUMN rotation_deg FLOAT DEFAULT 0")

        if "windows" in table_names:
            window_columns = {column["name"] for column in inspector.get_columns("windows")}
            if "wall_id" not in window_columns:
                connection.exec_driver_sql("ALTER TABLE windows ADD COLUMN wall_id INTEGER")
            if "rotation_deg" not in window_columns:
                connection.exec_driver_sql("ALTER TABLE windows ADD COLUMN rotation_deg FLOAT DEFAULT 0")

        if "rooms" in table_names:
            room_columns = {column["name"] for column in inspector.get_columns("rooms")}
            if "length_m" not in room_columns:
                connection.exec_driver_sql("ALTER TABLE rooms ADD COLUMN length_m FLOAT")
            if "width_m" not in room_columns:
                connection.exec_driver_sql("ALTER TABLE rooms ADD COLUMN width_m FLOAT")
            if "room_type" not in room_columns:
                connection.exec_driver_sql("ALTER TABLE rooms ADD COLUMN room_type VARCHAR(100)")

        if "fire_alarms" in table_names:
            fire_alarm_columns = {column["name"] for column in inspector.get_columns("fire_alarms")}
            if "room_id" not in fire_alarm_columns:
                connection.exec_driver_sql("ALTER TABLE fire_alarms ADD COLUMN room_id INTEGER")
            if "offset_left_m" not in fire_alarm_columns:
                connection.exec_driver_sql("ALTER TABLE fire_alarms ADD COLUMN offset_left_m FLOAT")
            if "offset_top_m" not in fire_alarm_columns:
                connection.exec_driver_sql("ALTER TABLE fire_alarms ADD COLUMN offset_top_m FLOAT")
            if "label_dx" not in fire_alarm_columns:
                connection.exec_driver_sql("ALTER TABLE fire_alarms ADD COLUMN label_dx FLOAT")
            if "label_dy" not in fire_alarm_columns:
                connection.exec_driver_sql("ALTER TABLE fire_alarms ADD COLUMN label_dy FLOAT")
            if "system_type" not in fire_alarm_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE fire_alarms ADD COLUMN system_type VARCHAR(32) DEFAULT 'non_addressable'"
                )
            if "zkspc_zone_id" not in fire_alarm_columns:
                connection.exec_driver_sql("ALTER TABLE fire_alarms ADD COLUMN zkspc_zone_id INTEGER")
            if "loop_kind" not in fire_alarm_columns:
                connection.exec_driver_sql("ALTER TABLE fire_alarms ADD COLUMN loop_kind VARCHAR(32)")
            if "loop_number" not in fire_alarm_columns:
                connection.exec_driver_sql("ALTER TABLE fire_alarms ADD COLUMN loop_number INTEGER")
            if "device_number" not in fire_alarm_columns:
                connection.exec_driver_sql("ALTER TABLE fire_alarms ADD COLUMN device_number INTEGER")
            connection.exec_driver_sql(
                """
                UPDATE fire_alarms
                SET system_type = 'non_addressable'
                WHERE system_type IS NULL OR system_type = ''
                """
            )

        if "signal_instruments" in table_names:
            signal_instrument_columns = {column["name"] for column in inspector.get_columns("signal_instruments")}
            if "label_dx" not in signal_instrument_columns:
                connection.exec_driver_sql("ALTER TABLE signal_instruments ADD COLUMN label_dx FLOAT")
            if "label_dy" not in signal_instrument_columns:
                connection.exec_driver_sql("ALTER TABLE signal_instruments ADD COLUMN label_dy FLOAT")

        if "cable_routes" in table_names:
            cable_route_columns = {column["name"] for column in inspector.get_columns("cable_routes")}
            if "zc_label_dx" not in cable_route_columns:
                connection.exec_driver_sql("ALTER TABLE cable_routes ADD COLUMN zc_label_dx FLOAT")
            if "zc_label_dy" not in cable_route_columns:
                connection.exec_driver_sql("ALTER TABLE cable_routes ADD COLUMN zc_label_dy FLOAT")

        if "projects" in table_names:
            connection.exec_driver_sql(
                """
                UPDATE projects
                SET code = REPLACE(code, 'RP-ZK-', 'РП-ЗК-')
                WHERE code LIKE 'RP-ZK-%'
                """
            )

        if "project_year_counters" in table_names and "projects" in table_names:
            connection.exec_driver_sql(
                """
                INSERT INTO project_year_counters (year, last_number, updated_at)
                SELECT year, MAX(number), CURRENT_TIMESTAMP
                FROM projects
                GROUP BY year
                ON CONFLICT(year) DO UPDATE SET
                    last_number = MAX(project_year_counters.last_number, excluded.last_number),
                    updated_at = CURRENT_TIMESTAMP
                """
            )


def _ensure_performance_indexes() -> None:
    """Create frequently used indexes in a compatibility-safe way."""
    statements = (
        "CREATE INDEX IF NOT EXISTS ix_floor_plans_project_id ON floor_plans (project_id)",
        "CREATE INDEX IF NOT EXISTS ix_walls_floor_plan_id ON walls (floor_plan_id)",
        "CREATE INDEX IF NOT EXISTS ix_doors_floor_plan_id ON doors (floor_plan_id)",
        "CREATE INDEX IF NOT EXISTS ix_windows_floor_plan_id ON windows (floor_plan_id)",
        "CREATE INDEX IF NOT EXISTS ix_rooms_floor_plan_id ON rooms (floor_plan_id)",
        "CREATE INDEX IF NOT EXISTS ix_fire_alarms_floor_plan_system ON fire_alarms (floor_plan_id, system_type)",
        "CREATE INDEX IF NOT EXISTS ix_fire_alarms_zkspc_zone_id ON fire_alarms (zkspc_zone_id)",
        "CREATE INDEX IF NOT EXISTS ix_zkspc_zones_floor_plan_id ON zkspc_zones (floor_plan_id)",
        "CREATE INDEX IF NOT EXISTS ix_signal_instruments_floor_plan_system ON signal_instruments (floor_plan_id, system_type)",
        "CREATE INDEX IF NOT EXISTS ix_cable_routes_floor_plan_system_instrument ON cable_routes (floor_plan_id, system_type, instrument_id)",
        "CREATE INDEX IF NOT EXISTS ix_recognition_feedback_floor_plan ON recognition_feedback_samples (floor_plan_id)",
        "CREATE INDEX IF NOT EXISTS ix_recognition_feedback_recognition ON recognition_feedback_samples (recognition_id)",
        "CREATE INDEX IF NOT EXISTS ix_audit_events_created_at ON audit_events (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_audit_events_floor_plan_step ON audit_events (floor_plan_id, pipeline_step)",
        "CREATE INDEX IF NOT EXISTS ix_audit_events_project_use_case ON audit_events (project_id, use_case)",
    )
    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)
