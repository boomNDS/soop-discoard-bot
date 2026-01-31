import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    soop_api_base_url: str
    soop_client_id: str
    database_url: str
    notify_channel_id: str | None
    poll_interval_seconds: int
    soop_max_pages: int
    notify_rate_per_second: float
    notify_burst_rate_per_second: float
    notify_burst_threshold: int
    shard_count: int | None
    log_level: str


@dataclass(frozen=True)
class BotSettings(Settings):
    discord_token: str
    discord_application_id: str
    discord_guild_id: str | None


def _get_env(name: str, required: bool = False, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if required and not value:
        raise ValueError(f"Missing required environment variable: {name}")
    return value


def load_settings() -> Settings:
    return Settings(
        soop_api_base_url=_get_env("SOOP_API_BASE_URL", required=True),
        soop_client_id=_get_env("SOOP_CLIENT_ID", required=True),
        database_url=_get_env("DATABASE_URL", required=True),
        notify_channel_id=_get_env("NOTIFY_CHANNEL_ID"),
        poll_interval_seconds=int(_get_env("POLL_INTERVAL_SECONDS", default="60") or "60"),
        soop_max_pages=int(_get_env("SOOP_MAX_PAGES", default="5") or "5"),
        notify_rate_per_second=float(
            _get_env("NOTIFY_RATE_PER_SECOND", default="2") or "2"
        ),
        notify_burst_rate_per_second=float(
            _get_env("NOTIFY_BURST_RATE_PER_SECOND", default="10") or "10"
        ),
        notify_burst_threshold=int(
            _get_env("NOTIFY_BURST_THRESHOLD", default="25") or "25"
        ),
        shard_count=(
            int(_get_env("SHARD_COUNT"))
            if _get_env("SHARD_COUNT") is not None
            else None
        ),
        log_level=_get_env("LOG_LEVEL", default="info") or "info",
    )


def load_bot_settings() -> BotSettings:
    base = load_settings()
    return BotSettings(
        **base.__dict__,
        discord_token=_get_env("DISCORD_TOKEN", required=True),
        discord_application_id=_get_env("DISCORD_APPLICATION_ID", required=True),
        discord_guild_id=_get_env("DISCORD_GUILD_ID"),
    )
