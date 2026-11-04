"""Deterministic asynchronous retry primitives."""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from reliability_lab.exceptions import RequestTimeoutError, UpstreamServiceError

type AsyncOperation[T] = Callable[[], Awaitable[T]]
type AsyncSleep = Callable[[float], Awaitable[None]]
type RandomValue = Callable[[], float]
type RetryClassifier = Callable[[Exception], bool]
type MonotonicClock = Callable[[], float]
type OperationSafety = Literal["safe", "idempotent", "unsafe"]


class RateLimiter(Protocol):
    """The limiter behavior needed by resilient operation composition."""

    async def acquire(self, amount: float = 1.0) -> None:
        """Wait for and consume capacity."""


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    """Bounds and delay rules for one logical operation."""

    max_attempts: int = 3
    initial_delay: float = 0.1
    multiplier: float = 2.0
    max_delay: float = 5.0
    jitter_ratio: float = 0.0
    max_retry_after: float = 30.0
    max_elapsed_time: float | None = None

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")
        if self.initial_delay < 0:
            raise ValueError("initial_delay must not be negative")
        if self.multiplier < 1:
            raise ValueError("multiplier must be at least 1")
        if self.max_delay < 0:
            raise ValueError("max_delay must not be negative")
        if not 0 <= self.jitter_ratio <= 1:
            raise ValueError("jitter_ratio must be between 0 and 1")
        if self.max_retry_after < 0:
            raise ValueError("max_retry_after must not be negative")
        if self.max_elapsed_time is not None and self.max_elapsed_time <= 0:
            raise ValueError("max_elapsed_time must be positive")


@dataclass(frozen=True, slots=True)
class RetryAttempt:
    """One failed attempt and its delay before the next attempt."""

    attempt_number: int
    error: Exception
    delay_before_next: float | None


class RetryExhaustedError(Exception):
    """A retryable operation used every permitted attempt without succeeding."""

    def __init__(
        self,
        attempts: Sequence[RetryAttempt],
        *,
        reason: Literal["attempts", "elapsed_budget"] = "attempts",
    ) -> None:
        if not attempts:
            raise ValueError("attempts must not be empty")
        super().__init__(f"operation failed after {len(attempts)} attempts")
        self.attempts = tuple(attempts)
        self.last_error = attempts[-1].error
        self.reason = reason


def is_retryable_client_error(error: Exception) -> bool:
    """Classify transient failures currently exposed by ``OrderClient``."""

    if isinstance(error, RequestTimeoutError):
        return True
    if isinstance(error, UpstreamServiceError):
        return error.status_code is None or error.status_code == 429 or (
            500 <= error.status_code < 600
        )
    return False


async def retry_async[T](
    operation: AsyncOperation[T],
    *,
    policy: RetryPolicy,
    is_retryable: RetryClassifier = is_retryable_client_error,
    sleep: AsyncSleep = asyncio.sleep,
    random_value: RandomValue = random.random,
    clock: MonotonicClock = time.monotonic,
) -> T:
    """Run an async operation using bounded, testable retry behavior.

    Cancellation is not caught. A non-retryable error is raised unchanged. When
    all attempts fail transiently, ``RetryExhaustedError`` retains every failure
    and scheduled delay for diagnostics.
    """

    attempts: list[RetryAttempt] = []
    started_at = clock()

    for attempt_number in range(1, policy.max_attempts + 1):
        try:
            return await operation()
        except Exception as error:
            if not is_retryable(error):
                raise

            if attempt_number == policy.max_attempts:
                attempts.append(
                    RetryAttempt(
                        attempt_number=attempt_number,
                        error=error,
                        delay_before_next=None,
                    )
                )
                raise RetryExhaustedError(attempts) from error

            delay = _retry_delay(policy, attempt_number, random_value(), error)
            if (
                policy.max_elapsed_time is not None
                and clock() - started_at + delay > policy.max_elapsed_time
            ):
                attempts.append(
                    RetryAttempt(
                        attempt_number=attempt_number,
                        error=error,
                        delay_before_next=None,
                    )
                )
                raise RetryExhaustedError(
                    attempts, reason="elapsed_budget"
                ) from error
            attempts.append(
                RetryAttempt(
                    attempt_number=attempt_number,
                    error=error,
                    delay_before_next=delay,
                )
            )
            await sleep(delay)

    raise AssertionError("retry loop must return or raise")


async def execute_resiliently[T](
    operation: AsyncOperation[T],
    *,
    safety: OperationSafety,
    policy: RetryPolicy,
    limiter: RateLimiter | None = None,
    is_retryable: RetryClassifier = is_retryable_client_error,
    sleep: AsyncSleep = asyncio.sleep,
    random_value: RandomValue = random.random,
    clock: MonotonicClock = time.monotonic,
) -> T:
    """Rate-limit every physical attempt and retry only safe operations."""

    if safety not in ("safe", "idempotent", "unsafe"):
        raise ValueError("unknown operation safety")

    async def limited_attempt() -> T:
        if limiter is not None:
            await limiter.acquire()
        return await operation()

    if safety == "unsafe":
        return await limited_attempt()

    return await retry_async(
        limited_attempt,
        policy=policy,
        is_retryable=is_retryable,
        sleep=sleep,
        random_value=random_value,
        clock=clock,
    )


def _retry_delay(
    policy: RetryPolicy,
    failed_attempt: int,
    random_sample: float,
    error: Exception,
) -> float:
    if not 0 <= random_sample <= 1:
        raise ValueError("random_value must return a value between 0 and 1")

    base_delay = min(
        policy.initial_delay * policy.multiplier ** (failed_attempt - 1),
        policy.max_delay,
    )
    jitter_multiplier = 1 + policy.jitter_ratio * (2 * random_sample - 1)
    backoff_delay = base_delay * jitter_multiplier
    retry_after = (
        error.retry_after_seconds
        if isinstance(error, UpstreamServiceError)
        else None
    )
    if retry_after is None:
        return backoff_delay
    return max(backoff_delay, min(retry_after, policy.max_retry_after))
