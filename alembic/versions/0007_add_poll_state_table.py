"""add poll state table

Revision ID: 0007
Revises: 0006
Create Date: 2026-02-01
"""

from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    op.create_table(
        "poll_state",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("poll_state")
