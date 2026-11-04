"""Bounded asynchronous TTL/LRU cache with per-key stampede control."""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

type AsyncLoader[V] = Callable[[], Awaitable[V]]
type MonotonicClock = Callable[[], float]
type StaleFallbackPolicy = Callable[[Exception], bool]


def _never_serve_stale(error: Exception) -> bool:
    del error
    return False


@dataclass(frozen=True, slots=True)
class CacheSnapshot:
    """Inspectable cache statistics."""

    size: int
    in_flight_loads: int
    capacity: int


@dataclass(frozen=True, slots=True)
class _CacheEntry[V]:
    value: V
    expires_at: float
    stale_until: float


class AsyncTTLCache[K, V]:
    """Cache fresh values, coalesce misses, and optionally serve bounded stale data."""

    def __init__(
        self,
        *,
        capacity: int,
        ttl: float,
        stale_ttl: float = 0,
        clock: MonotonicClock = time.monotonic,
        can_serve_stale: StaleFallbackPolicy = _never_serve_stale,
    ) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        if ttl <= 0:
            raise ValueError("ttl must be positive")
        if stale_ttl < 0:
            raise ValueError("stale_ttl must not be negative")

        self._capacity = capacity
        self._ttl = ttl
        self._stale_ttl = stale_ttl
        self._clock = clock
        self._can_serve_stale = can_serve_stale
        self._entries: OrderedDict[K, _CacheEntry[V]] = OrderedDict()
        self._in_flight: dict[K, asyncio.Task[V]] = {}
        self._generations: dict[K, int] = {}
        self._lock = asyncio.Lock()

    async def get_or_load(self, key: K, loader: AsyncLoader[V]) -> V:
        """Return a fresh value or share one per-key background load."""

        async with self._lock:
            now = self._clock()
            entry = self._entries.get(key)
            if entry is not None and now < entry.expires_at:
                self._entries.move_to_end(key)
                return entry.value

            existing_load = self._in_flight.get(key)
            if existing_load is not None:
                load = existing_load
            else:
                generation = self._generations.get(key, 0)
                load = asyncio.create_task(
                    self._load_and_store(key, loader, entry, generation)
                )
                load.add_done_callback(_consume_task_exception)
                self._in_flight[key] = load

        return await asyncio.shield(load)

    async def invalidate(self, key: K) -> None:
        """Remove a key and prevent an older in-flight load from repopulating it."""

        async with self._lock:
            self._entries.pop(key, None)
            self._generations[key] = self._generations.get(key, 0) + 1

    async def clear(self) -> None:
        """Invalidate all cached and currently loading keys."""

        async with self._lock:
            keys = set(self._entries) | set(self._in_flight)
            self._entries.clear()
            for key in keys:
                self._generations[key] = self._generations.get(key, 0) + 1

    async def snapshot(self) -> CacheSnapshot:
        async with self._lock:
            return CacheSnapshot(
                size=len(self._entries),
                in_flight_loads=len(self._in_flight),
                capacity=self._capacity,
            )

    async def _load_and_store(
        self,
        key: K,
        loader: AsyncLoader[V],
        stale_entry: _CacheEntry[V] | None,
        generation: int,
    ) -> V:
        current_task = asyncio.current_task()
        try:
            try:
                value = await loader()
            except Exception as error:
                if await self._stale_value_allowed(
                    key, stale_entry, generation, error
                ):
                    assert stale_entry is not None
                    return stale_entry.value
                raise

            async with self._lock:
                if self._generations.get(key, 0) == generation:
                    now = self._clock()
                    self._entries[key] = _CacheEntry(
                        value=value,
                        expires_at=now + self._ttl,
                        stale_until=now + self._ttl + self._stale_ttl,
                    )
                    self._entries.move_to_end(key)
                    while len(self._entries) > self._capacity:
                        self._entries.popitem(last=False)
            return value
        finally:
            async with self._lock:
                if self._in_flight.get(key) is current_task:
                    self._in_flight.pop(key, None)

    async def _stale_value_allowed(
        self,
        key: K,
        stale_entry: _CacheEntry[V] | None,
        generation: int,
        error: Exception,
    ) -> bool:
        if stale_entry is None or not self._can_serve_stale(error):
            return False
        async with self._lock:
            return (
                self._generations.get(key, 0) == generation
                and self._clock() < stale_entry.stale_until
            )


def _consume_task_exception(task: asyncio.Task[object]) -> None:
    if not task.cancelled():
        task.exception()
