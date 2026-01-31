import asyncio
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

from soupnotify.core.config import load_bot_settings
from soupnotify.core.embeds import build_live_embed
from soupnotify.core.metrics import BotMetrics
from soupnotify.core.notifier import Notifier
from soupnotify.core.storage import Storage
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
)


@bot.event
async def on_ready() -> None:
    logger.info("Logged in as %s", bot.user)
    try:
        if settings.discord_guild_id:
            guild_id = int(settings.discord_guild_id)
            await bot.sync_commands(guild_ids=[guild_id])
            logger.info("Synced commands to guild %s", guild_id)
        else:
            await bot.sync_commands()
            logger.info("Synced global commands")
    except Exception:
        logger.exception("Failed to sync commands")
    await notifier.start()
    asyncio.create_task(poller.run(bot))


def _is_admin(ctx: discord.ApplicationContext) -> bool:
    perms = ctx.user.guild_permissions
    return perms.administrator or perms.manage_guild


async def _require_admin(ctx: discord.ApplicationContext) -> bool:
    if _is_admin(ctx):
        return True
    await ctx.respond("You need Manage Server permission to use this command.", ephemeral=True)
    return False


@bot.slash_command(name="link", description="Link this server to a SOOP channel")
async def link(
    ctx: discord.ApplicationContext,
    soop_channel_id: discord.Option(str, "SOOP channel identifier"),
    notify_channel: discord.Option(
        discord.TextChannel,
        "Discord channel for alerts (optional if default is set)",
        required=False,
    ),
    message_template: discord.Option(
        str,
        "Optional template: {soop_channel_id}, {notify_channel}, {guild}, {soop_url}.",
        required=False,
    ),
) -> None:
    if not ctx.guild:
        await ctx.respond("This command must be used in a server.")
        return
    if not await _require_admin(ctx):
        return
    notify_channel_id = None
    if notify_channel:
        notify_channel_id = str(notify_channel.id)
    else:
        notify_channel_id = storage.get_default_notify_channel(str(ctx.guild.id))
        if not notify_channel_id:
            await ctx.respond("Set a default channel with /default_channel first.", ephemeral=True)
            return
    storage.add_link(
        str(ctx.guild.id),
        soop_channel_id,
        str(notify_channel_id),
        message_template,
    )
    await ctx.respond(
        f"Linked SOOP `{soop_channel_id}` to <#{notify_channel_id}>.",
        ephemeral=True,
    )


@bot.slash_command(name="unlink", description="Remove the SOOP link for this server")
async def unlink(
    ctx: discord.ApplicationContext,
    soop_channel_id: discord.Option(str, "SOOP channel identifier"),
) -> None:
    if not ctx.guild:
        await ctx.respond("This command must be used in a server.")
        return
    if not await _require_admin(ctx):
        return
    removed = storage.remove_link(str(ctx.guild.id), soop_channel_id)
    if removed:
        await ctx.respond("Link removed.", ephemeral=True)
    else:
        await ctx.respond("No link found for this server.", ephemeral=True)


@bot.slash_command(name="unlink_all", description="Remove all SOOP links for this server")
async def unlink_all(ctx: discord.ApplicationContext) -> None:
    if not ctx.guild:
        await ctx.respond("This command must be used in a server.")
        return
    if not await _require_admin(ctx):
        return
    removed = storage.remove_link(str(ctx.guild.id))
    if removed:
        await ctx.respond("All links removed.", ephemeral=True)
    else:
        await ctx.respond("No links found for this server.", ephemeral=True)


@bot.slash_command(name="status", description="Show current SOOP link status")
async def status(ctx: discord.ApplicationContext) -> None:
    if not ctx.guild:
        await ctx.respond("This command must be used in a server.")
        return
    links = storage.get_links(str(ctx.guild.id))
    if not links:
        await ctx.respond("No SOOP links configured.", ephemeral=True)
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
    await ctx.respond("\n".join(lines), ephemeral=True)


