from __future__ import annotations

import time
from collections import deque


class GuildRateLimiter:
    def __init__(self) -> None:
        self._events: dict[str, deque[float]] = {}

    def allow(self, guild_id: str, limit_per_min: int | None) -> bool:
        if not limit_per_min or limit_per_min <= 0:
            return True
        now = time.monotonic()
        window = 60.0
        queue = self._events.setdefault(guild_id, deque())
        while queue and now - queue[0] > window:
            queue.popleft()
        if len(queue) >= limit_per_min:
            return False
        queue.append(now)
        return True
