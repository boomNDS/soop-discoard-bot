import asyncio
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

from soop_discord_bot.core.config import load_bot_settings
from soop_discord_bot.core.notifier import Notifier
from soop_discord_bot.core.storage import Storage
from soop_discord_bot.soop.client import SoopClient
from soop_discord_bot.soop.poller import SoopPoller


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
soop_client = SoopClient(
    settings.soop_api_base_url,
    settings.soop_client_id,
    settings.soop_max_pages,
)
notifier = Notifier(
    bot,
    settings.notify_rate_per_second,
    settings.notify_burst_rate_per_second,
    settings.notify_burst_threshold,
)
poller = SoopPoller(soop_client, storage, notifier, settings.poll_interval_seconds)


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


@bot.slash_command(name="link", description="Link this server to a SOOP channel")
async def link(
    ctx: discord.ApplicationContext,
    soop_channel_id: discord.Option(str, "SOOP channel identifier"),
    notify_channel: discord.Option(discord.TextChannel, "Discord channel for alerts"),
    message_template: discord.Option(
        str,
        "Optional template: {soop_channel_id}, {notify_channel}, {guild}.",
        required=False,
    ),
) -> None:
    if not ctx.guild:
        await ctx.respond("This command must be used in a server.")
        return
    storage.add_link(
        str(ctx.guild.id),
        soop_channel_id,
        str(notify_channel.id),
        message_template,
    )
    await ctx.respond(
        f"Linked SOOP `{soop_channel_id}` to {notify_channel.mention}.",
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
        "Template: {soop_channel_id}, {notify_channel}, {guild}.",
        required=False,
    ),
) -> None:
    if not ctx.guild:
        await ctx.respond("This command must be used in a server.")
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


def main() -> None:
    bot.run(settings.discord_token)


if __name__ == "__main__":
    main()