@bot.slash_command(name="link_list", description="List linked streamers with pagination")
async def link_list(
    ctx: discord.ApplicationContext,
    page: discord.Option(int, "Page number", required=False),
) -> None:
    if not ctx.guild:
        await ctx.respond("This command must be used in a server.")
        return
    links = storage.get_links(str(ctx.guild.id))
    if not links:
        await ctx.respond("No SOOP links configured.", ephemeral=True)
        return
    page = page or 1
    page_size = 10
    start = (page - 1) * page_size
    end = start + page_size
    slice_links = links[start:end]
    if not slice_links:
        await ctx.respond("No more links on that page.", ephemeral=True)
        return
    lines = [
        f"- `{item['soop_channel_id']}` -> <#{item['notify_channel_id']}>"
        for item in slice_links
    ]
    total_pages = (len(links) + page_size - 1) // page_size
    lines.append(f"Page {page}/{total_pages}")
    await ctx.respond("\n".join(lines), ephemeral=True)


@bot.slash_command(name="test", description="Send a test notification")
async def test(
    ctx: discord.ApplicationContext,
    soop_channel_id: discord.Option(str, "SOOP channel identifier", required=False),
) -> None:
    if not ctx.guild:
        await ctx.respond("This command must be used in a server.")
        return
    links = storage.get_links(str(ctx.guild.id))
    if not links:
        await ctx.respond("No SOOP links configured.", ephemeral=True)
        return
    target = None
    if soop_channel_id:
        target = next((item for item in links if item["soop_channel_id"] == soop_channel_id), None)
        if not target:
            await ctx.respond("That SOOP channel is not linked.", ephemeral=True)
            return
    else:
        target = links[0]
    channel = bot.get_channel(int(target["notify_channel_id"]))
    if not channel:
        await ctx.respond("Notify channel not found.", ephemeral=True)
        return
    await channel.send(
        f"\N{WHITE HEAVY CHECK MARK} Test notification for `{target['soop_channel_id']}`."
    )
    await ctx.respond("Sent test notification.", ephemeral=True)


@bot.slash_command(name="template", description="Manage notification templates")
async def template(
    ctx: discord.ApplicationContext,
    action: discord.Option(
        str,
        "Action",
        choices=["set", "clear", "list"],
        required=True,
    ),
    soop_channel_id: discord.Option(
        str,
        "SOOP channel identifier",
        required=False,
    ),
    message_template: discord.Option(
        str,
        "Template: {soop_channel_id}, {notify_channel}, {guild}, {soop_url}.",
        required=False,
    ),
) -> None:
    if not ctx.guild:
        await ctx.respond("This command must be used in a server.")
        return
    if action in {"set", "clear"} and not await _require_admin(ctx):
        return
    if action == "list":
        links = storage.get_links(str(ctx.guild.id))
        if not links:
            await ctx.respond("No SOOP links configured.", ephemeral=True)
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
        await ctx.respond("\n".join(lines), ephemeral=True)
        return

    if not soop_channel_id:
        await ctx.respond("Provide a SOOP channel id.", ephemeral=True)
        return

    if action == "clear":
        updated = storage.set_template(str(ctx.guild.id), soop_channel_id, None)
        if not updated:
            await ctx.respond("That SOOP channel is not linked.", ephemeral=True)
            return
        await ctx.respond("Template cleared.", ephemeral=True)
        return

    if not message_template:
        await ctx.respond("Provide a message template.", ephemeral=True)
        return

    updated = storage.set_template(str(ctx.guild.id), soop_channel_id, message_template)
    if not updated:
        await ctx.respond("That SOOP channel is not linked.", ephemeral=True)
        return
    await ctx.respond("Template updated.", ephemeral=True)


