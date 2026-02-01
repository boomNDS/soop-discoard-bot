import re

import discord
from discord.ext import commands

from soupnotify.core.command_log import log_command
from soupnotify.core.discord_utils import safe_respond
from soupnotify.core.embeds import build_live_embed
from soupnotify.core.render import render_embed_overrides, render_message
from soupnotify.core.storage import Storage


CHANNEL_MENTION_RE = re.compile(r"^<#(\d+)>$")


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


def _format_links_page(links: list[dict], page: int, page_size: int) -> str:
    start = (page - 1) * page_size
    end = start + page_size
    slice_links = links[start:end]
    lines = [
        f"- `{item['soop_channel_id']}` -> <#{item['notify_channel_id']}>"
        for item in slice_links
    ]
    total_pages = (len(links) + page_size - 1) // page_size
    lines.append(f"Page {page}/{total_pages}")
    return "\n".join(lines)


def _parse_channel_id(value: str | None) -> str | None:
    if not value:
        return None
    match = CHANNEL_MENTION_RE.match(value.strip())
    if match:
        return match.group(1)
    if value.isdigit():
        return value
    return None


def _filter_links(
    links: list[dict],
    soop_channel_id: str | None,
    notify_channel_id: str | None,
) -> list[dict]:
    filtered = links
    if soop_channel_id:
        filtered = [link for link in filtered if link["soop_channel_id"] == soop_channel_id]
    if notify_channel_id:
        filtered = [link for link in filtered if link["notify_channel_id"] == notify_channel_id]
    return filtered


def _preview_embed(
    soop_channel_id: str,
    notify_channel_id: int,
    guild_name: str,
    stream_url_base: str,
    embed_settings: dict,
) -> discord.Embed:
    stream_url = f"{stream_url_base}/{soop_channel_id}"
    title_override, description_override, color_override = render_embed_overrides(
        embed_settings,
        soop_channel_id,
        notify_channel_id,
        guild_name,
        stream_url_base,
    )
    info = {
        "broadTitle": "Preview: stream title",
        "categoryName": "Category",
        "currentSumViewer": 123,
        "broadNo": "000000",
    }
    thumbnail_url = "https://liveimg.sooplive.co.kr/h/000000.webp"
    return build_live_embed(
        soop_channel_id,
        stream_url,
        info,
        thumbnail_url,
        title_override=title_override,
        description_override=description_override,
        color_hex=color_override,
    )


class _LinkListView(discord.ui.View):
    def __init__(self, links: list[dict], page: int, page_size: int) -> None:
        super().__init__(timeout=120)
        self._links = links
        self._page = page
        self._page_size = page_size
        self._total_pages = (len(links) + page_size - 1) // page_size
        self._prev = discord.ui.Button(label="Prev", style=discord.ButtonStyle.secondary)
        self._next = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary)
        self._prev.callback = self._on_prev
        self._next.callback = self._on_next
        self.add_item(self._prev)
        self.add_item(self._next)
        self._refresh_buttons()

    def _refresh_buttons(self) -> None:
        self._prev.disabled = self._page <= 1
        self._next.disabled = self._page >= self._total_pages

    async def _update(self, interaction: discord.Interaction) -> None:
        self._refresh_buttons()
        content = _format_links_page(self._links, self._page, self._page_size)
        await interaction.response.edit_message(content=content, view=self)

    async def _on_prev(self, interaction: discord.Interaction) -> None:
        if self._page > 1:
            self._page -= 1
        await self._update(interaction)

    async def _on_next(self, interaction: discord.Interaction) -> None:
        if self._page < self._total_pages:
            self._page += 1
        await self._update(interaction)


