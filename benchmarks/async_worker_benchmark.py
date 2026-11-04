"""Reproducible latency-bound benchmark for the Unit 2 async worker."""

from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from datetime import UTC, datetime
from decimal import Decimal

from reliability_lab.async_worker import fetch_orders
from reliability_lab.models import Order


def make_order(order_id: str) -> Order:
    return Order(
        id=order_id,
        customer_id="benchmark",
        status="pending",
        amount=Decimal("1.00"),
        currency="USD",
        created_at=datetime(2026, 11, 2, tzinfo=UTC),
    )


async def run_once(
    *, count: int, latency: float, concurrency: int, upstream_capacity: int
) -> float:
    service_limit = asyncio.Semaphore(upstream_capacity)

    async def fetch(order_id: str) -> Order:
        async with service_limit:
            await asyncio.sleep(latency)
            return make_order(order_id)

    started = time.perf_counter()
    results = await fetch_orders(
        [f"ord_{index}" for index in range(count)],
        fetch,
        max_concurrency=concurrency,
    )
    elapsed = time.perf_counter() - started
    if len(results) != count or not all(result.succeeded for result in results):
        raise RuntimeError("benchmark batch did not complete successfully")
    return elapsed


async def benchmark(
    *,
    count: int,
    latency: float,
    concurrencies: list[int],
    repetitions: int,
    upstream_capacity: int,
) -> list[dict[str, float | int]]:
    rows: list[dict[str, float | int]] = []
    for concurrency in concurrencies:
        samples = [
            await run_once(
                count=count,
                latency=latency,
                concurrency=concurrency,
                upstream_capacity=upstream_capacity,
            )
            for _ in range(repetitions)
        ]
        median = statistics.median(samples)
        rows.append(
            {
                "concurrency": concurrency,
                "median_seconds": round(median, 6),
                "orders_per_second": round(count / median, 2),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=100)
    parser.add_argument("--latency", type=float, default=0.02)
    parser.add_argument("--upstream-capacity", type=int, default=8)
    parser.add_argument(
        "--concurrency", type=int, nargs="+", default=[1, 2, 4, 8, 16, 32]
    )
    parser.add_argument("--repetitions", type=int, default=5)
    args = parser.parse_args()
    rows = asyncio.run(
        benchmark(
            count=args.count,
            latency=args.latency,
            concurrencies=args.concurrency,
            repetitions=args.repetitions,
            upstream_capacity=args.upstream_capacity,
        )
    )
    print(
        json.dumps(
            {
                "count": args.count,
                "simulated_latency_seconds": args.latency,
                "simulated_upstream_capacity": args.upstream_capacity,
                "repetitions": args.repetitions,
                "results": rows,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
