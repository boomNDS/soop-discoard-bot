"""add embed template fields to guild_settings

Revision ID: 0004
Revises: 0003
Create Date: 2026-02-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "guild_settings" in inspector.get_table_names():
        columns = {col["name"] for col in inspector.get_columns("guild_settings")}
        if "embed_title" not in columns:
            op.add_column("guild_settings", sa.Column("embed_title", sa.Text))
        if "embed_description" not in columns:
            op.add_column("guild_settings", sa.Column("embed_description", sa.Text))
        if "embed_color" not in columns:
            op.add_column("guild_settings", sa.Column("embed_color", sa.String))


def downgrade() -> None:
    # No-op for SQLite (dropping columns not supported without table rebuild).
    pass
