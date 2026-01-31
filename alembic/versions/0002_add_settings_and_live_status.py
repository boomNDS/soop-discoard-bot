"""add guild settings and live status

Revision ID: 0002
Revises: 0001
Create Date: 2026-01-31
"""

from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "guild_settings" not in inspector.get_table_names():
        op.create_table(
            "guild_settings",
            sa.Column("guild_id", sa.String, primary_key=True),
            sa.Column("default_notify_channel_id", sa.String, nullable=True),
        )

    if "live_status" not in inspector.get_table_names():
        op.create_table(
            "live_status",
            sa.Column("guild_id", sa.String, nullable=False),
            sa.Column("soop_channel_id", sa.String, nullable=False),
            sa.Column("is_live", sa.Integer, nullable=False),
            sa.Column("updated_at", sa.String, nullable=False),
            sa.PrimaryKeyConstraint("guild_id", "soop_channel_id", name="pk_live_status"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "live_status" in inspector.get_table_names():
        op.drop_table("live_status")
    if "guild_settings" in inspector.get_table_names():
        op.drop_table("guild_settings")
