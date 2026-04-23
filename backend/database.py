"""Database configuration and session management."""

from __future__ import annotations

import json
from typing import Generator

from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.config import settings
from backend.modules.equipment.domain.specs import coerce_current_specs
from backend.modules.shared.infrastructure.persistence.models import Base


def create_db_engine(database_url: str | None = None) -> Engine:
    """Create a SQLAlchemy engine for the configured database."""
    url = database_url or settings.database_url
    if url.startswith("sqlite"):
        return create_engine(url, connect_args={"check_same_thread": False})
    return create_engine(url, pool_pre_ping=True)


engine = create_db_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)


def configure_database(database_url: str) -> None:
    """Reconfigure the global engine/session factory, primarily for tests."""
    global engine, SessionLocal
    engine.dispose()
    engine = create_db_engine(database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)


def init_db() -> None:
    """Initialize the current schema for fresh environments."""
    Base.metadata.create_all(bind=engine)
    _ensure_backward_compatible_columns()
    _ensure_performance_indexes()
    from backend.auth import bootstrap_first_developer

    session = SessionLocal()
    try:
        bootstrap_first_developer(session)
    finally:
        session.close()


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
        if "projects" in table_names:
            project_columns = {column["name"] for column in inspector.get_columns("projects")}
            if "facility_genitive" not in project_columns:
                connection.exec_driver_sql("ALTER TABLE projects ADD COLUMN facility_genitive VARCHAR(255)")
            if "facility_instrumental" not in project_columns:
                connection.exec_driver_sql("ALTER TABLE projects ADD COLUMN facility_instrumental VARCHAR(255)")
            if "owner_user_id" not in project_columns:
                connection.exec_driver_sql("ALTER TABLE projects ADD COLUMN owner_user_id INTEGER")
            if "equipment_specification_overrides" not in project_columns:
                connection.exec_driver_sql("ALTER TABLE projects ADD COLUMN equipment_specification_overrides JSON")
            if "general_data_overrides" not in project_columns:
                connection.exec_driver_sql("ALTER TABLE projects ADD COLUMN general_data_overrides JSON")
            if "general_instructions_overrides" not in project_columns:
                connection.exec_driver_sql("ALTER TABLE projects ADD COLUMN general_instructions_overrides JSON")
            if "power_consumption_overrides" not in project_columns:
                connection.exec_driver_sql("ALTER TABLE projects ADD COLUMN power_consumption_overrides JSON")
            if "additional_info_text" not in project_columns:
                connection.exec_driver_sql("ALTER TABLE projects ADD COLUMN additional_info_text TEXT")
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
            if "is_evacuation_exit" not in door_columns:
                connection.exec_driver_sql("ALTER TABLE doors ADD COLUMN is_evacuation_exit BOOLEAN DEFAULT 0")

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
            if "max_occupancy" not in room_columns:
                connection.exec_driver_sql("ALTER TABLE rooms ADD COLUMN max_occupancy INTEGER")

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
            if "equipment_id" not in signal_instrument_columns:
                connection.exec_driver_sql("ALTER TABLE signal_instruments ADD COLUMN equipment_id INTEGER")

        if "cable_routes" in table_names:
            cable_route_columns = {column["name"] for column in inspector.get_columns("cable_routes")}
            if "zc_label_dx" not in cable_route_columns:
                connection.exec_driver_sql("ALTER TABLE cable_routes ADD COLUMN zc_label_dx FLOAT")
            if "zc_label_dy" not in cable_route_columns:
                connection.exec_driver_sql("ALTER TABLE cable_routes ADD COLUMN zc_label_dy FLOAT")
            if "subsystem_type" not in cable_route_columns:
                connection.exec_driver_sql("ALTER TABLE cable_routes ADD COLUMN subsystem_type VARCHAR(16) DEFAULT 'sps'")
            connection.exec_driver_sql(
                """
                UPDATE cable_routes
                SET subsystem_type = 'sps'
                WHERE subsystem_type IS NULL OR subsystem_type = ''
                """
            )

        if "soue_devices" in table_names:
            soue_columns = {column["name"] for column in inspector.get_columns("soue_devices")}
            if "sound_pressure_db" not in soue_columns:
                connection.exec_driver_sql("ALTER TABLE soue_devices ADD COLUMN sound_pressure_db FLOAT")
            if "label_dx" not in soue_columns:
                connection.exec_driver_sql("ALTER TABLE soue_devices ADD COLUMN label_dx FLOAT")
            if "label_dy" not in soue_columns:
                connection.exec_driver_sql("ALTER TABLE soue_devices ADD COLUMN label_dy FLOAT")
            if "equipment_id" not in soue_columns:
                connection.exec_driver_sql("ALTER TABLE soue_devices ADD COLUMN equipment_id INTEGER")

        if "equipment_items" in table_names:
            equipment_columns = {column["name"] for column in inspector.get_columns("equipment_items")}
            if "manufacturer" not in equipment_columns:
                connection.exec_driver_sql("ALTER TABLE equipment_items ADD COLUMN manufacturer VARCHAR(255)")
            if "service_life_years" not in equipment_columns:
                connection.exec_driver_sql("ALTER TABLE equipment_items ADD COLUMN service_life_years INTEGER")
            if "notes" not in equipment_columns:
                connection.exec_driver_sql("ALTER TABLE equipment_items ADD COLUMN notes TEXT")
            if "specs" not in equipment_columns:
                connection.exec_driver_sql("ALTER TABLE equipment_items ADD COLUMN specs JSON")
            if "label_pdf_path" not in equipment_columns:
                connection.exec_driver_sql("ALTER TABLE equipment_items ADD COLUMN label_pdf_path VARCHAR(500)")
            if "manual_pdf_path" not in equipment_columns:
                connection.exec_driver_sql("ALTER TABLE equipment_items ADD COLUMN manual_pdf_path VARCHAR(500)")
            if "price" in equipment_columns:
                connection.exec_driver_sql(
                    """
                    UPDATE equipment_items
                    SET price = ROUND(price, 2)
                    WHERE price IS NOT NULL
                    """
                )
            rows = connection.exec_driver_sql(
                """
                SELECT id, category, specs, smoke_addressing, standby_current_ma, alarm_current_ma
                FROM equipment_items
                """
            ).mappings()
            for row in rows:
                normalized_specs = coerce_current_specs(
                    row["category"],
                    row["specs"],
                    smoke_addressing=row["smoke_addressing"],
                    standby_current_ma=row["standby_current_ma"],
                    alarm_current_ma=row["alarm_current_ma"],
                )
                connection.exec_driver_sql(
                    "UPDATE equipment_items SET specs = ? WHERE id = ?",
                    (json.dumps(normalized_specs, ensure_ascii=False), row["id"]),
                )

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

        if "recognition_feedback_examples" in table_names:
            feedback_columns = {column["name"] for column in inspector.get_columns("recognition_feedback_examples")}
            if "curation_status" not in feedback_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE recognition_feedback_examples ADD COLUMN curation_status VARCHAR(32) DEFAULT 'approved'"
                )
            if "curated_at" not in feedback_columns:
                connection.exec_driver_sql("ALTER TABLE recognition_feedback_examples ADD COLUMN curated_at DATETIME")
            connection.exec_driver_sql(
                """
                UPDATE recognition_feedback_examples
                SET curation_status = 'approved'
                WHERE curation_status IS NULL OR curation_status = ''
                """
            )

        if "recognition_training_batch_examples" in table_names and "recognition_feedback_examples" in table_names:
            connection.exec_driver_sql(
                """
                INSERT INTO recognition_training_batch_examples (training_batch_id, feedback_example_id, included_at)
                SELECT feedback.training_batch_id,
                       feedback.id,
                       COALESCE(feedback.batched_at, feedback.exported_at, feedback.submitted_at, CURRENT_TIMESTAMP)
                FROM recognition_feedback_examples AS feedback
                WHERE feedback.training_batch_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1
                    FROM recognition_training_batch_examples AS links
                    WHERE links.training_batch_id = feedback.training_batch_id
                      AND links.feedback_example_id = feedback.id
                  )
                """
            )

        if "fire_alarms" in table_names:
            fire_alarm_columns = {column["name"] for column in inspector.get_columns("fire_alarms")}
            if "equipment_id" not in fire_alarm_columns:
                connection.exec_driver_sql("ALTER TABLE fire_alarms ADD COLUMN equipment_id INTEGER")

        if "project_equipment_links" in table_names and "project_equipment_selections" in table_names:
            connection.exec_driver_sql(
                """
                INSERT INTO project_equipment_links (project_id, equipment_id, created_at, updated_at)
                SELECT DISTINCT selections.project_id,
                       selections.equipment_id,
                       CURRENT_TIMESTAMP,
                       CURRENT_TIMESTAMP
                FROM project_equipment_selections AS selections
                WHERE selections.equipment_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1
                    FROM project_equipment_links AS links
                    WHERE links.project_id = selections.project_id
                      AND links.equipment_id = selections.equipment_id
                  )
                """
            )

        if "fire_alarms" in table_names and "project_equipment_selections" in table_names:
            connection.exec_driver_sql(
                """
                UPDATE fire_alarms
                SET equipment_id = (
                    SELECT selections.equipment_id
                    FROM floor_plans AS plans
                    JOIN project_equipment_selections AS selections
                      ON selections.project_id = plans.project_id
                     AND selections.role_key = CASE fire_alarms.device_type
                         WHEN 'linear_detector' THEN 'sps_linear_detector'
                         WHEN 'smoke_detector' THEN 'sps_smoke_detector'
                         WHEN 'heat_detector' THEN 'sps_heat_detector'
                         WHEN 'manual_call_point' THEN 'sps_manual_call_point'
                         ELSE NULL
                     END
                    WHERE plans.id = fire_alarms.floor_plan_id
                    LIMIT 1
                )
                WHERE fire_alarms.equipment_id IS NULL
                """
            )

        if "soue_devices" in table_names and "project_equipment_selections" in table_names:
            connection.exec_driver_sql(
                """
                UPDATE soue_devices
                SET equipment_id = (
                    SELECT selections.equipment_id
                    FROM floor_plans AS plans
                    JOIN project_equipment_selections AS selections
                      ON selections.project_id = plans.project_id
                     AND selections.role_key = CASE soue_devices.device_type
                         WHEN 'siren' THEN 'soue_siren'
                         WHEN 'exit_sign' THEN 'soue_exit_sign'
                         WHEN 'speech_device' THEN 'soue_speech_device'
                         ELSE NULL
                     END
                    WHERE plans.id = soue_devices.floor_plan_id
                    LIMIT 1
                )
                WHERE soue_devices.equipment_id IS NULL
                """
            )

        if "signal_instruments" in table_names and "project_equipment_selections" in table_names:
            connection.exec_driver_sql(
                """
                UPDATE signal_instruments
                SET equipment_id = (
                    SELECT CASE
                        WHEN instrument_selection.equipment_id IS NOT NULL
                             AND (
                                 keyboard_selection.equipment_id IS NULL
                                 OR keyboard_selection.equipment_id = instrument_selection.equipment_id
                             )
                            THEN instrument_selection.equipment_id
                        WHEN keyboard_selection.equipment_id IS NOT NULL
                             AND instrument_selection.equipment_id IS NULL
                            THEN keyboard_selection.equipment_id
                        ELSE NULL
                    END
                    FROM floor_plans AS plans
                    LEFT JOIN project_equipment_selections AS instrument_selection
                      ON instrument_selection.project_id = plans.project_id
                     AND instrument_selection.role_key = 'common_instrument'
                    LEFT JOIN project_equipment_selections AS keyboard_selection
                      ON keyboard_selection.project_id = plans.project_id
                     AND keyboard_selection.role_key = 'common_keyboard'
                    WHERE plans.id = signal_instruments.floor_plan_id
                    LIMIT 1
                )
                WHERE signal_instruments.equipment_id IS NULL
                """
            )


