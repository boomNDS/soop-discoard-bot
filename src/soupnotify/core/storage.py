from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    delete,
    select,
    text,
    update,
)


@dataclass
class StorageTables:
    guild_streamers: Table
    guild_settings: Table
    live_status: Table


class Storage:
    def __init__(self, database_url: str) -> None:
        connect_args = {}
        if database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        self._engine = create_engine(database_url, future=True, connect_args=connect_args)
        self._tables = self._define_tables()
        self._ensure_schema()

    def _define_tables(self) -> StorageTables:
        metadata = MetaData()
        guild_streamers = Table(
            "guild_streamers",
            metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            Column("guild_id", String, nullable=False),
            Column("soop_channel_id", String, nullable=False),
            Column("notify_channel_id", String, nullable=False),
            Column("message_template", Text, nullable=True),
            Column("created_at", String, nullable=False),
            UniqueConstraint("guild_id", "soop_channel_id", name="uq_guild_streamer"),
        )
        guild_settings = Table(
            "guild_settings",
            metadata,
            Column("guild_id", String, primary_key=True),
            Column("default_notify_channel_id", String, nullable=True),
            Column("embed_title", Text, nullable=True),
            Column("embed_description", Text, nullable=True),
            Column("embed_color", String, nullable=True),
            Column("mention_type", String, nullable=True),
            Column("mention_value", String, nullable=True),
        )
        live_status = Table(
            "live_status",
            metadata,
            Column("guild_id", String, primary_key=True),
            Column("soop_channel_id", String, primary_key=True),
            Column("is_live", Integer, nullable=False),
            Column("broad_no", String, nullable=True),
            Column("updated_at", String, nullable=False),
        )
        self._metadata = metadata
        return StorageTables(guild_streamers=guild_streamers, guild_settings=guild_settings, live_status=live_status)

    def _ensure_schema(self) -> None:
        if not self._schema_exists():
            raise RuntimeError(
                "Database schema is missing. Run `alembic upgrade head` before starting the app."
            )
        self._migrate_legacy_links()

    def _schema_exists(self) -> bool:
        with self._engine.begin() as conn:
            result = conn.execute(
                text(
                    "SELECT table_name FROM information_schema.tables WHERE table_name='guild_streamers'"
                )
                if self._engine.dialect.name != "sqlite"
                else text(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='guild_streamers'"
                )
            ).fetchone()
        return result is not None

    def _migrate_legacy_links(self) -> None:
        # One-time migration for older single-link schema (sqlite only).
        if self._engine.dialect.name != "sqlite":
            return
        with self._engine.begin() as conn:
            result = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name='guild_links'")
            ).fetchone()
            if not result:
                return
            rows = conn.execute(
                text(
                    "SELECT guild_id, soop_channel_id, notify_channel_id, created_at FROM guild_links"
                )
            ).fetchall()
            for row in rows:
                conn.execute(
                    text(
                        """
                        INSERT OR IGNORE INTO guild_streamers
                        (guild_id, soop_channel_id, notify_channel_id, message_template, created_at)
                        VALUES (:guild_id, :soop_channel_id, :notify_channel_id, :message_template, :created_at)
                        """
                    ),
                    {
                        "guild_id": row[0],
                        "soop_channel_id": row[1],
                        "notify_channel_id": row[2],
                        "message_template": None,
                        "created_at": row[3],
                    },
                )
            conn.execute(text("DROP TABLE guild_links"))

    def add_link(
        self,
        guild_id: str,
        soop_channel_id: str,
        notify_channel_id: str,
        message_template: str | None = None,
    ) -> None:
        stmt = text(
            """
            INSERT INTO guild_streamers
            (guild_id, soop_channel_id, notify_channel_id, message_template, created_at)
            VALUES (:guild_id, :soop_channel_id, :notify_channel_id, :message_template, :created_at)
            ON CONFLICT (guild_id, soop_channel_id)
            DO UPDATE SET notify_channel_id=excluded.notify_channel_id,
                          message_template=excluded.message_template
            """
        )
        with self._engine.begin() as conn:
            conn.execute(
                stmt,
                {
                    "guild_id": guild_id,
                    "soop_channel_id": soop_channel_id,
                    "notify_channel_id": notify_channel_id,
                    "message_template": message_template,
                    "created_at": datetime.utcnow().isoformat(),
                },
            )

    def get_links(self, guild_id: str) -> list[dict]:
        stmt = select(self._tables.guild_streamers).where(
            self._tables.guild_streamers.c.guild_id == guild_id
        )
        with self._engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [dict(row) for row in rows]

    def remove_link(self, guild_id: str, soop_channel_id: str | None = None) -> int:
        if soop_channel_id:
            stmt = delete(self._tables.guild_streamers).where(
                (self._tables.guild_streamers.c.guild_id == guild_id)
                & (self._tables.guild_streamers.c.soop_channel_id == soop_channel_id)
            )
        else:
            stmt = delete(self._tables.guild_streamers).where(
                self._tables.guild_streamers.c.guild_id == guild_id
            )
        with self._engine.begin() as conn:
            result = conn.execute(stmt)
            return result.rowcount or 0

    def list_links(self, guild_id: str | None = None) -> list[dict]:
        stmt = select(self._tables.guild_streamers)
        if guild_id:
            stmt = stmt.where(self._tables.guild_streamers.c.guild_id == guild_id)
        with self._engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [dict(row) for row in rows]

    def set_template(self, guild_id: str, soop_channel_id: str, template: str | None) -> bool:
        stmt = (
            update(self._tables.guild_streamers)
            .where(
                (self._tables.guild_streamers.c.guild_id == guild_id)
                & (self._tables.guild_streamers.c.soop_channel_id == soop_channel_id)
            )
            .values(message_template=template)
        )
        with self._engine.begin() as conn:
            result = conn.execute(stmt)
            return (result.rowcount or 0) > 0

    def set_default_notify_channel(self, guild_id: str, channel_id: str | None) -> None:
        if channel_id:
            stmt = text(
                """
                INSERT INTO guild_settings (guild_id, default_notify_channel_id)
                VALUES (:guild_id, :channel_id)
                ON CONFLICT (guild_id)
                DO UPDATE SET default_notify_channel_id=excluded.default_notify_channel_id
                """
            )
            with self._engine.begin() as conn:
                conn.execute(stmt, {"guild_id": guild_id, "channel_id": channel_id})
        else:
            stmt = delete(self._tables.guild_settings).where(
                self._tables.guild_settings.c.guild_id == guild_id
            )
            with self._engine.begin() as conn:
                conn.execute(stmt)

    def get_default_notify_channel(self, guild_id: str) -> str | None:
        stmt = select(self._tables.guild_settings.c.default_notify_channel_id).where(
            self._tables.guild_settings.c.guild_id == guild_id
        )
        with self._engine.begin() as conn:
            row = conn.execute(stmt).fetchone()
        if not row:
            return None
        return row[0]

    def set_embed_template(
        self,
        guild_id: str,
        title: str | None,
        description: str | None,
        color: str | None,
    ) -> None:
        stmt = text(
            """
            INSERT INTO guild_settings (guild_id, embed_title, embed_description, embed_color)
            VALUES (:guild_id, :embed_title, :embed_description, :embed_color)
            ON CONFLICT (guild_id)
            DO UPDATE SET embed_title=excluded.embed_title,
                          embed_description=excluded.embed_description,
                          embed_color=excluded.embed_color
            """
        )
        with self._engine.begin() as conn:
            conn.execute(
                stmt,
                {
                    "guild_id": guild_id,
                    "embed_title": title,
                    "embed_description": description,
                    "embed_color": color,
                },
            )

    def get_embed_template(self, guild_id: str) -> dict[str, str | None]:
        stmt = select(
            self._tables.guild_settings.c.embed_title,
            self._tables.guild_settings.c.embed_description,
            self._tables.guild_settings.c.embed_color,
        ).where(self._tables.guild_settings.c.guild_id == guild_id)
        with self._engine.begin() as conn:
            row = conn.execute(stmt).fetchone()
        if not row:
            return {"title": None, "description": None, "color": None}
        return {"title": row[0], "description": row[1], "color": row[2]}

    def set_mention(self, guild_id: str, mention_type: str | None, mention_value: str | None) -> None:
        stmt = text(
            """
            INSERT INTO guild_settings (guild_id, mention_type, mention_value)
            VALUES (:guild_id, :mention_type, :mention_value)
            ON CONFLICT (guild_id)
            DO UPDATE SET mention_type=excluded.mention_type,
                          mention_value=excluded.mention_value
            """
        )
        with self._engine.begin() as conn:
            conn.execute(
                stmt,
                {
                    "guild_id": guild_id,
                    "mention_type": mention_type,
                    "mention_value": mention_value,
                },
            )

    def get_mention(self, guild_id: str) -> dict[str, str | None]:
        stmt = select(
            self._tables.guild_settings.c.mention_type,
            self._tables.guild_settings.c.mention_value,
        ).where(self._tables.guild_settings.c.guild_id == guild_id)
        with self._engine.begin() as conn:
            row = conn.execute(stmt).fetchone()
        if not row:
            return {"type": None, "value": None}
        return {"type": row[0], "value": row[1]}

    def set_live_status(
        self, guild_id: str, soop_channel_id: str, is_live: bool, broad_no: str | None
    ) -> None:
        stmt = text(
            """
            INSERT INTO live_status (guild_id, soop_channel_id, is_live, broad_no, updated_at)
            VALUES (:guild_id, :soop_channel_id, :is_live, :broad_no, :updated_at)
            ON CONFLICT (guild_id, soop_channel_id)
            DO UPDATE SET is_live=excluded.is_live,
                          broad_no=excluded.broad_no,
                          updated_at=excluded.updated_at
            """
        )
        with self._engine.begin() as conn:
            conn.execute(
                stmt,
                {
                    "guild_id": guild_id,
                    "soop_channel_id": soop_channel_id,
                    "is_live": int(is_live),
                    "broad_no": broad_no,
                    "updated_at": datetime.utcnow().isoformat(),
                },
            )

    def load_live_status(self) -> dict[str, dict[str, str | bool | None]]:
        stmt = select(self._tables.live_status)
        with self._engine.begin() as conn:
            rows = conn.execute(stmt).mappings().all()
        return {
            f"{row['guild_id']}:{row['soop_channel_id']}": {
                "is_live": bool(row["is_live"]),
                "broad_no": row["broad_no"],
            }
            for row in rows
        }

    def prune_live_status(self, active_keys: set[str]) -> None:
        with self._engine.begin() as conn:
            rows = conn.execute(
                select(
                    self._tables.live_status.c.guild_id,
                    self._tables.live_status.c.soop_channel_id,
                )
            ).all()
            for row in rows:
                key = f"{row[0]}:{row[1]}"
                if key not in active_keys:
                    conn.execute(
                        delete(self._tables.live_status).where(
                            (self._tables.live_status.c.guild_id == row[0])
                            & (self._tables.live_status.c.soop_channel_id == row[1])
                        )
                    )

    def remove_live_status(self, guild_id: str, soop_channel_id: str) -> int:
        stmt = delete(self._tables.live_status).where(
            (self._tables.live_status.c.guild_id == guild_id)
            & (self._tables.live_status.c.soop_channel_id == soop_channel_id)
        )
        with self._engine.begin() as conn:
            result = conn.execute(stmt)
            return result.rowcount or 0

    def ping(self) -> bool:
        try:
            with self._engine.begin() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
