import discord
from discord.ext import commands

from soupnotify.core.audit import send_audit
from soupnotify.core.command_log import log_command
from soupnotify.core.discord_utils import parse_channel_id, safe_respond
from soupnotify.core.permissions import require_admin
from soupnotify.core.storage import Storage


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


class LinkingCog(commands.Cog):
    def __init__(self, bot: commands.Bot, storage: Storage) -> None:
        self._bot = bot
        self._storage = storage

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
        if not await require_admin(ctx, self._storage):
            return
        if notify_channel:
            notify_channel_id = parse_channel_id(notify_channel)
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
        await send_audit(
            self._bot,
            self._storage,
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
        if not await require_admin(ctx, self._storage):
            return
        removed = self._storage.remove_link(str(ctx.guild.id), soop_channel_id)
        if removed:
            await safe_respond(ctx, "Link removed.", ephemeral=True)
            await send_audit(
                self._bot,
                self._storage,
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
        if not await require_admin(ctx, self._storage):
            return
        removed = self._storage.remove_link(str(ctx.guild.id))
        if removed:
            await safe_respond(ctx, "All links removed.", ephemeral=True)
            await send_audit(
                self._bot,
                self._storage,
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
        notify_channel_id = parse_channel_id(notify_channel)
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
