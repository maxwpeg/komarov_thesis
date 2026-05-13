"""add managed file metadata registry"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect


revision = "20260513_000001"
down_revision = "20260316_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(inspect(bind).get_table_names())
    if "managed_files" not in existing_tables:
        op.create_table(
            "managed_files",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("path", sa.String(length=500), nullable=False, unique=True),
            sa.Column("storage_root", sa.String(length=64), nullable=False, server_default="storage_objects"),
            sa.Column("content_type", sa.String(length=128), nullable=True),
            sa.Column("size_bytes", sa.Integer(), nullable=True),
            sa.Column("sha256", sa.String(length=64), nullable=True),
            sa.Column("project_id", sa.Integer(), nullable=True),
            sa.Column("floor_plan_id", sa.Integer(), nullable=True),
            sa.Column("equipment_id", sa.Integer(), nullable=True),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("last_seen_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS ix_managed_files_path ON managed_files (path)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_managed_files_project_id ON managed_files (project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_managed_files_floor_plan_id ON managed_files (floor_plan_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_managed_files_equipment_id ON managed_files (equipment_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_managed_files_created_by_user_id ON managed_files (created_by_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_managed_files_sha256 ON managed_files (sha256)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_managed_files_last_seen_at ON managed_files (last_seen_at)")


def downgrade() -> None:
    op.drop_table("managed_files")
