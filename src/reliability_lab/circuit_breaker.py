"""Concurrent asynchronous circuit breaker with explicit state transitions."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum

from reliability_lab.exceptions import (
    ReliabilityLabError,
    RequestTimeoutError,
    UpstreamServiceError,
)
from reliability_lab.retry import RetryExhaustedError

type AsyncOperation[T] = Callable[[], Awaitable[T]]
type FailureClassifier = Callable[[Exception], bool]
type MonotonicClock = Callable[[], float]


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass(frozen=True, slots=True)
class CircuitBreakerSnapshot:
    """Inspectable circuit state without exposing mutable internals."""

    state: CircuitState
    consecutive_failures: int
    opened_at: float | None
    probe_in_flight: bool


class CircuitOpenError(ReliabilityLabError):
    """The circuit rejected an operation without calling the dependency."""

    def __init__(self, *, retry_after_seconds: float | None) -> None:
        super().__init__("dependency circuit is open")
        self.retry_after_seconds = retry_after_seconds


def is_breaker_failure(error: Exception) -> bool:
    """Count dependency availability failures, not caller or capacity errors."""

    if isinstance(error, RetryExhaustedError):
        return is_breaker_failure(error.last_error)
    if isinstance(error, RequestTimeoutError):
        return True
    if isinstance(error, UpstreamServiceError):
        return error.status_code is None or (
            error.status_code != 429 and 500 <= error.status_code < 600
        )
    return False


class AsyncCircuitBreaker:
    """Protect a dependency after repeated availability failures."""

    def __init__(
        self,
        *,
        failure_threshold: int,
        recovery_timeout: float,
        clock: MonotonicClock = time.monotonic,
        is_failure: FailureClassifier = is_breaker_failure,
    ) -> None:
        if failure_threshold < 1:
            raise ValueError("failure_threshold must be at least 1")
        if recovery_timeout <= 0:
            raise ValueError("recovery_timeout must be positive")

        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._clock = clock
        self._is_failure = is_failure
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._opened_at: float | None = None
        self._probe_in_flight = False
        self._lock = asyncio.Lock()

    async def call[T](self, operation: AsyncOperation[T]) -> T:
        """Execute an operation when permitted by the current circuit state."""

        is_probe = await self._before_call()
        try:
            result = await operation()
        except asyncio.CancelledError:
            if is_probe:
                await self._release_cancelled_probe()
            raise
        except Exception as error:
            await self._record_failure(error, is_probe=is_probe)
            raise
        else:
            await self._record_success(is_probe=is_probe)
            return result

    async def snapshot(self) -> CircuitBreakerSnapshot:
        """Return a consistent view of the state for telemetry and tests."""

        async with self._lock:
            return CircuitBreakerSnapshot(
                state=self._state,
                consecutive_failures=self._consecutive_failures,
                opened_at=self._opened_at,
                probe_in_flight=self._probe_in_flight,
            )

    async def _before_call(self) -> bool:
        async with self._lock:
            now = self._clock()
            if self._state is CircuitState.OPEN:
                assert self._opened_at is not None
                elapsed = now - self._opened_at
                if elapsed < self._recovery_timeout:
                    raise CircuitOpenError(
                        retry_after_seconds=self._recovery_timeout - elapsed
                    )
                self._state = CircuitState.HALF_OPEN
                self._probe_in_flight = False

            if self._state is CircuitState.HALF_OPEN:
                if self._probe_in_flight:
                    raise CircuitOpenError(retry_after_seconds=None)
                self._probe_in_flight = True
                return True

            return False

    async def _record_failure(self, error: Exception, *, is_probe: bool) -> None:
        async with self._lock:
            if is_probe:
                self._probe_in_flight = False
            if not self._is_failure(error):
                return

            if self._state is CircuitState.HALF_OPEN:
                self._open()
                return

            self._consecutive_failures += 1
            if self._consecutive_failures >= self._failure_threshold:
                self._open()

    async def _record_success(self, *, is_probe: bool) -> None:
        async with self._lock:
            if is_probe:
                self._probe_in_flight = False
                self._state = CircuitState.CLOSED
                self._opened_at = None
            self._consecutive_failures = 0

    async def _release_cancelled_probe(self) -> None:
        async with self._lock:
            self._probe_in_flight = False

    def _open(self) -> None:
        self._state = CircuitState.OPEN
        self._opened_at = self._clock()
        self._consecutive_failures = self._failure_threshold
        self._probe_in_flight = False
