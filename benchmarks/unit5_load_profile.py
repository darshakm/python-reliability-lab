"""Load, tail-latency, CPU, and memory benchmark for the resilient read path."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
import tracemalloc
from datetime import UTC, datetime
from decimal import Decimal

from reliability_lab.async_worker import fetch_orders
from reliability_lab.cache import AsyncTTLCache
from reliability_lab.circuit_breaker import AsyncCircuitBreaker
from reliability_lab.integration_harness import ScriptedOrderSource, ScriptedResponse
from reliability_lab.models import Order
from reliability_lab.resilient_reader import ResilientOrderReader
from reliability_lab.retry import RetryPolicy


def percentile(samples: list[float], probability: float) -> float:
    ordered = sorted(samples)
    index = min(len(ordered) - 1, int(len(ordered) * probability))
    return ordered[index]


async def run_once(
    *, count: int, latency: float, concurrency: int
) -> dict[str, float | int]:
    template = Order(
        id="benchmark",
        customer_id="benchmark",
        status="pending",
        amount=Decimal("1.00"),
        currency="USD",
        created_at=datetime(2026, 11, 3, tzinfo=UTC),
    )
    source = ScriptedOrderSource(
        {
            f"ord_{index}": [ScriptedResponse(template, delay=latency)]
            for index in range(count)
        },
        observation_capacity=count,
    )
    reader = ResilientOrderReader(
        fetch_order=source.fetch,
        cache=AsyncTTLCache(capacity=min(count, 100), ttl=60),
        circuit_breaker=AsyncCircuitBreaker(
            failure_threshold=5, recovery_timeout=1
        ),
        retry_policy=RetryPolicy(max_attempts=1),
    )
    latencies: list[float] = []

    async def timed_fetch(order_id: str) -> Order:
        started = time.perf_counter()
        try:
            return await reader.get_order(order_id)
        finally:
            latencies.append(time.perf_counter() - started)

    started = time.perf_counter()
    results = await fetch_orders(
        [f"ord_{index}" for index in range(count)],
        timed_fetch,
        max_concurrency=concurrency,
    )
    elapsed = time.perf_counter() - started
    if not all(result.succeeded for result in results):
        raise RuntimeError("load benchmark contained a failed result")

    return {
        "concurrency": concurrency,
        "elapsed_seconds": round(elapsed, 6),
        "throughput_per_second": round(count / elapsed, 2),
        "p50_ms": round(statistics.median(latencies) * 1000, 3),
        "p95_ms": round(percentile(latencies, 0.95) * 1000, 3),
        "peak_dependency_concurrency": source.peak_active_requests,
    }


async def benchmark(
    *, count: int, latency: float, concurrencies: list[int]
) -> list[dict[str, float | int]]:
    return [
        await run_once(count=count, latency=latency, concurrency=concurrency)
        for concurrency in concurrencies
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--latency", type=float, default=0.002)
    parser.add_argument("--concurrency", nargs="+", type=int, default=[1, 8, 32])
    args = parser.parse_args()

    tracemalloc.start()
    rows = asyncio.run(
        benchmark(
            count=args.count,
            latency=args.latency,
            concurrencies=args.concurrency,
        )
    )
    current, peak = tracemalloc.get_traced_memory()
    print(
        json.dumps(
            {
                "count": args.count,
                "simulated_dependency_latency_seconds": args.latency,
                "current_traced_bytes": current,
                "peak_traced_bytes": peak,
                "results": rows,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
