import asyncio
import logging

import discord
from discord.ext import commands

from soupnotify.bot.cogs.admin import AdminCog
from soupnotify.bot.cogs.help import HelpCog
from soupnotify.bot.cogs.links import LinksCog
from soupnotify.core.config import load_bot_settings
from soupnotify.core.metrics import BotMetrics
from soupnotify.core.notifier import Notifier
from soupnotify.core.storage import Storage
from soupnotify.soop.client import SoopClient
from soupnotify.soop.poller import SoopPoller


settings = load_bot_settings()
logging.basicConfig(level=settings.log_level.upper())
logger = logging.getLogger(__name__)

bot_kwargs = {
    "intents": discord.Intents.default(),
    "application_id": settings.discord_application_id,
}
if settings.shard_count:
    bot_kwargs["shard_count"] = settings.shard_count

bot = commands.Bot(**bot_kwargs)
storage = Storage(settings.database_url)
metrics = BotMetrics()
soop_client = SoopClient(
    settings.soop_channel_api_base_url,
    "",
    0,
    settings.soop_channel_api_base_url,
    settings.soop_hardcode_streamer_id,
    settings.soop_thumbnail_url_template,
    settings.soop_retry_max,
    settings.soop_retry_backoff,
    channel_headers=settings.soop_channel_headers,
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
