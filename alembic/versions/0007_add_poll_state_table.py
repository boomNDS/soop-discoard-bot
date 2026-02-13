"""add poll state table

Revision ID: 0007
Revises: 0006
Create Date: 2026-02-01
"""

from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "poll_state",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("poll_state")
