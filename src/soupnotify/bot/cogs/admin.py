import logging

import discord
from discord.ext import commands

from soupnotify.core.discord_utils import safe_respond
from soupnotify.core.command_log import log_command
from soupnotify.core.metrics import BotMetrics
from soupnotify.core.storage import Storage

logger = logging.getLogger(__name__)


def _is_admin(ctx: discord.ApplicationContext) -> bool:
    perms = ctx.user.guild_permissions
    return perms.administrator or perms.manage_guild


async def _require_admin(ctx: discord.ApplicationContext) -> bool:
    if _is_admin(ctx):
        return True
    await safe_respond(ctx, "You need Manage Server permission to use this command.", ephemeral=True)
    return False


class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot, storage: Storage, settings, metrics: BotMetrics) -> None:
        self._bot = bot
        self._storage = storage
        self._settings = settings
        self._metrics = metrics

    @commands.slash_command(name="config", description="Show current guild configuration")
    async def config(self, ctx: discord.ApplicationContext) -> None:
        log_command(ctx, "config")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        if not await _require_admin(ctx):
            return
        default_channel = self._storage.get_default_notify_channel(str(ctx.guild.id))
        link_count = len(self._storage.get_links(str(ctx.guild.id)))
        embed_settings = self._storage.get_embed_template(str(ctx.guild.id))
        mention = self._storage.get_mention(str(ctx.guild.id))
        mention_display = "none"
        if mention.get("type") == "everyone":
            mention_display = "@everyone"
        elif mention.get("type") == "role" and mention.get("value"):
            mention_display = f"<@&{mention['value']}>"
        lines = [
            f"Default channel: {f'<#{default_channel}>' if default_channel else 'None'}",
            f"Linked streamers: {link_count}",
            f"Mentions: {mention_display}",
            f"Embed title: {embed_settings.get('title') or 'default'}",
            f"Embed description: {embed_settings.get('description') or 'default'}",
            f"Embed color: {embed_settings.get('color') or 'default'}",
            f"Poll interval: {self._settings.poll_interval_seconds}s",
            f"Queue size: {self._metrics.queue_size}",
        ]
        await safe_respond(ctx, "\n".join(lines), ephemeral=True)

    @commands.slash_command(name="metrics", description="Show bot metrics")
    async def metrics(self, ctx: discord.ApplicationContext) -> None:
        log_command(ctx, "metrics")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        if not await _require_admin(ctx):
            return
        lines = [
            f"Messages sent: {self._metrics.messages_sent}",
            f"Messages failed: {self._metrics.messages_failed}",
            f"API errors: {self._metrics.api_errors}",
            f"Cache hits: {self._metrics.cache_hits}",
            f"Cache misses: {self._metrics.cache_misses}",
            f"Queue size: {self._metrics.queue_size}",
            f"Last poll: {self._metrics.last_poll_duration_ms:.1f}ms",
            f"Live count: {self._metrics.last_live_count}",
            f"Poll count: {self._metrics.poll_count}",
        ]
        await safe_respond(ctx, "\n".join(lines), ephemeral=True)

    @commands.slash_command(name="debug_live_status", description="Show live_status rows for this server")
    async def debug_live_status(self, ctx: discord.ApplicationContext) -> None:
        log_command(ctx, "debug_live_status")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        if not await _require_admin(ctx):
            return
        rows = self._storage.load_live_status()
        prefix = f"{ctx.guild.id}:"
        filtered = {
            key[len(prefix) :]: value for key, value in rows.items() if key.startswith(prefix)
        }
        if not filtered:
            await safe_respond(ctx, "No live_status rows for this server.", ephemeral=True)
            return
        lines = [
            f"- `{streamer}` live={data.get('is_live')} broad_no={data.get('broad_no')}"
            for streamer, data in filtered.items()
        ]
        await safe_respond(ctx, "\n".join(lines), ephemeral=True)

    @commands.slash_command(name="sync", description="Manually sync slash commands")
    async def sync(self, ctx: discord.ApplicationContext) -> None:
        log_command(ctx, "sync")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        if not await _require_admin(ctx):
            return
        try:
            await self._bot.sync_commands(guild_ids=[ctx.guild.id])
            await safe_respond(ctx, "Commands synced for this server.", ephemeral=True)
        except Exception:
            logger.exception("Failed to sync commands")
            await safe_respond(ctx, "Sync failed. Check logs.", ephemeral=True)
