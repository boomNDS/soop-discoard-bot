import asyncio
import logging

import discord

from soop_discord_bot.core.notifier import Notifier
from soop_discord_bot.core.storage import Storage
from soop_discord_bot.soop.client import SoopClient


logger = logging.getLogger(__name__)


class SoopPoller:
    def __init__(
        self,
        client: SoopClient,
        storage: Storage,
        notifier: Notifier,
        interval_seconds: int,
    ) -> None:
        self._client = client
        self._storage = storage
        self._notifier = notifier
        self._interval = interval_seconds
        self._last_live: dict[str, bool] = {}

    async def run(self, bot: discord.Bot) -> None:
        while True:
            try:
                await self._poll_once(bot)
            except Exception:
                logger.exception("SOOP poller failed")
            await asyncio.sleep(self._interval)

    async def _poll_once(self, bot: discord.Bot) -> None:
        links = self._storage.list_links()
        target_ids = {link["soop_channel_id"] for link in links}
        try:
            live_ids = await self._client.fetch_live_user_ids(target_ids)
        except Exception:
            logger.exception("Failed to fetch SOOP live list")
            return

        for link in links:
            guild_id = link["guild_id"]
            soop_channel_id = link["soop_channel_id"]
            notify_channel_id = int(link["notify_channel_id"])
            key = f"{guild_id}:{soop_channel_id}"

            is_live = soop_channel_id in live_ids

            was_live = self._last_live.get(key, False)
            if is_live and not was_live:
                guild = bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
                template = link.get("message_template")
                message = _render_message(
                    template,
                    soop_channel_id,
                    notify_channel_id,
                    guild.name if guild else guild_id,
                )
                await self._notifier.enqueue(notify_channel_id, message)
            self._last_live[key] = is_live


def _render_message(
    template: str | None,
    soop_channel_id: str,
    notify_channel_id: int,
    guild_name: str,
) -> str:
    if template:
        return (
            template.replace("{soop_channel_id}", soop_channel_id)
            .replace("{notify_channel}", f"<#{notify_channel_id}>")
            .replace("{guild}", guild_name)
        )
    return f"\N{LARGE RED CIRCLE} **Live Now** on SOOP: `{soop_channel_id}`"
