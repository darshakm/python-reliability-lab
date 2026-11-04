from __future__ import annotations

import asyncio

import pytest

from reliability_lab.exceptions import (
    AuthenticationError,
    RequestTimeoutError,
    UpstreamServiceError,
)
from reliability_lab.retry import (
    RetryExhaustedError,
    RetryPolicy,
    execute_resiliently,
    is_retryable_client_error,
    retry_async,
)


def test_retry_async_retries_transient_failures_then_returns() -> None:
    async def scenario() -> None:
        calls = 0
        delays: list[float] = []

        async def operation() -> str:
            nonlocal calls
            calls += 1
            if calls < 3:
                raise UpstreamServiceError("unavailable", status_code=503)
            return "ok"

        async def fake_sleep(delay: float) -> None:
            delays.append(delay)

        result = await retry_async(
            operation,
            policy=RetryPolicy(max_attempts=4, initial_delay=0.5),
            sleep=fake_sleep,
        )

        assert result == "ok"
        assert calls == 3
        assert delays == [0.5, 1.0]

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (RequestTimeoutError("timeout"), True),
        (UpstreamServiceError("network"), True),
        (UpstreamServiceError("rate limited", status_code=429), True),
        (UpstreamServiceError("bad gateway", status_code=502), True),
        (UpstreamServiceError("bad request", status_code=400), False),
        (AuthenticationError("unauthorized"), False),
        (ValueError("invalid data"), False),
    ],
)
def test_client_error_classification(error: Exception, expected: bool) -> None:
    assert is_retryable_client_error(error) is expected


def test_retry_async_raises_non_retryable_error_unchanged() -> None:
    async def scenario() -> None:
        error = AuthenticationError("unauthorized")

        async def operation() -> None:
            raise error

        with pytest.raises(AuthenticationError) as caught:
            await retry_async(operation, policy=RetryPolicy())

        assert caught.value is error

    asyncio.run(scenario())


def test_retry_async_records_attempt_history_when_exhausted() -> None:
    async def scenario() -> None:
        delays: list[float] = []

        async def operation() -> None:
            raise RequestTimeoutError("timeout")

        async def fake_sleep(delay: float) -> None:
            delays.append(delay)

        with pytest.raises(RetryExhaustedError) as caught:
            await retry_async(
                operation,
                policy=RetryPolicy(
                    max_attempts=3,
                    initial_delay=1,
                    multiplier=3,
                    max_delay=2,
                ),
                sleep=fake_sleep,
            )

        assert delays == [1, 2]
        assert [
            attempt.attempt_number for attempt in caught.value.attempts
        ] == [1, 2, 3]
        assert [
            attempt.delay_before_next for attempt in caught.value.attempts
        ] == [1, 2, None]
        assert isinstance(caught.value.last_error, RequestTimeoutError)

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("random_sample", "expected_delay"),
    [(0.0, 8.0), (0.5, 10.0), (1.0, 12.0)],
)
def test_retry_async_applies_bounded_deterministic_jitter(
    random_sample: float, expected_delay: float
) -> None:
    async def scenario() -> None:
        delays: list[float] = []
        calls = 0

        async def operation() -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RequestTimeoutError("timeout")

        async def fake_sleep(delay: float) -> None:
            delays.append(delay)

        await retry_async(
            operation,
            policy=RetryPolicy(
                max_attempts=2,
                initial_delay=10,
                max_delay=20,
                jitter_ratio=0.2,
            ),
            sleep=fake_sleep,
            random_value=lambda: random_sample,
        )

        assert delays == [expected_delay]

    asyncio.run(scenario())


def test_retry_async_propagates_cancellation_without_retrying() -> None:
    async def scenario() -> None:
        calls = 0

        async def operation() -> None:
            nonlocal calls
            calls += 1
            raise asyncio.CancelledError

        with pytest.raises(asyncio.CancelledError):
            await retry_async(operation, policy=RetryPolicy(max_attempts=3))

        assert calls == 1

    asyncio.run(scenario())


def test_retry_async_honors_bounded_retry_after() -> None:
    async def scenario() -> None:
        calls = 0
        delays: list[float] = []

        async def operation() -> None:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise UpstreamServiceError(
                    "rate limited",
                    status_code=429,
                    retry_after_seconds=20,
                )

        async def fake_sleep(delay: float) -> None:
            delays.append(delay)

        await retry_async(
            operation,
            policy=RetryPolicy(
                max_attempts=2,
                initial_delay=1,
                max_retry_after=5,
            ),
            sleep=fake_sleep,
        )

        assert delays == [5]

    asyncio.run(scenario())


def test_retry_async_stops_before_exceeding_elapsed_budget() -> None:
    async def scenario() -> None:
        slept = False

        async def operation() -> None:
            raise RequestTimeoutError("timeout")

        async def fake_sleep(delay: float) -> None:
            nonlocal slept
            slept = True

        with pytest.raises(RetryExhaustedError) as caught:
            await retry_async(
                operation,
                policy=RetryPolicy(
                    max_attempts=5,
                    initial_delay=2,
                    max_elapsed_time=1,
                ),
                sleep=fake_sleep,
                clock=lambda: 0,
            )

        assert caught.value.reason == "elapsed_budget"
        assert not slept
        assert len(caught.value.attempts) == 1

    asyncio.run(scenario())


def test_safe_composition_rate_limits_every_attempt() -> None:
    class FakeLimiter:
        def __init__(self) -> None:
            self.acquisitions = 0

        async def acquire(self, amount: float = 1.0) -> None:
            assert amount == 1
            self.acquisitions += 1

    async def scenario() -> None:
        calls = 0
        limiter = FakeLimiter()

        async def operation() -> str:
            nonlocal calls
            calls += 1
            if calls == 1:
                raise UpstreamServiceError("unavailable", status_code=503)
            return "ok"

        result = await execute_resiliently(
            operation,
            safety="safe",
            policy=RetryPolicy(max_attempts=2, initial_delay=0),
            limiter=limiter,
        )

        assert result == "ok"
        assert calls == 2
        assert limiter.acquisitions == 2

    asyncio.run(scenario())


def test_unsafe_operation_is_never_retried() -> None:
    async def scenario() -> None:
        calls = 0

        async def operation() -> None:
            nonlocal calls
            calls += 1
            raise UpstreamServiceError("unavailable", status_code=503)

        with pytest.raises(UpstreamServiceError):
            await execute_resiliently(
                operation,
                safety="unsafe",
                policy=RetryPolicy(max_attempts=5, initial_delay=0),
            )

        assert calls == 1

    asyncio.run(scenario())


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_attempts": 0},
        {"initial_delay": -1},
        {"multiplier": 0.5},
        {"max_delay": -1},
        {"jitter_ratio": -0.1},
        {"jitter_ratio": 1.1},
        {"max_retry_after": -1},
        {"max_elapsed_time": 0},
    ],
)
def test_retry_policy_rejects_invalid_configuration(
    kwargs: dict[str, float | int]
) -> None:
    with pytest.raises(ValueError):
        RetryPolicy(**kwargs)  # type: ignore[arg-type]
