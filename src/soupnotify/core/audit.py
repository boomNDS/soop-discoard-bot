import logging

from discord.ext import commands

from soupnotify.core.storage import Storage

logger = logging.getLogger(__name__)


async def send_audit(bot: commands.Bot, storage: Storage, guild_id: str, message: str) -> None:
    channel_id = storage.get_audit_channel(guild_id)
    if not channel_id:
        return
    channel = bot.get_channel(int(channel_id))
    if channel:
        try:
            await channel.send(message)
        except Exception:
            logger.exception("Failed to send audit log to %s", channel_id)
