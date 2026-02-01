import asyncio
import logging
import time
from datetime import datetime

import discord

from soupnotify.core.embeds import build_live_embed
from soupnotify.core.metrics import BotMetrics
from soupnotify.core.notifier import Notifier
from soupnotify.core.rate_limit import GuildRateLimiter
from soupnotify.core.render import render_embed_overrides, render_message
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
        info_cooldown_seconds: int,
    ) -> None:
        self._client = client
        self._storage = storage
        self._notifier = notifier
        self._stream_url_base = stream_url_base.rstrip("/")
        self._interval = interval_seconds
        self._metrics = metrics
        self._last_live: dict[str, bool] = {}
        self._last_broad_no: dict[str, str | None] = {}
        self._info_cache: dict[str, dict] = {}
        self._info_cache_ts: dict[str, float] = {}
        self._info_cooldown = max(info_cooldown_seconds, 1)
        self._rate_limiter = GuildRateLimiter()
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
        info_map: dict[str, dict | None] = {}
        if target_ids:
            results = await asyncio.gather(
                *[self._get_broad_info(streamer_id) for streamer_id in target_ids],
                return_exceptions=True,
            )
            for streamer_id, result in zip(target_ids, results):
                if isinstance(result, Exception):
                    self._metrics.record_api_error()
                    logger.warning("SOOP info fetch failed for %s: %s", streamer_id, result)
                    info_map[streamer_id] = None
                else:
                    info_map[streamer_id] = result

        live_ids = {streamer_id for streamer_id, info in info_map.items() if info}
        empty_count = sum(1 for info in info_map.values() if not info)
        if empty_count:
            self._metrics.record_empty_response(empty_count)

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
                info = info_map.get(soop_channel_id)
                broad_no = str(info.get("broadNo")) if info and info.get("broadNo") else None

            should_notify = is_live and not was_live
            rate_limit = self._storage.get_rate_limit(guild_id)
            if should_notify and not self._rate_limiter.allow(guild_id, rate_limit):
                should_notify = False

            if should_notify:
                guild = bot.get_guild(int(guild_id)) if guild_id.isdigit() else None
                template = link.get("message_template")
                mention = _mention_text(self._storage.get_mention(guild_id))
                message = render_message(
                    template,
                    soop_channel_id,
                    notify_channel_id,
                    guild.name if guild else guild_id,
                    self._stream_url_base,
                    mention,
                )
                stream_url = f"{self._stream_url_base}/{soop_channel_id}"
                thumbnail_url = _thumbnail_url(self._client, info)
                embed_settings = self._storage.get_embed_template(guild_id)
                title_override, description_override, color_override = render_embed_overrides(
                    embed_settings,
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
                    color_hex=color_override,
                )
                view = _watch_view(stream_url)
                await self._notifier.enqueue(notify_channel_id, message, embed=embed, view=view)
                last_notified_at = datetime.utcnow().isoformat()
            self._last_live[key] = is_live
            self._last_broad_no[key] = broad_no
            self._storage.set_live_status(
                guild_id,
                soop_channel_id,
                is_live,
                broad_no,
                last_notified_at if should_notify else None,
            )
        duration_ms = (time.perf_counter() - start) * 1000
        self._metrics.record_poll(duration_ms, len(live_ids))
        self._metrics.record_live_detected(len(live_ids))
        logger.info(
            "Poll summary: links=%s live=%s empty=%s duration_ms=%.1f",
            len(links),
            len(live_ids),
            empty_count,
            duration_ms,
        )
        self._storage.set_poll_state("last_poll_at", datetime.utcnow().isoformat())

    async def _get_broad_info(self, streamer_id: str) -> dict | None:
        now = time.time()
        cached = self._info_cache.get(streamer_id)
        last_fetch = self._info_cache_ts.get(streamer_id, 0.0)
        if cached and now - last_fetch < self._info_cooldown:
            self._metrics.record_cache_hit()
            return cached
        self._metrics.record_cache_miss()
        info = await self._client.fetch_broad_info(streamer_id)
        if info:
            self._info_cache[streamer_id] = info
            self._info_cache_ts[streamer_id] = now
        return info


def _thumbnail_url(client: SoopClient, info: dict | None) -> str | None:
    if not info:
        return None
    return client.build_thumbnail_url(info.get("broadNo"))


def _mention_text(mention: dict[str, str | None]) -> str | None:
    mention_type = mention.get("type")
    value = mention.get("value")
    if mention_type == "everyone":
        return "@everyone"
    if mention_type == "role" and value:
        return f"<@&{value}>"
    return None


def _watch_view(stream_url: str) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    view.add_item(
        discord.ui.Button(label="Watch Stream", style=discord.ButtonStyle.link, url=stream_url)
    )
    return view
