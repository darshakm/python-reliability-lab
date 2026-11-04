"""Composition of cache, circuit breaker, retries, rate limiting, and fetch."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from reliability_lab.cache import AsyncTTLCache
from reliability_lab.circuit_breaker import (
    AsyncCircuitBreaker,
    CircuitOpenError,
    is_breaker_failure,
)
from reliability_lab.models import Order
from reliability_lab.rate_limit import AsyncTokenBucket
from reliability_lab.retry import (
    RetryExhaustedError,
    RetryPolicy,
    execute_resiliently,
)

type AsyncOrderFetcher = Callable[[str], Awaitable[Order]]


def can_serve_stale_order(error: Exception) -> bool:
    """Allow stale data only for dependency availability failures."""

    if isinstance(error, CircuitOpenError):
        return True
    if isinstance(error, RetryExhaustedError):
        return is_breaker_failure(error.last_error)
    return is_breaker_failure(error)


class ResilientOrderReader:
    """Read-through order cache with layered dependency protection."""

    def __init__(
        self,
        *,
        fetch_order: AsyncOrderFetcher,
        cache: AsyncTTLCache[str, Order],
        circuit_breaker: AsyncCircuitBreaker,
        retry_policy: RetryPolicy,
        rate_limiter: AsyncTokenBucket | None = None,
    ) -> None:
        self._fetch_order = fetch_order
        self._cache = cache
        self._circuit_breaker = circuit_breaker
        self._retry_policy = retry_policy
        self._rate_limiter = rate_limiter

    async def get_order(self, order_id: str) -> Order:
        """Return a cached order or execute the protected dependency call."""

        async def load() -> Order:
            async def logical_operation() -> Order:
                return await execute_resiliently(
                    lambda: self._fetch_order(order_id),
                    safety="safe",
                    policy=self._retry_policy,
                    limiter=self._rate_limiter,
                )

            return await self._circuit_breaker.call(logical_operation)

        return await self._cache.get_or_load(order_id, load)

    async def invalidate(self, order_id: str) -> None:
        """Invalidate an order after a known write or freshness event."""

        await self._cache.invalidate(order_id)
