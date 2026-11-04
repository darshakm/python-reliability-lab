from __future__ import annotations

import asyncio

import pytest

from reliability_lab.cache import AsyncTTLCache
from reliability_lab.exceptions import AuthenticationError, UpstreamServiceError


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_fresh_value_avoids_duplicate_load() -> None:
    async def scenario() -> None:
        calls = 0
        cache: AsyncTTLCache[str, str] = AsyncTTLCache(capacity=2, ttl=10)

        async def load() -> str:
            nonlocal calls
            calls += 1
            return "value"

        assert await cache.get_or_load("key", load) == "value"
        assert await cache.get_or_load("key", load) == "value"
        assert calls == 1

    asyncio.run(scenario())


def test_expired_value_reloads() -> None:
    async def scenario() -> None:
        clock = FakeClock()
        cache: AsyncTTLCache[str, int] = AsyncTTLCache(
            capacity=2, ttl=5, clock=clock
        )
        calls = 0

        async def load() -> int:
            nonlocal calls
            calls += 1
            return calls

        assert await cache.get_or_load("key", load) == 1
        clock.advance(5)
        assert await cache.get_or_load("key", load) == 2

    asyncio.run(scenario())


def test_lru_access_controls_bounded_eviction() -> None:
    async def scenario() -> None:
        cache: AsyncTTLCache[str, str] = AsyncTTLCache(capacity=2, ttl=10)
        calls: dict[str, int] = {}

        def loader(key: str):  # type: ignore[no-untyped-def]
            async def load() -> str:
                calls[key] = calls.get(key, 0) + 1
                return key

            return load

        await cache.get_or_load("a", loader("a"))
        await cache.get_or_load("b", loader("b"))
        await cache.get_or_load("a", loader("a"))
        await cache.get_or_load("c", loader("c"))
        await cache.get_or_load("b", loader("b"))

        assert calls == {"a": 1, "b": 2, "c": 1}
        assert (await cache.snapshot()).size == 2

    asyncio.run(scenario())


def test_concurrent_misses_share_one_load() -> None:
    async def scenario() -> None:
        cache: AsyncTTLCache[str, str] = AsyncTTLCache(capacity=2, ttl=10)
        load_started = asyncio.Event()
        release_load = asyncio.Event()
        calls = 0

        async def load() -> str:
            nonlocal calls
            calls += 1
            load_started.set()
            await release_load.wait()
            return "value"

        tasks = [
            asyncio.create_task(cache.get_or_load("key", load))
            for _ in range(5)
        ]
        await load_started.wait()
        assert (await cache.snapshot()).in_flight_loads == 1
        release_load.set()

        assert await asyncio.gather(*tasks) == ["value"] * 5
        assert calls == 1

    asyncio.run(scenario())


def test_cancelled_waiter_does_not_cancel_shared_load() -> None:
    async def scenario() -> None:
        cache: AsyncTTLCache[str, str] = AsyncTTLCache(capacity=1, ttl=10)
        load_started = asyncio.Event()
        release_load = asyncio.Event()

        async def load() -> str:
            load_started.set()
            await release_load.wait()
            return "value"

        cancelled_waiter = asyncio.create_task(cache.get_or_load("key", load))
        surviving_waiter = asyncio.create_task(cache.get_or_load("key", load))
        await load_started.wait()
        cancelled_waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await cancelled_waiter

        release_load.set()
        assert await surviving_waiter == "value"

    asyncio.run(scenario())


def test_stale_fallback_is_bounded_and_failure_specific() -> None:
    async def scenario() -> None:
        clock = FakeClock()
        cache: AsyncTTLCache[str, str] = AsyncTTLCache(
            capacity=1,
            ttl=1,
            stale_ttl=5,
            clock=clock,
            can_serve_stale=lambda error: isinstance(
                error, UpstreamServiceError
            ),
        )

        async def initial_load() -> str:
            return "stale-value"

        async def unavailable() -> str:
            raise UpstreamServiceError("unavailable", status_code=503)

        async def unauthorized() -> str:
            raise AuthenticationError("unauthorized")

        await cache.get_or_load("key", initial_load)
        clock.advance(2)
        assert await cache.get_or_load("key", unavailable) == "stale-value"

        with pytest.raises(AuthenticationError):
            await cache.get_or_load("key", unauthorized)

        clock.advance(4)
        with pytest.raises(UpstreamServiceError):
            await cache.get_or_load("key", unavailable)

    asyncio.run(scenario())


def test_invalidation_prevents_in_flight_load_from_repopulating_cache() -> None:
    async def scenario() -> None:
        cache: AsyncTTLCache[str, str] = AsyncTTLCache(capacity=1, ttl=10)
        load_started = asyncio.Event()
        release_load = asyncio.Event()
        calls = 0

        async def load() -> str:
            nonlocal calls
            calls += 1
            load_started.set()
            await release_load.wait()
            return f"value-{calls}"

        first = asyncio.create_task(cache.get_or_load("key", load))
        await load_started.wait()
        await cache.invalidate("key")
        release_load.set()
        assert await first == "value-1"

        assert await cache.get_or_load("key", load) == "value-2"
        assert calls == 2

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"capacity": 0, "ttl": 1},
        {"capacity": 1, "ttl": 0},
        {"capacity": 1, "ttl": 1, "stale_ttl": -1},
    ],
)
def test_rejects_invalid_configuration(kwargs: dict[str, float | int]) -> None:
    with pytest.raises(ValueError):
        AsyncTTLCache[str, str](**kwargs)  # type: ignore[arg-type]
