import sqlite3
from datetime import datetime


def _sqlite_path(database_url: str) -> str:
    if database_url.startswith("sqlite:///"):
        return database_url[len("sqlite:///"):]
    if database_url.startswith("sqlite://"):
        return database_url[len("sqlite://"):]
    raise ValueError("Only sqlite URLs are supported in the starter scaffold.")


class Storage:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._path = _sqlite_path(database_url)
        self._conn = sqlite3.connect(self._path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS guild_streamers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                soop_channel_id TEXT NOT NULL,
                notify_channel_id TEXT NOT NULL,
                message_template TEXT,
                created_at TEXT NOT NULL,
                UNIQUE (guild_id, soop_channel_id)
            )
            """
        )
        self._ensure_column("guild_streamers", "message_template", "TEXT")
        self._migrate_legacy_links()
        self._conn.commit()

    def _ensure_column(self, table: str, column: str, column_type: str) -> None:
        existing = {
            row["name"]
            for row in self._conn.execute(f"PRAGMA table_info({table})").fetchall()
        }
        if column not in existing:
            self._conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")

    def _migrate_legacy_links(self) -> None:
        # One-time migration for older single-link schema.
        legacy_exists = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='guild_links'"
        ).fetchone()
        if not legacy_exists:
            return
        rows = self._conn.execute(
            "SELECT guild_id, soop_channel_id, notify_channel_id, created_at FROM guild_links"
        ).fetchall()
        for row in rows:
            self._conn.execute(
                """
                INSERT OR IGNORE INTO guild_streamers
                (guild_id, soop_channel_id, notify_channel_id, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (row["guild_id"], row["soop_channel_id"], row["notify_channel_id"], row["created_at"]),
            )
        self._conn.execute("DROP TABLE guild_links")

    def add_link(
        self,
        guild_id: str,
        soop_channel_id: str,
        notify_channel_id: str,
        message_template: str | None = None,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO guild_streamers
            (guild_id, soop_channel_id, notify_channel_id, message_template, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, soop_channel_id)
            DO UPDATE SET notify_channel_id=excluded.notify_channel_id,
                         message_template=excluded.message_template
            """,
            (
                guild_id,
                soop_channel_id,
                notify_channel_id,
                message_template,
                datetime.utcnow().isoformat(),
            ),
        )
        self._conn.commit()

    def get_links(self, guild_id: str) -> list[dict]:
        rows = self._conn.execute(
            "SELECT * FROM guild_streamers WHERE guild_id = ?",
            (guild_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def remove_link(self, guild_id: str, soop_channel_id: str | None = None) -> int:
        if soop_channel_id:
            cursor = self._conn.execute(
                "DELETE FROM guild_streamers WHERE guild_id = ? AND soop_channel_id = ?",
                (guild_id, soop_channel_id),
            )
        else:
            cursor = self._conn.execute(
                "DELETE FROM guild_streamers WHERE guild_id = ?",
                (guild_id,),
            )
        self._conn.commit()
        return cursor.rowcount

    def set_template(self, guild_id: str, soop_channel_id: str, template: str | None) -> bool:
        cursor = self._conn.execute(
            """
            UPDATE guild_streamers
            SET message_template = ?
            WHERE guild_id = ? AND soop_channel_id = ?
            """,
            (template, guild_id, soop_channel_id),
        )
        self._conn.commit()
        return cursor.rowcount > 0

    def list_links(self, guild_id: str | None = None) -> list[dict]:
        if guild_id:
            rows = self._conn.execute(
                "SELECT * FROM guild_streamers WHERE guild_id = ?",
                (guild_id,),
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM guild_streamers").fetchall()
        return [dict(row) for row in rows]
