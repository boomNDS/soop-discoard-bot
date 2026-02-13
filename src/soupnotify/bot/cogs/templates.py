import discord
from discord.ext import commands

from soupnotify.core.audit import send_audit
from soupnotify.core.command_log import log_command
from soupnotify.core.discord_utils import safe_respond
from soupnotify.core.embeds import build_live_embed
from soupnotify.core.permissions import require_admin
from soupnotify.core.render import render_embed_overrides, render_message
from soupnotify.core.storage import Storage


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


class TemplatesCog(commands.Cog):
    def __init__(self, bot: commands.Bot, storage: Storage, settings) -> None:
        self._bot = bot
        self._storage = storage
        self._settings = settings

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
        if action in {"set", "clear"} and not await require_admin(ctx, self._storage):
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
            await send_audit(
                self._bot,
                self._storage,
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
        await send_audit(
            self._bot,
            self._storage,
            str(ctx.guild.id),
            f"Updated template for `{soop_channel_id}` by {ctx.user.mention}.",
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
        if action in {"set", "clear"} and not await require_admin(ctx, self._storage):
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
            await send_audit(
                self._bot,
                self._storage,
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
        await send_audit(
            self._bot,
            self._storage,
            str(ctx.guild.id),
            f"Embed template updated by {ctx.user.mention}.",
        )
