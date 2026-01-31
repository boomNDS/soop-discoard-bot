"""create guild_streamers table

Revision ID: 0001
Revises: 
Create Date: 2026-01-31
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if "guild_streamers" not in inspector.get_table_names():
        op.create_table(
            "guild_streamers",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("guild_id", sa.String, nullable=False),
            sa.Column("soop_channel_id", sa.String, nullable=False),
            sa.Column("notify_channel_id", sa.String, nullable=False),
            sa.Column("message_template", sa.Text, nullable=True),
            sa.Column("created_at", sa.String, nullable=False),
            sa.UniqueConstraint("guild_id", "soop_channel_id", name="uq_guild_streamer"),
        )
    else:
        columns = {col["name"] for col in inspector.get_columns("guild_streamers")}
        if "message_template" not in columns:
            op.add_column("guild_streamers", sa.Column("message_template", sa.Text))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "guild_streamers" in inspector.get_table_names():
        op.drop_table("guild_streamers")
