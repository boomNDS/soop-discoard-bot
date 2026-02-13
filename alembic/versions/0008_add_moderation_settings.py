"""add moderation settings to guild_settings

Revision ID: 0008
Revises: 0007
Create Date: 2026-02-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("guild_settings", sa.Column("admin_role_id", sa.String(), nullable=True))
    op.add_column("guild_settings", sa.Column("audit_channel_id", sa.String(), nullable=True))
    op.add_column("guild_settings", sa.Column("rate_limit_per_min", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("guild_settings", "rate_limit_per_min")
    op.drop_column("guild_settings", "audit_channel_id")
    op.drop_column("guild_settings", "admin_role_id")
