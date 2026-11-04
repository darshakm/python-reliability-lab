"""Concurrent token-bucket rate limiting with injectable time."""

from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Awaitable, Callable

type AsyncSleep = Callable[[float], Awaitable[None]]
type MonotonicClock = Callable[[], float]


class AsyncTokenBucket:
    """Limit average request rate while allowing a bounded initial burst."""

    def __init__(
        self,
        *,
        rate: float,
        capacity: float,
        clock: MonotonicClock = time.monotonic,
        sleep: AsyncSleep = asyncio.sleep,
    ) -> None:
        if not math.isfinite(rate) or rate <= 0:
            raise ValueError("rate must be finite and positive")
        if not math.isfinite(capacity) or capacity <= 0:
            raise ValueError("capacity must be finite and positive")

        self._rate = rate
        self._capacity = capacity
        self._tokens = capacity
        self._clock = clock
        self._sleep = sleep
        self._updated_at = clock()
        self._lock = asyncio.Lock()

    async def acquire(self, amount: float = 1.0) -> None:
        """Wait until ``amount`` tokens are available, then consume them."""

        if not math.isfinite(amount) or amount <= 0:
            raise ValueError("amount must be finite and positive")
        if amount > self._capacity:
            raise ValueError("amount must not exceed bucket capacity")

        while True:
            async with self._lock:
                now = self._clock()
                if now < self._updated_at:
                    raise RuntimeError("monotonic clock moved backwards")
                elapsed = now - self._updated_at
                self._tokens = min(
                    self._capacity, self._tokens + elapsed * self._rate
                )
                self._updated_at = now

                if self._tokens >= amount:
                    self._tokens -= amount
                    return

                wait_time = (amount - self._tokens) / self._rate

            await self._sleep(wait_time)

    @property
    def available_tokens(self) -> float:
        """Return the last calculated token balance for diagnostics."""

        return self._tokens
