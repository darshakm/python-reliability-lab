"""Executable system-design experiments backed by the library components."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from collections.abc import Callable, Coroutine, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from reliability_lab.async_worker import fetch_orders
from reliability_lab.cache import AsyncTTLCache
from reliability_lab.circuit_breaker import AsyncCircuitBreaker, CircuitOpenError
from reliability_lab.exceptions import UpstreamServiceError
from reliability_lab.models import Order
from reliability_lab.retry import RetryPolicy, execute_resiliently

type Experiment = Callable[
    [argparse.Namespace], Coroutine[Any, Any, dict[str, Any]]
]


def _order(order_id: str) -> Order:
    return Order(
        id=order_id,
        customer_id="demo-customer",
        status="pending",
        amount=Decimal("10.00"),
        currency="USD",
        created_at=datetime(2026, 11, 4, tzinfo=UTC),
    )


def _percentile(samples: Sequence[float], probability: float) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, int(len(ordered) * probability))
    return ordered[index]


async def _concurrency(args: argparse.Namespace) -> dict[str, Any]:
    active = 0
    peak = 0
    latencies: list[float] = []
    lock = asyncio.Lock()
    upstream = asyncio.Semaphore(args.upstream_capacity)

    async def fetch(order_id: str) -> Order:
        nonlocal active, peak
        started = time.perf_counter()
        async with upstream:
            async with lock:
                active += 1
                peak = max(peak, active)
            try:
                await asyncio.sleep(args.latency)
                return _order(order_id)
            finally:
                latencies.append(time.perf_counter() - started)
                async with lock:
                    active -= 1

    started = time.perf_counter()
    results = await fetch_orders(
        [f"ord-{index}" for index in range(args.orders)],
        fetch,
        max_concurrency=args.workers,
    )
    elapsed = time.perf_counter() - started
    return {
        "experiment": "concurrency",
        "orders": args.orders,
        "workers": args.workers,
        "upstream_capacity": args.upstream_capacity,
        "successful": sum(result.succeeded for result in results),
        "peak_dependency_concurrency": peak,
        "elapsed_seconds": round(elapsed, 4),
        "throughput_per_second": round(args.orders / elapsed, 2),
        "p50_ms": round(statistics.median(latencies) * 1000, 2),
        "p95_ms": round(_percentile(latencies, 0.95) * 1000, 2),
    }


async def _outage(args: argparse.Namespace) -> dict[str, Any]:
    attempts = 0

    async def dependency() -> str:
        nonlocal attempts
        attempts += 1
        if attempts <= args.failures:
            raise UpstreamServiceError("simulated outage", status_code=503)
        return "recovered"

    started = time.perf_counter()
    outcome = "retry_exhausted"
    error_type: str | None
    try:
        outcome = await execute_resiliently(
            dependency,
            safety="safe",
            policy=RetryPolicy(
                max_attempts=args.retries + 1,
                initial_delay=args.backoff,
                max_delay=args.backoff,
            ),
        )
    except Exception as error:
        error_type = type(error).__name__
    else:
        error_type = None
    return {
        "experiment": "outage",
        "configured_failures": args.failures,
        "retry_budget": args.retries,
        "physical_attempts": attempts,
        "outcome": outcome,
        "error_type": error_type,
        "elapsed_seconds": round(time.perf_counter() - started, 4),
    }


async def _cache_stampede(args: argparse.Namespace) -> dict[str, Any]:
    dependency_calls = 0
    active = 0
    peak = 0
    lock = asyncio.Lock()

    async def load() -> Order:
        nonlocal dependency_calls, active, peak
        async with lock:
            dependency_calls += 1
            active += 1
            peak = max(peak, active)
        try:
            await asyncio.sleep(args.latency)
            return _order("shared-order")
        finally:
            async with lock:
                active -= 1

    cache: AsyncTTLCache[str, Order] = AsyncTTLCache(capacity=10, ttl=60)

    async def read() -> Order:
        if args.single_flight == "on":
            return await cache.get_or_load("shared-order", load)
        return await load()

    started = time.perf_counter()
    results = await asyncio.gather(*(read() for _ in range(args.callers)))
    return {
        "experiment": "cache-stampede",
        "callers": args.callers,
        "single_flight": args.single_flight,
        "dependency_calls": dependency_calls,
        "peak_dependency_concurrency": peak,
        "all_callers_received_same_value": all(
            result == results[0] for result in results
        ),
        "elapsed_seconds": round(time.perf_counter() - started, 4),
    }


async def _recovery(args: argparse.Namespace) -> dict[str, Any]:
    now = 0.0
    dependency_calls = 0
    transitions: list[str] = []

    def clock() -> float:
        return now

    breaker = AsyncCircuitBreaker(
        failure_threshold=args.threshold,
        recovery_timeout=args.recovery_timeout,
        clock=clock,
    )

    async def fail() -> None:
        nonlocal dependency_calls
        dependency_calls += 1
        raise UpstreamServiceError("simulated outage", status_code=503)

    for _ in range(args.threshold):
        try:
            await breaker.call(fail)
        except UpstreamServiceError:
            transitions.append((await breaker.snapshot()).state.value)

    try:
        await breaker.call(fail)
    except CircuitOpenError:
        transitions.append("rejected_while_open")

    now += args.recovery_timeout

    async def recover() -> str:
        nonlocal dependency_calls
        dependency_calls += 1
        return "healthy"

    outcome = await breaker.call(recover)
    transitions.append((await breaker.snapshot()).state.value)
    return {
        "experiment": "recovery",
        "failure_threshold": args.threshold,
        "recovery_timeout": args.recovery_timeout,
        "dependency_calls": dependency_calls,
        "probe_outcome": outcome,
        "transitions": transitions,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="reliability-lab",
        description="Run observable reliability and system-design experiments.",
    )
    subparsers = parser.add_subparsers(dest="experiment", required=True)

    concurrency = subparsers.add_parser(
        "concurrency", help="Explore worker and upstream capacity limits."
    )
    concurrency.add_argument("--orders", type=int, default=40)
    concurrency.add_argument("--workers", type=int, default=8)
    concurrency.add_argument("--upstream-capacity", type=int, default=4)
    concurrency.add_argument("--latency", type=float, default=0.01)
    concurrency.set_defaults(run=_concurrency)

    outage = subparsers.add_parser(
        "outage", help="Observe retry recovery or exhaustion."
    )
    outage.add_argument("--failures", type=int, default=2)
    outage.add_argument("--retries", type=int, default=3)
    outage.add_argument("--backoff", type=float, default=0)
    outage.set_defaults(run=_outage)

    stampede = subparsers.add_parser(
        "cache-stampede", help="Compare protected and unprotected cache misses."
    )
    stampede.add_argument("--callers", type=int, default=20)
    stampede.add_argument("--single-flight", choices=("on", "off"), default="on")
    stampede.add_argument("--latency", type=float, default=0.01)
    stampede.set_defaults(run=_cache_stampede)

    recovery = subparsers.add_parser(
        "recovery", help="Trace circuit opening, rejection, and recovery."
    )
    recovery.add_argument("--threshold", type=int, default=3)
    recovery.add_argument("--recovery-timeout", type=float, default=10)
    recovery.set_defaults(run=_recovery)
    return parser


def _validate(args: argparse.Namespace) -> None:
    positive = ("orders", "workers", "upstream_capacity", "callers", "threshold")
    for name in positive:
        value = getattr(args, name, None)
        if value is not None and value < 1:
            raise ValueError(f"--{name.replace('_', '-')} must be at least 1")
    non_negative = ("latency", "failures", "retries", "backoff")
    for name in non_negative:
        value = getattr(args, name, None)
        if value is not None and value < 0:
            raise ValueError(f"--{name.replace('_', '-')} must not be negative")
    recovery_timeout = getattr(args, "recovery_timeout", None)
    if recovery_timeout is not None and recovery_timeout <= 0:
        raise ValueError("--recovery-timeout must be positive")


def main(argv: Sequence[str] | None = None) -> None:
    """Parse arguments, run one experiment, and print stable JSON output."""

    args = _parser().parse_args(argv)
    _validate(args)
    run: Experiment = args.run
    print(json.dumps(asyncio.run(run(args)), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
