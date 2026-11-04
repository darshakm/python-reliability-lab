from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from reliability_lab.cache import AsyncTTLCache
from reliability_lab.circuit_breaker import AsyncCircuitBreaker, CircuitState
from reliability_lab.exceptions import (
    AuthenticationError,
    UpstreamServiceError,
)
from reliability_lab.integration_harness import (
    InMemoryTraceRecorder,
    ScriptedOrderSource,
    ScriptedResponse,
    TracedOrderReader,
)
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
        customer_id="cust_integration",
        status="pending",
        amount=Decimal("25.00"),
        currency="USD",
        created_at=datetime(2026, 11, 3, tzinfo=UTC),
    )


def make_reader(
    source: ScriptedOrderSource,
    *,
    cache: AsyncTTLCache[str, Order] | None = None,
    breaker: AsyncCircuitBreaker | None = None,
    retry_policy: RetryPolicy | None = None,
) -> ResilientOrderReader:
    return ResilientOrderReader(
        fetch_order=source.fetch,
        cache=cache or AsyncTTLCache(capacity=10, ttl=60),
        circuit_breaker=breaker
        or AsyncCircuitBreaker(failure_threshold=2, recovery_timeout=10),
        retry_policy=retry_policy
        or RetryPolicy(max_attempts=2, initial_delay=0),
    )


def test_transient_outage_recovers_then_cache_avoids_dependency() -> None:
    async def scenario() -> None:
        order = make_order("ord_1")
        source = ScriptedOrderSource(
            {
                "ord_1": [
                    ScriptedResponse(
                        UpstreamServiceError("unavailable", status_code=503)
                    ),
                    ScriptedResponse(order),
                ]
            }
        )
        reader = make_reader(source)

        assert await reader.get_order("ord_1") is order
        assert await reader.get_order("ord_1") is order
        assert source.attempts == {"ord_1": 2}
        assert [item.outcome for item in source.observations] == [
            "UpstreamServiceError",
            "success",
        ]

    asyncio.run(scenario())


def test_sustained_outage_opens_circuit_and_serves_stale() -> None:
    async def scenario() -> None:
        clock = FakeClock()
        order = make_order("ord_1")
        source = ScriptedOrderSource(
            {
                "ord_1": [
                    ScriptedResponse(order),
                    ScriptedResponse(
                        UpstreamServiceError("unavailable", status_code=503)
                    ),
                ]
            }
        )
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
        reader = make_reader(
            source,
            cache=cache,
            breaker=breaker,
            retry_policy=RetryPolicy(max_attempts=1),
        )

        assert await reader.get_order("ord_1") is order
        clock.advance(2)
        assert await reader.get_order("ord_1") is order
        assert await reader.get_order("ord_1") is order
        assert source.attempts == {"ord_1": 2}
        assert (await breaker.snapshot()).state is CircuitState.OPEN

    asyncio.run(scenario())


def test_concurrent_cache_misses_make_one_dependency_call() -> None:
    async def scenario() -> None:
        order = make_order("ord_1")
        source = ScriptedOrderSource(
            {"ord_1": [ScriptedResponse(order, delay=0.01)]}
        )
        reader = make_reader(source)

        results = await asyncio.gather(
            *(reader.get_order("ord_1") for _ in range(10))
        )

        assert results == [order] * 10
        assert source.attempts == {"ord_1": 1}
        assert source.peak_active_requests == 1

    asyncio.run(scenario())


def test_trace_correlates_logical_failure_without_sensitive_data() -> None:
    async def scenario() -> None:
        source = ScriptedOrderSource(
            {
                "ord_1": [
                    ScriptedResponse(AuthenticationError("unauthorized"))
                ]
            }
        )
        recorder = InMemoryTraceRecorder()
        reader = TracedOrderReader(make_reader(source), recorder)

        with pytest.raises(AuthenticationError):
            await reader.get_order("ord_1", trace_id="trace-123")

        assert [event.event for event in recorder.events] == [
            "started",
            "failed",
        ]
        assert all(event.trace_id == "trace-123" for event in recorder.events)
        assert all(
            item.trace_id == "trace-123" for item in source.observations
        )
        assert recorder.events[-1].error_type == "AuthenticationError"
        assert "unauthorized" not in repr(recorder.events)

    asyncio.run(scenario())
