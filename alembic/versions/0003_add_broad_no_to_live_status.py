"""add broad_no to live_status

Revision ID: 0003
Revises: 0002
Create Date: 2026-01-31
"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "live_status" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("live_status")}
        if "broad_no" not in columns:
            op.add_column("live_status", sa.Column("broad_no", sa.String))


def downgrade() -> None:
    # No-op for SQLite (dropping columns not supported without table rebuild).
    pass
