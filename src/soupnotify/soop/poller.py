import asyncio
import logging
import time

import discord

from soupnotify.core.embeds import build_live_embed
from soupnotify.core.metrics import BotMetrics
from soupnotify.core.notifier import Notifier
from soupnotify.core.storage import Storage
from soupnotify.soop.client import SoopClient


logger = logging.getLogger(__name__)


class SoopPoller:
    def __init__(
        self,
        client: SoopClient,
        storage: Storage,
        notifier: Notifier,
        stream_url_base: str,
        metrics: BotMetrics,
        interval_seconds: int,
    ) -> None:
        self._client = client
        self._storage = storage
        self._notifier = notifier
        self._stream_url_base = stream_url_base.rstrip("/")
        self._interval = interval_seconds
        self._metrics = metrics
        self._last_live: dict[str, bool] = {}
        self._last_broad_no: dict[str, str | None] = {}
        for key, status in self._storage.load_live_status().items():
            self._last_live[key] = bool(status.get("is_live"))
            self._last_broad_no[key] = status.get("broad_no")  # type: ignore[assignment]

    async def run(self, bot: discord.Bot) -> None:
        while True:
            try:
                await self._poll_once(bot)
            except Exception:
                logger.exception("SOOP poller failed")
            await asyncio.sleep(self._interval)

    async def _poll_once(self, bot: discord.Bot) -> None:
        start = time.perf_counter()
        links = self._storage.list_links()
        active_keys = {f"{link['guild_id']}:{link['soop_channel_id']}" for link in links}
        self._storage.prune_live_status(active_keys)
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
            prev_broad_no = self._last_broad_no.get(key)

            info = None
            broad_no = None
            if is_live:
                info = await self._client.fetch_broad_info(soop_channel_id)
                broad_no = str(info.get("broadNo")) if info and info.get("broadNo") else None

            should_notify = is_live and (
                not was_live or (broad_no is not None and broad_no != prev_broad_no)
            )

            if should_notify:
                guild = bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
                template = link.get("message_template")
                message = _render_message(
                    template,
                    soop_channel_id,
                    notify_channel_id,
                    guild.name if guild else guild_id,
                    self._stream_url_base,
                )
                stream_url = f"{self._stream_url_base}/{soop_channel_id}"
                thumbnail_url = _thumbnail_url(self._client, info)
                embed_settings = self._storage.get_embed_template(guild_id)
                title_override = _render_template_value(
                    embed_settings.get("title"),
                    soop_channel_id,
                    notify_channel_id,
                    guild.name if guild else guild_id,
                    self._stream_url_base,
                )
                description_override = _render_template_value(
                    embed_settings.get("description"),
                    soop_channel_id,
                    notify_channel_id,
                    guild.name if guild else guild_id,
                    self._stream_url_base,
                )
                embed = build_live_embed(
                    soop_channel_id,
                    stream_url,
                    info,
                    thumbnail_url,
                    title_override=title_override,
                    description_override=description_override,
                    color_hex=embed_settings.get("color"),
                )
                await self._notifier.enqueue(notify_channel_id, message, embed=embed)
            self._last_live[key] = is_live
            self._last_broad_no[key] = broad_no
            self._storage.set_live_status(guild_id, soop_channel_id, is_live, broad_no)
        duration_ms = (time.perf_counter() - start) * 1000
        self._metrics.record_poll(duration_ms)


def _render_message(
    template: str | None,
    soop_channel_id: str,
    notify_channel_id: int,
    guild_name: str,
    stream_url_base: str,
) -> str:
    soop_url = f"{stream_url_base}/{soop_channel_id}"
    if template:
        return (
            template.replace("{soop_channel_id}", soop_channel_id)
            .replace("{notify_channel}", f"<#{notify_channel_id}>")
            .replace("{guild}", guild_name)
            .replace("{soop_url}", soop_url)
        )
    return f"\N{LARGE RED CIRCLE} **Live Now** on SOOP: `{soop_channel_id}` {soop_url}"


def _render_template_value(
    template: str | None,
    soop_channel_id: str,
    notify_channel_id: int,
    guild_name: str,
    stream_url_base: str,
) -> str | None:
    if not template:
        return None
    soop_url = f"{stream_url_base}/{soop_channel_id}"
    return (
        template.replace("{soop_channel_id}", soop_channel_id)
        .replace("{notify_channel}", f"<#{notify_channel_id}>")
        .replace("{guild}", guild_name)
        .replace("{soop_url}", soop_url)
    )


def _thumbnail_url(client: SoopClient, info: dict | None) -> str | None:
    if not info:
        return None
    return client.build_thumbnail_url(info.get("broadNo"))