def _ensure_performance_indexes() -> None:
    """Create frequently used indexes in a compatibility-safe way."""
    statements = (
        "CREATE INDEX IF NOT EXISTS ix_floor_plans_project_id ON floor_plans (project_id)",
        "CREATE INDEX IF NOT EXISTS ix_projects_owner_user_id ON projects (owner_user_id)",
        "CREATE INDEX IF NOT EXISTS ix_walls_floor_plan_id ON walls (floor_plan_id)",
        "CREATE INDEX IF NOT EXISTS ix_doors_floor_plan_id ON doors (floor_plan_id)",
        "CREATE INDEX IF NOT EXISTS ix_windows_floor_plan_id ON windows (floor_plan_id)",
        "CREATE INDEX IF NOT EXISTS ix_rooms_floor_plan_id ON rooms (floor_plan_id)",
        "CREATE INDEX IF NOT EXISTS ix_fire_alarms_floor_plan_system ON fire_alarms (floor_plan_id, system_type)",
        "CREATE INDEX IF NOT EXISTS ix_fire_alarms_zkspc_zone_id ON fire_alarms (zkspc_zone_id)",
        "CREATE INDEX IF NOT EXISTS ix_soue_devices_floor_plan_system ON soue_devices (floor_plan_id, system_type)",
        "CREATE INDEX IF NOT EXISTS ix_zkspc_zones_floor_plan_id ON zkspc_zones (floor_plan_id)",
        "CREATE INDEX IF NOT EXISTS ix_signal_instruments_floor_plan_system ON signal_instruments (floor_plan_id, system_type)",
        "CREATE INDEX IF NOT EXISTS ix_signal_instruments_equipment_id ON signal_instruments (equipment_id)",
        "CREATE INDEX IF NOT EXISTS ix_cable_routes_floor_plan_system_instrument ON cable_routes (floor_plan_id, system_type, instrument_id)",
        "CREATE INDEX IF NOT EXISTS ix_cable_routes_floor_plan_system_subsystem ON cable_routes (floor_plan_id, system_type, subsystem_type)",
        "CREATE INDEX IF NOT EXISTS ix_recognition_feedback_floor_plan ON recognition_feedback_samples (floor_plan_id)",
        "CREATE INDEX IF NOT EXISTS ix_recognition_feedback_recognition ON recognition_feedback_samples (recognition_id)",
        "CREATE INDEX IF NOT EXISTS ix_pipeline_detection_snapshot_lookup ON pipeline_detection_snapshots (floor_plan_id, step, step_revision)",
        "CREATE INDEX IF NOT EXISTS ix_feedback_example_step_status ON recognition_feedback_examples (step, status, submitted_at)",
        "CREATE INDEX IF NOT EXISTS ix_feedback_example_step_curation ON recognition_feedback_examples (step, curation_status, submitted_at)",
        "CREATE INDEX IF NOT EXISTS ix_feedback_example_floor_step_revision ON recognition_feedback_examples (floor_plan_id, step, step_revision)",
        "CREATE INDEX IF NOT EXISTS ix_training_batch_step_exported ON recognition_training_batches (step, exported_at)",
        "CREATE INDEX IF NOT EXISTS ix_training_batch_example_lookup ON recognition_training_batch_examples (training_batch_id, feedback_example_id)",
        "CREATE INDEX IF NOT EXISTS ix_training_run_status_requested ON recognition_training_runs (status, requested_at)",
        "CREATE INDEX IF NOT EXISTS ix_training_run_step_finished ON recognition_training_runs (step, finished_at)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_active_model_step_unique ON recognition_active_models (step)",
        "CREATE INDEX IF NOT EXISTS ix_active_model_run_lookup ON recognition_active_models (training_run_id)",
        "CREATE INDEX IF NOT EXISTS ix_audit_events_created_at ON audit_events (created_at)",
        "CREATE INDEX IF NOT EXISTS ix_audit_events_floor_plan_step ON audit_events (floor_plan_id, pipeline_step)",
        "CREATE INDEX IF NOT EXISTS ix_audit_events_project_use_case ON audit_events (project_id, use_case)",
        "CREATE INDEX IF NOT EXISTS ix_equipment_items_category ON equipment_items (category)",
        "CREATE INDEX IF NOT EXISTS ix_project_equipment_selections_project_role ON project_equipment_selections (project_id, role_key)",
        "CREATE INDEX IF NOT EXISTS ix_project_equipment_selections_equipment_id ON project_equipment_selections (equipment_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_project_equipment_links_project_equipment ON project_equipment_links (project_id, equipment_id)",
        "CREATE INDEX IF NOT EXISTS ix_project_equipment_links_equipment_id ON project_equipment_links (equipment_id)",
        "CREATE INDEX IF NOT EXISTS ix_equipment_compatibility_links_equipment_id ON equipment_compatibility_links (equipment_id)",
        "CREATE INDEX IF NOT EXISTS ix_equipment_compatibility_links_compatible_id ON equipment_compatibility_links (compatible_equipment_id)",
        "CREATE INDEX IF NOT EXISTS ix_fire_alarms_equipment_id ON fire_alarms (equipment_id)",
        "CREATE INDEX IF NOT EXISTS ix_soue_devices_equipment_id ON soue_devices (equipment_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_username ON users (username)",
        "CREATE INDEX IF NOT EXISTS ix_users_role_active ON users (role, is_active)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_auth_sessions_token_hash ON auth_sessions (token_hash)",
        "CREATE INDEX IF NOT EXISTS ix_auth_sessions_user_id ON auth_sessions (user_id)",
        "CREATE INDEX IF NOT EXISTS ix_auth_sessions_expires_at ON auth_sessions (expires_at)",
    )
    with engine.begin() as connection:
        for statement in statements:
            connection.exec_driver_sql(statement)
