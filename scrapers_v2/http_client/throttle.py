"""Token bucket rate limiter for polite scraping."""
from __future__ import annotations

import asyncio
import time


class TokenBucket:
    """Async token bucket: allows up to `rate` requests per second with burst `capacity`.

    Usage:
        bucket = TokenBucket(rate=10, capacity=10)
        await bucket.acquire()
        # ... make request
    """

    def __init__(self, rate: float = 10.0, capacity: float | None = None) -> None:
        self.rate = float(rate)
        self.capacity = float(capacity if capacity is not None else rate)
        self._tokens = self.capacity
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        """Block until `tokens` are available."""
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._last_refill
                self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
                self._last_refill = now
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return
                deficit = tokens - self._tokens
                sleep_for = deficit / self.rate
                # release lock while sleeping so other tasks can try
                await asyncio.sleep(sleep_for)
