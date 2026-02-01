import asyncio
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

from soupnotify.bot.cogs.admin import AdminCog
from soupnotify.bot.cogs.help import HelpCog
from soupnotify.bot.cogs.links import LinksCog
from soupnotify.core.metrics import BotMetrics
from soupnotify.core.notifier import Notifier
from soupnotify.core.storage import Storage
from soupnotify.core.config import load_bot_settings
from soupnotify.soop.client import SoopClient
from soupnotify.soop.poller import SoopPoller


load_dotenv()

settings = load_bot_settings()
logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)

intents = discord.Intents.default()

bot_kwargs: dict[str, object] = {
    "command_prefix": "!",
    "intents": intents,
    "application_id": settings.discord_application_id,
}
if settings.shard_count:
    bot_kwargs["shard_count"] = settings.shard_count

bot = commands.Bot(**bot_kwargs)
storage = Storage(settings.database_url)
metrics = BotMetrics()
soop_client = SoopClient(
    settings.soop_api_base_url,
    settings.soop_client_id,
    settings.soop_max_pages,
    settings.soop_channel_api_base_url,
    settings.soop_hardcode_streamer_id,
    settings.soop_thumbnail_url_template,
    settings.soop_retry_max,
    settings.soop_retry_backoff,
)
notifier = Notifier(
    bot,
    settings.notify_rate_per_second,
    settings.notify_burst_rate_per_second,
    settings.notify_burst_threshold,
    metrics,
)
poller = SoopPoller(
    soop_client,
    storage,
    notifier,
    settings.soop_stream_url_base,
    metrics,
    settings.poll_interval_seconds,
    settings.soop_info_cooldown_seconds,
)


@bot.event
async def on_ready() -> None:
    logger.info("Logged in as %s", bot.user)
    await notifier.start()
    asyncio.create_task(poller.run(bot))


@bot.event
async def on_application_command(ctx: discord.ApplicationContext) -> None:
    if ctx.response.is_done():
        return
    try:
        await ctx.defer(ephemeral=True)
    except discord.errors.InteractionResponded:
        # Another handler already responded; avoid crashing the event loop.
        return


def _load_cogs() -> None:
    bot.add_cog(LinksCog(bot, storage, settings, notifier))
    bot.add_cog(AdminCog(bot, storage, settings, metrics))
    bot.add_cog(HelpCog())


def main() -> None:
    _load_cogs()
    bot.run(settings.discord_token)


if __name__ == "__main__":
    main()
