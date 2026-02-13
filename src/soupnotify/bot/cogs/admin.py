import logging
import re

import discord
from discord.ext import commands

from soupnotify.core.discord_utils import safe_respond
from soupnotify.core.command_log import log_command
from soupnotify.core.metrics import BotMetrics
from soupnotify.core.storage import Storage

logger = logging.getLogger(__name__)


def _is_admin(ctx: discord.ApplicationContext, storage: Storage) -> bool:
    member = ctx.user if isinstance(ctx.user, discord.Member) else None
    if not member and ctx.guild:
        member = ctx.guild.get_member(ctx.user.id)
    if not member:
        return False
    admin_role_id = storage.get_admin_role(str(ctx.guild.id)) if ctx.guild else None
    if admin_role_id and any(str(role.id) == admin_role_id for role in member.roles):
        return True
    perms = member.guild_permissions
    return perms.administrator or perms.manage_guild


async def _require_admin(ctx: discord.ApplicationContext, storage: Storage) -> bool:
    if _is_admin(ctx, storage):
        return True
    await safe_respond(ctx, "You need Manage Server permission to use this command.", ephemeral=True)
    return False


async def _send_audit(
    bot: commands.Bot, storage: Storage, guild_id: str, message: str
) -> None:
    channel_id = storage.get_audit_channel(guild_id)
    if not channel_id:
        return
    channel = bot.get_channel(int(channel_id))
    if channel:
        try:
            await channel.send(message)
        except Exception:
            logger.exception("Failed to send audit log to %s", channel_id)


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
        if not await _require_admin(ctx, self._storage):
            return
        default_channel = self._storage.get_default_notify_channel(str(ctx.guild.id))
        link_count = len(self._storage.get_links(str(ctx.guild.id)))
        embed_settings = self._storage.get_embed_template(str(ctx.guild.id))
        mention = self._storage.get_mention(str(ctx.guild.id))
        admin_role = self._storage.get_admin_role(str(ctx.guild.id))
        audit_channel = self._storage.get_audit_channel(str(ctx.guild.id))
        rate_limit = self._storage.get_rate_limit(str(ctx.guild.id))
        mention_display = "none"
        if mention.get("type") == "everyone":
            mention_display = "@everyone"
        elif mention.get("type") == "role" and mention.get("value"):
            mention_display = f"<@&{mention['value']}>"
        lines = [
            f"Default channel: {f'<#{default_channel}>' if default_channel else 'None'}",
            f"Linked streamers: {link_count}",
            f"Mentions: {mention_display}",
            f"Admin role: {f'<@&{admin_role}>' if admin_role else 'None'}",
            f"Audit channel: {f'<#{audit_channel}>' if audit_channel else 'None'}",
            f"Rate limit: {f'{rate_limit}/min' if rate_limit else 'None'}",
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
        if not await _require_admin(ctx, self._storage):
            return
        lines = [
            f"Messages sent: {self._metrics.messages_sent}",
            f"Messages failed: {self._metrics.messages_failed}",
            f"API errors: {self._metrics.api_errors}",
            f"Cache hits: {self._metrics.cache_hits}",
            f"Cache misses: {self._metrics.cache_misses}",
            f"Live detected: {self._metrics.live_detected}",
            f"Empty responses: {self._metrics.empty_responses}",
            f"Queue size: {self._metrics.queue_size}",
            f"Last poll: {self._metrics.last_poll_duration_ms:.1f}ms",
            f"Live count: {self._metrics.last_live_count}",
            f"Last empty: {self._metrics.last_empty_count}",
            f"Poll count: {self._metrics.poll_count}",
        ]
        await safe_respond(ctx, "\n".join(lines), ephemeral=True)

    @commands.slash_command(name="debug_live_status", description="Show live_status rows for this server")
    async def debug_live_status(self, ctx: discord.ApplicationContext) -> None:
        log_command(ctx, "debug_live_status")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        if not await _require_admin(ctx, self._storage):
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
            (
                f"- `{streamer}` live={data.get('is_live')} broad_no={data.get('broad_no')} "
                f"last_notified_at={data.get('last_notified_at')}"
            )
            for streamer, data in filtered.items()
        ]
        await safe_respond(ctx, "\n".join(lines), ephemeral=True)

    @commands.slash_command(name="reset_live_status", description="Reset live status for a streamer")
    async def reset_live_status(
        self,
        ctx: discord.ApplicationContext,
        soop_channel_id: discord.Option(str, "SOOP channel identifier"),
    ) -> None:
        log_command(ctx, "reset_live_status")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        if not await _require_admin(ctx, self._storage):
            return
        removed = self._storage.remove_live_status(str(ctx.guild.id), soop_channel_id)
        if removed:
            await safe_respond(ctx, f"Live status reset for `{soop_channel_id}`.", ephemeral=True)
            await _send_audit(
                self._bot,
                self._storage,
                str(ctx.guild.id),
                f"Reset live status for `{soop_channel_id}` by {ctx.user.mention}.",
            )
        else:
            await safe_respond(ctx, "No live status row found for that streamer.", ephemeral=True)

    @commands.slash_command(name="sync", description="Manually sync slash commands")
    async def sync(self, ctx: discord.ApplicationContext) -> None:
        log_command(ctx, "sync")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        if not await _require_admin(ctx, self._storage):
            return
        try:
            await self._bot.sync_commands(guild_ids=[ctx.guild.id])
            await safe_respond(ctx, "Commands synced for this server.", ephemeral=True)
        except Exception:
            logger.exception("Failed to sync commands")
            await safe_respond(ctx, "Sync failed. Check logs.", ephemeral=True)

    @commands.slash_command(name="admin_role", description="Set or clear admin role for bot commands")
    async def admin_role(
        self,
        ctx: discord.ApplicationContext,
        action: discord.Option(str, "Action", choices=["set", "clear"], required=True),
        role: discord.Option(discord.Role, "Role to allow", required=False),
    ) -> None:
        log_command(ctx, "admin_role")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        if not await _require_admin(ctx, self._storage):
            return
        if action == "set":
            if not role:
                await safe_respond(ctx, "Provide a role to set.", ephemeral=True)
                return
            self._storage.set_admin_role(str(ctx.guild.id), str(role.id))
            await safe_respond(ctx, f"Admin role set to {role.mention}.", ephemeral=True)
            await _send_audit(
                self._bot,
                self._storage,
                str(ctx.guild.id),
                f"Admin role set to {role.mention} by {ctx.user.mention}.",
            )
            return
        self._storage.set_admin_role(str(ctx.guild.id), None)
        await safe_respond(ctx, "Admin role cleared.", ephemeral=True)
        await _send_audit(
            self._bot,
            self._storage,
            str(ctx.guild.id),
            f"Admin role cleared by {ctx.user.mention}.",
        )

    @commands.slash_command(name="audit_channel", description="Set or clear audit log channel")
    async def audit_channel(
        self,
        ctx: discord.ApplicationContext,
        action: discord.Option(str, "Action", choices=["set", "clear"], required=True),
        channel: discord.Option(str, "Channel mention or ID", required=False),
    ) -> None:
        log_command(ctx, "audit_channel")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        if not await _require_admin(ctx, self._storage):
            return
        if action == "set":
            if not channel:
                await safe_respond(ctx, "Provide a channel to set.", ephemeral=True)
                return
            match = re.match(r"^<#(\\d+)>$", channel.strip())
            channel_id = match.group(1) if match else channel if channel.isdigit() else None
            if not channel_id:
                await safe_respond(ctx, "Provide a valid channel mention or ID.", ephemeral=True)
                return
            self._storage.set_audit_channel(str(ctx.guild.id), channel_id)
            await safe_respond(ctx, f"Audit channel set to <#{channel_id}>.", ephemeral=True)
            await _send_audit(
                self._bot,
                self._storage,
                str(ctx.guild.id),
                f"Audit channel set to <#{channel_id}> by {ctx.user.mention}.",
            )
            return
        self._storage.set_audit_channel(str(ctx.guild.id), None)
        await safe_respond(ctx, "Audit channel cleared.", ephemeral=True)
        await _send_audit(
            self._bot,
            self._storage,
            str(ctx.guild.id),
            f"Audit channel cleared by {ctx.user.mention}.",
        )

    @commands.slash_command(name="rate_limit", description="Set or clear per-guild notify rate limit")
    async def rate_limit(
        self,
        ctx: discord.ApplicationContext,
        action: discord.Option(str, "Action", choices=["set", "clear"], required=True),
        per_min: discord.Option(int, "Notifications per minute", required=False),
    ) -> None:
        log_command(ctx, "rate_limit")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        if not await _require_admin(ctx, self._storage):
            return
        if action == "set":
            if per_min is None or per_min <= 0:
                await safe_respond(ctx, "Provide a positive number.", ephemeral=True)
                return
            self._storage.set_rate_limit(str(ctx.guild.id), per_min)
            await safe_respond(ctx, f"Rate limit set to {per_min}/min.", ephemeral=True)
            await _send_audit(
                self._bot,
                self._storage,
                str(ctx.guild.id),
                f"Rate limit set to {per_min}/min by {ctx.user.mention}.",
            )
            return
        self._storage.set_rate_limit(str(ctx.guild.id), None)
        await safe_respond(ctx, "Rate limit cleared.", ephemeral=True)
        await _send_audit(
            self._bot,
            self._storage,
            str(ctx.guild.id),
            f"Rate limit cleared by {ctx.user.mention}.",
        )
