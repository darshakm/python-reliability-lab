"""Demonstrate retry recovery followed by a cache hit."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from reliability_lab import (
    AsyncCircuitBreaker,
    AsyncTTLCache,
    Order,
    ResilientOrderReader,
    RetryPolicy,
    ScriptedOrderSource,
    ScriptedResponse,
    UpstreamServiceError,
)


async def main() -> None:
    order = Order(
        id="ord_123",
        customer_id="cust_456",
        status="pending",
        amount=Decimal("25.00"),
        currency="USD",
        created_at=datetime(2026, 11, 3, tzinfo=UTC),
    )
    source = ScriptedOrderSource(
        {
            order.id: [
                ScriptedResponse(
                    UpstreamServiceError("synthetic outage", status_code=503)
                ),
                ScriptedResponse(order),
            ]
        }
    )
    reader = ResilientOrderReader(
        fetch_order=source.fetch,
        cache=AsyncTTLCache(capacity=10, ttl=60),
        circuit_breaker=AsyncCircuitBreaker(
            failure_threshold=2, recovery_timeout=5
        ),
        retry_policy=RetryPolicy(max_attempts=2, initial_delay=0),
    )

    recovered = await reader.get_order(order.id)
    cached = await reader.get_order(order.id)
    print(
        f"recovered={recovered.id} attempts={source.attempts[order.id]} "
        f"cache_hit={cached is recovered}"
    )


if __name__ == "__main__":
    asyncio.run(main())
