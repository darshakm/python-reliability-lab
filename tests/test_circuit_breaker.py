from __future__ import annotations

import asyncio
from typing import Any

import pytest

from reliability_lab.circuit_breaker import (
    AsyncCircuitBreaker,
    CircuitOpenError,
    CircuitState,
    is_breaker_failure,
)
from reliability_lab.exceptions import (
    AuthenticationError,
    RequestTimeoutError,
    UpstreamServiceError,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


async def raise_error(error: Exception) -> None:
    raise error


def test_threshold_opens_and_rejects_without_calling_dependency() -> None:
    async def scenario() -> None:
        clock = FakeClock()
        breaker = AsyncCircuitBreaker(
            failure_threshold=2, recovery_timeout=10, clock=clock
        )
        calls = 0

        async def failing_operation() -> None:
            nonlocal calls
            calls += 1
            raise UpstreamServiceError("unavailable", status_code=503)

        for _ in range(2):
            with pytest.raises(UpstreamServiceError):
                await breaker.call(failing_operation)

        with pytest.raises(CircuitOpenError) as caught:
            await breaker.call(failing_operation)

        assert calls == 2
        assert caught.value.retry_after_seconds == 10
        snapshot = await breaker.snapshot()
        assert snapshot.state is CircuitState.OPEN
        assert snapshot.consecutive_failures == 2

    asyncio.run(scenario())


def test_successful_half_open_probe_closes_circuit() -> None:
    async def scenario() -> None:
        clock = FakeClock()
        breaker = AsyncCircuitBreaker(
            failure_threshold=1, recovery_timeout=5, clock=clock
        )

        with pytest.raises(RequestTimeoutError):
            await breaker.call(
                lambda: raise_error(RequestTimeoutError("timeout"))
            )
        clock.advance(5)

        assert await breaker.call(lambda: asyncio.sleep(0, result="ok")) == "ok"
        snapshot = await breaker.snapshot()
        assert snapshot.state is CircuitState.CLOSED
        assert snapshot.consecutive_failures == 0

    asyncio.run(scenario())


def test_failed_half_open_probe_reopens_from_probe_time() -> None:
    async def scenario() -> None:
        clock = FakeClock()
        breaker = AsyncCircuitBreaker(
            failure_threshold=1, recovery_timeout=5, clock=clock
        )

        with pytest.raises(RequestTimeoutError):
            await breaker.call(
                lambda: raise_error(RequestTimeoutError("first"))
            )
        clock.advance(5)
        with pytest.raises(RequestTimeoutError):
            await breaker.call(
                lambda: raise_error(RequestTimeoutError("probe"))
            )

        clock.advance(2)
        with pytest.raises(CircuitOpenError) as caught:
            await breaker.call(lambda: asyncio.sleep(0))
        assert caught.value.retry_after_seconds == 3

    asyncio.run(scenario())


def test_only_one_half_open_probe_runs_concurrently() -> None:
    async def scenario() -> None:
        clock = FakeClock()
        breaker = AsyncCircuitBreaker(
            failure_threshold=1, recovery_timeout=1, clock=clock
        )
        probe_started = asyncio.Event()
        release_probe = asyncio.Event()

        with pytest.raises(RequestTimeoutError):
            await breaker.call(
                lambda: raise_error(RequestTimeoutError("timeout"))
            )
        clock.advance(1)

        async def probe() -> str:
            probe_started.set()
            await release_probe.wait()
            return "recovered"

        active_probe = asyncio.create_task(breaker.call(probe))
        await probe_started.wait()
        with pytest.raises(CircuitOpenError):
            await breaker.call(lambda: asyncio.sleep(0, result="second"))

        release_probe.set()
        assert await active_probe == "recovered"

    asyncio.run(scenario())


def test_cancelled_probe_releases_probe_slot() -> None:
    async def scenario() -> None:
        clock = FakeClock()
        breaker = AsyncCircuitBreaker(
            failure_threshold=1, recovery_timeout=1, clock=clock
        )
        probe_started = asyncio.Event()

        with pytest.raises(RequestTimeoutError):
            await breaker.call(
                lambda: raise_error(RequestTimeoutError("timeout"))
            )
        clock.advance(1)

        async def blocking_probe() -> None:
            probe_started.set()
            await asyncio.Event().wait()

        probe = asyncio.create_task(breaker.call(blocking_probe))
        await probe_started.wait()
        probe.cancel()
        with pytest.raises(asyncio.CancelledError):
            await probe

        assert await breaker.call(lambda: asyncio.sleep(0, result="ok")) == "ok"

    asyncio.run(scenario())


def test_non_dependency_failure_does_not_increment_threshold() -> None:
    async def scenario() -> None:
        breaker = AsyncCircuitBreaker(
            failure_threshold=1, recovery_timeout=1
        )

        with pytest.raises(AuthenticationError):
            await breaker.call(
                lambda: raise_error(AuthenticationError("unauthorized"))
            )

        snapshot = await breaker.snapshot()
        assert snapshot.state is CircuitState.CLOSED
        assert snapshot.consecutive_failures == 0

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (RequestTimeoutError("timeout"), True),
        (UpstreamServiceError("network"), True),
        (UpstreamServiceError("server", status_code=503), True),
        (UpstreamServiceError("limited", status_code=429), False),
        (UpstreamServiceError("bad request", status_code=400), False),
        (AuthenticationError("unauthorized"), False),
    ],
)
def test_breaker_failure_classification(
    error: Exception, expected: bool
) -> None:
    assert is_breaker_failure(error) is expected


@pytest.mark.parametrize(
    "kwargs",
    [
        {"failure_threshold": 0, "recovery_timeout": 1},
        {"failure_threshold": 1, "recovery_timeout": 0},
    ],
)
def test_rejects_invalid_configuration(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        AsyncCircuitBreaker(**kwargs)
