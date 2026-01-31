import asyncio
import logging
from dataclasses import dataclass

import discord


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotifyMessage:
    channel_id: int
    content: str


class Notifier:
    def __init__(
        self,
        bot: discord.Bot,
        rate_per_second: float,
        burst_rate_per_second: float,
        burst_threshold: int,
        max_queue: int = 1000,
    ) -> None:
        self._bot = bot
        self._queue: asyncio.Queue[NotifyMessage] = asyncio.Queue(maxsize=max_queue)
        self._base_delay = 1.0 / max(rate_per_second, 0.1)
        self._burst_delay = 1.0 / max(burst_rate_per_second, 0.1)
        self._burst_threshold = max(burst_threshold, 1)
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._worker())

    async def enqueue(self, channel_id: int, content: str) -> None:
        try:
            self._queue.put_nowait(NotifyMessage(channel_id=channel_id, content=content))
        except asyncio.QueueFull:
            logger.warning("Notification queue is full; dropping message for %s", channel_id)

    async def _worker(self) -> None:
        while True:
            message = await self._queue.get()
            channel = self._bot.get_channel(message.channel_id)
            if channel:
                try:
                    await channel.send(message.content)
                except Exception:
                    logger.exception("Failed to send notification to %s", message.channel_id)
            delay = self._burst_delay if self._queue.qsize() >= self._burst_threshold else self._base_delay
            await asyncio.sleep(delay)
