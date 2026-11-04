from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from reliability_lab.cache import AsyncTTLCache
from reliability_lab.circuit_breaker import AsyncCircuitBreaker, CircuitState
from reliability_lab.exceptions import UpstreamServiceError
from reliability_lab.models import Order
from reliability_lab.resilient_reader import (
    ResilientOrderReader,
    can_serve_stale_order,
)
from reliability_lab.retry import RetryPolicy


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_order(order_id: str) -> Order:
    return Order(
        id=order_id,
        customer_id="cust_123",
        status="pending",
        amount=Decimal("10.00"),
        currency="USD",
        created_at=datetime(2026, 11, 3, tzinfo=UTC),
    )


def test_reader_cache_bypasses_dependency_and_invalidation_reloads() -> None:
    async def scenario() -> None:
        calls = 0

        async def fetch(order_id: str) -> Order:
            nonlocal calls
            calls += 1
            return make_order(order_id)

        cache: AsyncTTLCache[str, Order] = AsyncTTLCache(
            capacity=10, ttl=60
        )
        reader = ResilientOrderReader(
            fetch_order=fetch,
            cache=cache,
            circuit_breaker=AsyncCircuitBreaker(
                failure_threshold=2, recovery_timeout=10
            ),
            retry_policy=RetryPolicy(max_attempts=1),
        )

        await reader.get_order("ord_1")
        await reader.get_order("ord_1")
        assert calls == 1

        await reader.invalidate("ord_1")
        await reader.get_order("ord_1")
        assert calls == 2

    asyncio.run(scenario())


def test_reader_serves_stale_for_outage_and_open_circuit() -> None:
    async def scenario() -> None:
        clock = FakeClock()
        should_fail = False
        calls = 0

        async def fetch(order_id: str) -> Order:
            nonlocal calls
            calls += 1
            if should_fail:
                raise UpstreamServiceError("unavailable", status_code=503)
            return make_order(order_id)

        cache: AsyncTTLCache[str, Order] = AsyncTTLCache(
            capacity=10,
            ttl=1,
            stale_ttl=10,
            clock=clock,
            can_serve_stale=can_serve_stale_order,
        )
        breaker = AsyncCircuitBreaker(
            failure_threshold=1, recovery_timeout=10, clock=clock
        )
        reader = ResilientOrderReader(
            fetch_order=fetch,
            cache=cache,
            circuit_breaker=breaker,
            retry_policy=RetryPolicy(max_attempts=1),
        )

        fresh = await reader.get_order("ord_1")
        clock.advance(2)
        should_fail = True
        stale_after_failure = await reader.get_order("ord_1")
        stale_while_open = await reader.get_order("ord_1")

        assert stale_after_failure is fresh
        assert stale_while_open is fresh
        assert calls == 2
        assert (await breaker.snapshot()).state is CircuitState.OPEN

    asyncio.run(scenario())
