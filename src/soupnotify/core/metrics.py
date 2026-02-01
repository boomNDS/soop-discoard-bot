from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class BotMetrics:
    messages_sent: int = 0
    messages_failed: int = 0
    api_errors: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    last_poll_duration_ms: float = 0.0
    last_poll_at: float | None = None
    poll_count: int = 0
    last_live_count: int = 0
    live_detected: int = 0
    empty_responses: int = 0
    last_empty_count: int = 0
    _queue_size: int = 0

    def record_poll(self, duration_ms: float, live_count: int) -> None:
        self.last_poll_duration_ms = duration_ms
        self.last_poll_at = time.time()
        self.poll_count += 1
        self.last_live_count = live_count
        self.last_empty_count = 0

    def record_live_detected(self, count: int) -> None:
        self.live_detected += count

    def record_empty_response(self, count: int = 1) -> None:
        self.empty_responses += count
        self.last_empty_count = count

    def record_sent(self) -> None:
        self.messages_sent += 1

    def record_failed(self) -> None:
        self.messages_failed += 1

    def record_api_error(self) -> None:
        self.api_errors += 1

    def record_cache_hit(self) -> None:
        self.cache_hits += 1

    def record_cache_miss(self) -> None:
        self.cache_misses += 1

    def set_queue_size(self, size: int) -> None:
        self._queue_size = size

    @property
    def queue_size(self) -> int:
        return self._queue_size
