"""add last notified timestamp to live status

Revision ID: 0006
Revises: 0005
Create Date: 2026-02-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("live_status", sa.Column("last_notified_at", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("live_status", "last_notified_at")
