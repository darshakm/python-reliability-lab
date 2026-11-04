"""Deterministic dependency and trace harness for integration experiments."""

from __future__ import annotations

import asyncio
import contextvars
from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from reliability_lab.models import Order
from reliability_lab.resilient_reader import ResilientOrderReader

_TRACE_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "reliability_lab_trace_id", default=None
)


@dataclass(frozen=True, slots=True)
class ScriptedResponse:
    """One deterministic dependency result with optional simulated latency."""

    result: Order | Exception
    delay: float = 0

    def __post_init__(self) -> None:
        if self.delay < 0:
            raise ValueError("delay must not be negative")


@dataclass(frozen=True, slots=True)
class DependencyObservation:
    trace_id: str | None
    order_id: str
    attempt_number: int
    active_requests: int
    outcome: str


class ScriptedOrderSource:
    """An async order dependency driven by finite per-order response scripts."""

    def __init__(
        self,
        scripts: Mapping[str, Sequence[ScriptedResponse]],
        *,
        observation_capacity: int = 10_000,
    ) -> None:
        if observation_capacity < 1:
            raise ValueError("observation_capacity must be at least 1")
        self._scripts = {
            order_id: deque(responses)
            for order_id, responses in scripts.items()
        }
        if any(not responses for responses in self._scripts.values()):
            raise ValueError("every order script must contain a response")
        self._attempts: dict[str, int] = defaultdict(int)
        self._active_requests = 0
        self._peak_active_requests = 0
        self._observations: deque[DependencyObservation] = deque(
            maxlen=observation_capacity
        )
        self._lock = asyncio.Lock()

    async def fetch(self, order_id: str) -> Order:
        async with self._lock:
            script = self._scripts.get(order_id)
            if script is None or not script:
                raise AssertionError(f"no scripted response remains for {order_id!r}")
            response = script.popleft()
            if not script:
                self._scripts.pop(order_id, None)
            self._attempts[order_id] += 1
            attempt_number = self._attempts[order_id]
            self._active_requests += 1
            self._peak_active_requests = max(
                self._peak_active_requests, self._active_requests
            )
            active_requests = self._active_requests

        outcome = "cancelled"
        try:
            if response.delay:
                await asyncio.sleep(response.delay)
            if isinstance(response.result, Exception):
                raise response.result
            outcome = "success"
            return response.result
        except Exception as error:
            outcome = type(error).__name__
            raise
        finally:
            async with self._lock:
                self._observations.append(
                    DependencyObservation(
                        trace_id=_TRACE_ID.get(),
                        order_id=order_id,
                        attempt_number=attempt_number,
                        active_requests=active_requests,
                        outcome=outcome,
                    )
                )
                self._active_requests -= 1

    @property
    def attempts(self) -> Mapping[str, int]:
        return dict(self._attempts)

    @property
    def peak_active_requests(self) -> int:
        return self._peak_active_requests

    @property
    def observations(self) -> tuple[DependencyObservation, ...]:
        return tuple(self._observations)

    @property
    def pending_scripts(self) -> int:
        return len(self._scripts)


@dataclass(frozen=True, slots=True)
class TraceEvent:
    trace_id: str
    order_id: str
    event: str
    error_type: str | None = None


class InMemoryTraceRecorder:
    """Capture secret-free logical request events for tests and demonstrations."""

    def __init__(self) -> None:
        self._events: list[TraceEvent] = []

    def record(self, event: TraceEvent) -> None:
        self._events.append(event)

    @property
    def events(self) -> tuple[TraceEvent, ...]:
        return tuple(self._events)


class TracedOrderReader:
    """Add correlation events around a resilient logical read."""

    def __init__(
        self,
        reader: ResilientOrderReader,
        recorder: InMemoryTraceRecorder,
    ) -> None:
        self._reader = reader
        self._recorder = recorder

    async def get_order(self, order_id: str, *, trace_id: str) -> Order:
        self._recorder.record(
            TraceEvent(trace_id=trace_id, order_id=order_id, event="started")
        )
        token = _TRACE_ID.set(trace_id)
        try:
            order = await self._reader.get_order(order_id)
        except Exception as error:
            self._recorder.record(
                TraceEvent(
                    trace_id=trace_id,
                    order_id=order_id,
                    event="failed",
                    error_type=type(error).__name__,
                )
            )
            raise
        finally:
            _TRACE_ID.reset(token)
        self._recorder.record(
            TraceEvent(trace_id=trace_id, order_id=order_id, event="succeeded")
        )
        return order
