import discord
from discord.ext import commands

from soupnotify.core.audit import send_audit
from soupnotify.core.command_log import log_command
from soupnotify.core.discord_utils import parse_channel_id, safe_respond
from soupnotify.core.permissions import require_admin
from soupnotify.core.storage import Storage


class NotificationsCog(commands.Cog):
    def __init__(self, bot: commands.Bot, storage: Storage) -> None:
        self._bot = bot
        self._storage = storage

    @commands.slash_command(name="test", description="Send a test notification")
    async def test(
        self,
        ctx: discord.ApplicationContext,
        soop_channel_id: discord.Option(str, "SOOP channel identifier", required=False),
    ) -> None:
        log_command(ctx, "test")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        links = self._storage.get_links(str(ctx.guild.id))
        if not links:
            await safe_respond(ctx, "No SOOP links configured.", ephemeral=True)
            return
        if soop_channel_id:
            target = next((item for item in links if item["soop_channel_id"] == soop_channel_id), None)
            if not target:
                await safe_respond(ctx, "That SOOP channel is not linked.", ephemeral=True)
                return
        else:
            target = links[0]
        channel = self._bot.get_channel(int(target["notify_channel_id"]))
        if not channel:
            await safe_respond(ctx, "Notify channel not found.", ephemeral=True)
            return
        await channel.send(
            f"\N{WHITE HEAVY CHECK MARK} Test notification for `{target['soop_channel_id']}`."
        )
        await safe_respond(ctx, "Sent test notification.", ephemeral=True)

    @commands.slash_command(name="default_channel", description="Set or clear default notify channel")
    async def default_channel(
        self,
        ctx: discord.ApplicationContext,
        action: discord.Option(str, "Action", choices=["set", "clear"], required=True),
        channel: discord.Option(str, "Channel mention or ID", required=False),
    ) -> None:
        log_command(ctx, "default_channel")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        if not await require_admin(ctx, self._storage):
            return
        if action == "set":
            channel_id = parse_channel_id(channel)
            if not channel_id:
                await safe_respond(
                    ctx, "Provide a channel mention like #general or a numeric channel ID.", ephemeral=True
                )
                return
            self._storage.set_default_notify_channel(str(ctx.guild.id), str(channel_id))
            await safe_respond(ctx, f"Default channel set to <#{channel_id}>.", ephemeral=True)
            await send_audit(
                self._bot,
                self._storage,
                str(ctx.guild.id),
                f"Default channel set to <#{channel_id}> by {ctx.user.mention}.",
            )
            return
        self._storage.set_default_notify_channel(str(ctx.guild.id), None)
        await safe_respond(ctx, "Default channel cleared.", ephemeral=True)
        await send_audit(
            self._bot,
            self._storage,
            str(ctx.guild.id),
            f"Default channel cleared by {ctx.user.mention}.",
        )

    @commands.slash_command(name="mention", description="Configure mentions for live notifications")
    async def mention(
        self,
        ctx: discord.ApplicationContext,
        action: discord.Option(str, "Action", choices=["set", "clear", "show"], required=True),
        mention_type: discord.Option(
            str,
            "Mention type",
            choices=["none", "everyone", "role"],
            required=False,
        ),
        role: discord.Option(discord.Role, "Role to mention", required=False),
    ) -> None:
        log_command(ctx, "mention")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        if action in {"set", "clear"} and not await require_admin(ctx, self._storage):
            return
        if action == "show":
            current = self._storage.get_mention(str(ctx.guild.id))
            display = "none"
            if current.get("type") == "everyone":
                display = "@everyone"
            elif current.get("type") == "role" and current.get("value"):
                display = f"<@&{current['value']}>"
            await safe_respond(ctx, f"Mention: {display}", ephemeral=True)
            return
        if action == "clear":
            self._storage.set_mention(str(ctx.guild.id), None, None)
            await safe_respond(ctx, "Mentions disabled.", ephemeral=True)
            await send_audit(
                self._bot,
                self._storage,
                str(ctx.guild.id),
                f"Mentions cleared by {ctx.user.mention}.",
            )
            return
        if not mention_type:
            await safe_respond(ctx, "Choose a mention type.", ephemeral=True)
            return
        if mention_type == "none":
            self._storage.set_mention(str(ctx.guild.id), None, None)
            await safe_respond(ctx, "Mentions disabled.", ephemeral=True)
            await send_audit(
                self._bot,
                self._storage,
                str(ctx.guild.id),
                f"Mentions cleared by {ctx.user.mention}.",
            )
            return
        if mention_type == "everyone":
            self._storage.set_mention(str(ctx.guild.id), "everyone", None)
            await safe_respond(ctx, "Mentions set to @everyone.", ephemeral=True)
            await send_audit(
                self._bot,
                self._storage,
                str(ctx.guild.id),
                f"Mentions set to @everyone by {ctx.user.mention}.",
            )
            return
        if mention_type == "role":
            if not role:
                await safe_respond(ctx, "Provide a role to mention.", ephemeral=True)
                return
            self._storage.set_mention(str(ctx.guild.id), "role", str(role.id))
            await safe_respond(ctx, f"Mentions set to {role.mention}.", ephemeral=True)
            await send_audit(
                self._bot,
                self._storage,
                str(ctx.guild.id),
                f"Mentions set to {role.mention} by {ctx.user.mention}.",
            )
