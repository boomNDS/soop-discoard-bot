"""add mention settings

Revision ID: 0005
Revises: 0004
Create Date: 2026-02-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "guild_settings" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("guild_settings")}
        if "mention_type" not in columns:
            op.add_column("guild_settings", sa.Column("mention_type", sa.String))
        if "mention_value" not in columns:
            op.add_column("guild_settings", sa.Column("mention_value", sa.String))


def downgrade() -> None:
    # No-op for SQLite (dropping columns not supported without table rebuild).
    pass
