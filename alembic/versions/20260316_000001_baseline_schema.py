"""baseline schema"""

from __future__ import annotations

from alembic import op

from backend.modules.shared.infrastructure.persistence.models import Base


revision = "20260316_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    op.execute("CREATE INDEX IF NOT EXISTS ix_floor_plans_project_id ON floor_plans (project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_walls_floor_plan_id ON walls (floor_plan_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_doors_floor_plan_id ON doors (floor_plan_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_windows_floor_plan_id ON windows (floor_plan_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_rooms_floor_plan_id ON rooms (floor_plan_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fire_alarms_floor_plan_system ON fire_alarms (floor_plan_id, system_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_fire_alarms_zkspc_zone_id ON fire_alarms (zkspc_zone_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_zkspc_zones_floor_plan_id ON zkspc_zones (floor_plan_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_signal_instruments_floor_plan_system ON signal_instruments (floor_plan_id, system_type)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_cable_routes_floor_plan_system_instrument ON cable_routes (floor_plan_id, system_type, instrument_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_events_created_at ON audit_events (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_events_floor_plan_step ON audit_events (floor_plan_id, pipeline_step)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_audit_events_project_use_case ON audit_events (project_id, use_case)")


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)