class LinksCog(commands.Cog):
    def __init__(
        self,
        bot: commands.Bot,
        storage: Storage,
        settings,
        notifier,
    ) -> None:
        self._bot = bot
        self._storage = storage
        self._settings = settings
        self._notifier = notifier

    async def _send_audit(self, guild_id: str, message: str) -> None:
        channel_id = self._storage.get_audit_channel(guild_id)
        if not channel_id:
            return
        channel = self._bot.get_channel(int(channel_id))
        if channel:
            try:
                await channel.send(message)
            except Exception:
                pass

    @commands.slash_command(name="link", description="Link this server to a SOOP channel")
    async def link(
        self,
        ctx: discord.ApplicationContext,
        soop_channel_id: discord.Option(str, "SOOP channel identifier"),
        notify_channel: discord.Option(
            str,
            "Discord channel mention or ID (optional if default is set)",
            required=False,
        ),
        message_template: discord.Option(
            str,
            "Optional template: {soop_channel_id}, {notify_channel}, {guild}, {soop_url}.",
            required=False,
        ),
    ) -> None:
        log_command(ctx, "link")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        if not await _require_admin(ctx, self._storage):
            return
        if notify_channel:
            notify_channel_id = _parse_channel_id(notify_channel)
            if not notify_channel_id:
                await safe_respond(
                    ctx,
                    "Provide a channel mention like #general or a numeric channel ID.",
                    ephemeral=True,
                )
                return
        else:
            notify_channel_id = self._storage.get_default_notify_channel(str(ctx.guild.id))
            if not notify_channel_id:
                await safe_respond(
                    ctx, "Set a default channel with /default_channel first.", ephemeral=True
                )
                return
        self._storage.add_link(
            str(ctx.guild.id),
            soop_channel_id,
            str(notify_channel_id),
            message_template,
        )
        await safe_respond(
            ctx,
            f"Linked SOOP `{soop_channel_id}` to <#{notify_channel_id}>.",
            ephemeral=True,
        )
        await self._send_audit(
            str(ctx.guild.id),
            f"Linked `{soop_channel_id}` -> <#{notify_channel_id}> by {ctx.user.mention}.",
        )

    @commands.slash_command(name="unlink", description="Remove the SOOP link for this server")
    async def unlink(
        self,
        ctx: discord.ApplicationContext,
        soop_channel_id: discord.Option(str, "SOOP channel identifier"),
    ) -> None:
        log_command(ctx, "unlink")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        if not await _require_admin(ctx, self._storage):
            return
        removed = self._storage.remove_link(str(ctx.guild.id), soop_channel_id)
        if removed:
            await safe_respond(ctx, "Link removed.", ephemeral=True)
            await self._send_audit(
                str(ctx.guild.id),
                f"Unlinked `{soop_channel_id}` by {ctx.user.mention}.",
            )
        else:
            await safe_respond(ctx, "No link found for this server.", ephemeral=True)

    @commands.slash_command(name="unlink_all", description="Remove all SOOP links for this server")
    async def unlink_all(self, ctx: discord.ApplicationContext) -> None:
        log_command(ctx, "unlink_all")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        if not await _require_admin(ctx, self._storage):
            return
        removed = self._storage.remove_link(str(ctx.guild.id))
        if removed:
            await safe_respond(ctx, "All links removed.", ephemeral=True)
            await self._send_audit(
                str(ctx.guild.id),
                f"Removed all links by {ctx.user.mention}.",
            )
        else:
            await safe_respond(ctx, "No links found for this server.", ephemeral=True)

    @commands.slash_command(name="status", description="Show current SOOP link status")
    async def status(self, ctx: discord.ApplicationContext) -> None:
        log_command(ctx, "status")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        links = self._storage.get_links(str(ctx.guild.id))
        if not links:
            await safe_respond(ctx, "No SOOP links configured.", ephemeral=True)
            return
        preview = links[:10]
        lines = [
            (
                f"- `{item['soop_channel_id']}` -> <#{item['notify_channel_id']}>"
                + (" (custom template)" if item.get("message_template") else "")
            )
            for item in preview
        ]
        if len(links) > len(preview):
            lines.append(f"...and {len(links) - len(preview)} more")
        await safe_respond(ctx, "\n".join(lines), ephemeral=True)

    @commands.slash_command(name="link_list", description="List linked streamers with pagination")
    async def link_list(
        self,
        ctx: discord.ApplicationContext,
        page: discord.Option(int, "Page number", required=False),
        soop_channel_id: discord.Option(str, "Filter by SOOP channel", required=False),
        notify_channel: discord.Option(str, "Filter by notify channel", required=False),
    ) -> None:
        log_command(ctx, "link_list")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        links = self._storage.get_links(str(ctx.guild.id))
        notify_channel_id = _parse_channel_id(notify_channel)
        filtered = _filter_links(links, soop_channel_id, notify_channel_id)
        if not filtered:
            await safe_respond(ctx, "No SOOP links configured.", ephemeral=True)
            return
        page_size = 10
        total_pages = (len(filtered) + page_size - 1) // page_size
        page = max(1, min(page or 1, total_pages))
        content = _format_links_page(filtered, page, page_size)
        view = _LinkListView(filtered, page, page_size)
        await safe_respond(ctx, content, view=view, ephemeral=True)

    @commands.slash_command(name="preview", description="Preview the live notification message")
    async def preview(self, ctx: discord.ApplicationContext) -> None:
        log_command(ctx, "preview")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        links = self._storage.get_links(str(ctx.guild.id))
        if not links:
            await safe_respond(ctx, "No SOOP links configured.", ephemeral=True)
            return
        target = links[0]
        notify_channel_id = int(target["notify_channel_id"])
        template = target.get("message_template")
        message = render_message(
            template,
            target["soop_channel_id"],
            notify_channel_id,
            ctx.guild.name,
            self._settings.soop_stream_url_base,
            None,
        )
        embed_settings = self._storage.get_embed_template(str(ctx.guild.id))
        embed = _preview_embed(
            target["soop_channel_id"],
            notify_channel_id,
            ctx.guild.name,
            self._settings.soop_stream_url_base,
            embed_settings,
        )
        await safe_respond(ctx, message, embed=embed, ephemeral=True)

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

    @commands.slash_command(name="template", description="Manage notification templates")
    async def template(
        self,
        ctx: discord.ApplicationContext,
        action: discord.Option(str, "Action", choices=["set", "clear", "list"], required=True),
        soop_channel_id: discord.Option(str, "SOOP channel identifier", required=False),
        message_template: discord.Option(
            str,
            "Template: {soop_channel_id}, {notify_channel}, {guild}, {soop_url}.",
            required=False,
        ),
    ) -> None:
        log_command(ctx, "template")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        if action in {"set", "clear"} and not await _require_admin(ctx, self._storage):
            return
        if action == "list":
            links = self._storage.get_links(str(ctx.guild.id))
            if not links:
                await safe_respond(ctx, "No SOOP links configured.", ephemeral=True)
                return
            preview = links[:10]
            lines = [
                (
                    f"- `{item['soop_channel_id']}` -> "
                    f"{item.get('message_template') or '(default)'}"
                )
                for item in preview
            ]
            if len(links) > len(preview):
                lines.append(f"...and {len(links) - len(preview)} more")
            await safe_respond(ctx, "\n".join(lines), ephemeral=True)
            return

        if not soop_channel_id:
            await safe_respond(ctx, "Provide a SOOP channel id.", ephemeral=True)
            return

        if action == "clear":
            updated = self._storage.set_template(str(ctx.guild.id), soop_channel_id, None)
            if not updated:
                await safe_respond(ctx, "That SOOP channel is not linked.", ephemeral=True)
                return
            await safe_respond(ctx, "Template cleared.", ephemeral=True)
            await self._send_audit(
                str(ctx.guild.id),
                f"Cleared template for `{soop_channel_id}` by {ctx.user.mention}.",
            )
            return

        if not message_template:
            await safe_respond(ctx, "Provide a message template.", ephemeral=True)
            return

        updated = self._storage.set_template(str(ctx.guild.id), soop_channel_id, message_template)
        if not updated:
            await safe_respond(ctx, "That SOOP channel is not linked.", ephemeral=True)
            return
        await safe_respond(ctx, "Template updated.", ephemeral=True)
        await self._send_audit(
            str(ctx.guild.id),
            f"Updated template for `{soop_channel_id}` by {ctx.user.mention}.",
        )

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
        if not await _require_admin(ctx, self._storage):
            return
        if action == "set":
            channel_id = _parse_channel_id(channel)
            if not channel_id:
                await safe_respond(
                    ctx, "Provide a channel mention like #general or a numeric channel ID.", ephemeral=True
                )
                return
            self._storage.set_default_notify_channel(str(ctx.guild.id), str(channel_id))
            await safe_respond(ctx, f"Default channel set to <#{channel_id}>.", ephemeral=True)
            await self._send_audit(
                str(ctx.guild.id),
                f"Default channel set to <#{channel_id}> by {ctx.user.mention}.",
            )
            return
        self._storage.set_default_notify_channel(str(ctx.guild.id), None)
        await safe_respond(ctx, "Default channel cleared.", ephemeral=True)
        await self._send_audit(
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
        if action in {"set", "clear"} and not await _require_admin(ctx, self._storage):
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
            await self._send_audit(
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
            await self._send_audit(
                str(ctx.guild.id),
                f"Mentions cleared by {ctx.user.mention}.",
            )
            return
        if mention_type == "everyone":
            self._storage.set_mention(str(ctx.guild.id), "everyone", None)
            await safe_respond(ctx, "Mentions set to @everyone.", ephemeral=True)
            await self._send_audit(
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
            await self._send_audit(
                str(ctx.guild.id),
                f"Mentions set to {role.mention} by {ctx.user.mention}.",
            )

    @commands.slash_command(name="embed_template", description="Customize live notification embed")
    async def embed_template(
        self,
        ctx: discord.ApplicationContext,
        action: discord.Option(str, "Action", choices=["set", "clear", "show"], required=True),
        title: discord.Option(str, "Embed title (supports variables)", required=False),
        description: discord.Option(str, "Embed description (supports variables)", required=False),
        color: discord.Option(str, "Hex color, e.g. #FF5500", required=False),
    ) -> None:
        log_command(ctx, "embed_template")
        if not ctx.guild:
            await safe_respond(ctx, "This command must be used in a server.", ephemeral=True)
            return
        if action in {"set", "clear"} and not await _require_admin(ctx, self._storage):
            return
        if action == "show":
            current = self._storage.get_embed_template(str(ctx.guild.id))
            lines = [
                f"Title: {current.get('title') or 'default'}",
                f"Description: {current.get('description') or 'default'}",
                f"Color: {current.get('color') or 'default'}",
                "Variables: {soop_channel_id}, {soop_url}, {notify_channel}, {guild}",
            ]
            await safe_respond(ctx, "\n".join(lines), ephemeral=True)
            return
        if action == "clear":
            self._storage.set_embed_template(str(ctx.guild.id), None, None, None)
            await safe_respond(ctx, "Embed template cleared.", ephemeral=True)
            await self._send_audit(
                str(ctx.guild.id),
                f"Embed template cleared by {ctx.user.mention}.",
            )
            return
        if not title and not description and not color:
            await safe_respond(
                ctx, "Provide at least one of title, description, or color.", ephemeral=True
            )
            return
        if color:
            color_value = color.strip().lstrip("#")
            if len(color_value) != 6 or any(c not in "0123456789abcdefABCDEF" for c in color_value):
                await safe_respond(
                    ctx, "Color must be a 6-digit hex value like #FF5500.", ephemeral=True
                )
                return
            color = color_value
        self._storage.set_embed_template(str(ctx.guild.id), title, description, color)
        await safe_respond(ctx, "Embed template updated.", ephemeral=True)
        await self._send_audit(
            str(ctx.guild.id),
            f"Embed template updated by {ctx.user.mention}.",
        )