@bot.slash_command(name="default_channel", description="Set or clear default notify channel")
async def default_channel(
    ctx: discord.ApplicationContext,
    action: discord.Option(str, "Action", choices=["set", "clear"], required=True),
    channel: discord.Option(discord.TextChannel, "Channel", required=False),
) -> None:
    if not ctx.guild:
        await ctx.respond("This command must be used in a server.")
        return
    if not await _require_admin(ctx):
        return
    if action == "set":
        if not channel:
            await ctx.respond("Provide a channel to set.", ephemeral=True)
            return
        storage.set_default_notify_channel(str(ctx.guild.id), str(channel.id))
        await ctx.respond(f"Default channel set to {channel.mention}.", ephemeral=True)
        return
    storage.set_default_notify_channel(str(ctx.guild.id), None)
    await ctx.respond("Default channel cleared.", ephemeral=True)


@bot.slash_command(name="config", description="Show current guild configuration")
async def config(ctx: discord.ApplicationContext) -> None:
    if not ctx.guild:
        await ctx.respond("This command must be used in a server.")
        return
    if not await _require_admin(ctx):
        return
    default_channel = storage.get_default_notify_channel(str(ctx.guild.id))
    link_count = len(storage.get_links(str(ctx.guild.id)))
    lines = [
        f"Default channel: {f'<#{default_channel}>' if default_channel else 'None'}",
        f"Linked streamers: {link_count}",
        f"Poll interval: {settings.poll_interval_seconds}s",
        f"Queue size: {metrics.queue_size}",
    ]
    await ctx.respond("\n".join(lines), ephemeral=True)


@bot.slash_command(name="help", description="Show bot commands")
async def help_command(ctx: discord.ApplicationContext) -> None:
    lines = [
        "/link soop_channel:<id> [notify_channel:<#channel>]",
        "/unlink soop_channel:<id>",
        "/unlink_all",
        "/link_list [page:<n>]",
        "/status",
        "/test [soop_channel:<id>]",
        "/force_noti_gssspotted",
        "/template action:<set|clear|list> soop_channel:<id> message_template:<text>",
        "/default_channel action:<set|clear> channel:<#channel>",
        "/config",
    ]
    await ctx.respond("\n".join(lines), ephemeral=True)


@bot.slash_command(name="metrics", description="Show bot metrics")
async def metrics_command(ctx: discord.ApplicationContext) -> None:
    if not ctx.guild:
        await ctx.respond("This command must be used in a server.")
        return
    if not await _require_admin(ctx):
        return
    lines = [
        f"Messages sent: {metrics.messages_sent}",
        f"Messages failed: {metrics.messages_failed}",
        f"Queue size: {metrics.queue_size}",
        f"Last poll: {metrics.last_poll_duration_ms:.1f}ms",
        f"Poll count: {metrics.poll_count}",
    ]
    await ctx.respond("\n".join(lines), ephemeral=True)


@bot.slash_command(name="debug_live_status", description="Show live_status rows for this server")
async def debug_live_status(ctx: discord.ApplicationContext) -> None:
    if not ctx.guild:
        await ctx.respond("This command must be used in a server.")
        return
    if not await _require_admin(ctx):
        return
    rows = storage.load_live_status()
    prefix = f"{ctx.guild.id}:"
    filtered = {
        key[len(prefix) :]: value for key, value in rows.items() if key.startswith(prefix)
    }
    if not filtered:
        await ctx.respond("No live_status rows for this server.", ephemeral=True)
        return
    lines = [
        f"- `{streamer}` live={data.get('is_live')} broad_no={data.get('broad_no')}"
        for streamer, data in filtered.items()
    ]
    await ctx.respond("\n".join(lines), ephemeral=True)


def _render_template(
    template: str | None,
    soop_channel_id: str,
    notify_channel_id: int,
    guild_name: str,
    stream_url_base: str,
) -> str:
    soop_url = f"{stream_url_base.rstrip('/')}/{soop_channel_id}"
    if template:
        return (
            template.replace("{soop_channel_id}", soop_channel_id)
            .replace("{notify_channel}", f"<#{notify_channel_id}>")
            .replace("{guild}", guild_name)
            .replace("{soop_url}", soop_url)
        )
    return f"\N{LARGE RED CIRCLE} **Live Now** on SOOP: `{soop_channel_id}` {soop_url}"


def main() -> None:
    bot.run(settings.discord_token)


if __name__ == "__main__":
    main()
