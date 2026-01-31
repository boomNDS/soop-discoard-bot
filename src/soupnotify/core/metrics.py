import time
from dataclasses import dataclass, field


@dataclass
class BotMetrics:
    messages_sent: int = 0
    messages_failed: int = 0
    last_poll_duration_ms: float = 0.0
    last_poll_at: float | None = None
    poll_count: int = 0
    _queue_size: int = 0

    def record_poll(self, duration_ms: float) -> None:
        self.last_poll_duration_ms = duration_ms
        self.last_poll_at = time.time()
        self.poll_count += 1

    def record_sent(self) -> None:
        self.messages_sent += 1

    def record_failed(self) -> None:
        self.messages_failed += 1

    def set_queue_size(self, size: int) -> None:
        self._queue_size = size

    @property
    def queue_size(self) -> int:
        return self._queue_size
