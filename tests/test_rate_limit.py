from __future__ import annotations

import asyncio
import math

import pytest

from reliability_lab.rate_limit import AsyncTokenBucket


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    async def sleep(self, delay: float) -> None:
        self.sleeps.append(delay)
        self.now += delay
        await asyncio.sleep(0)


def test_bucket_allows_burst_then_waits_for_refill() -> None:
    async def scenario() -> None:
        clock = FakeClock()
        bucket = AsyncTokenBucket(
            rate=2,
            capacity=3,
            clock=clock,
            sleep=clock.sleep,
        )

        await bucket.acquire(3)
        assert clock.sleeps == []

        await bucket.acquire()
        assert clock.sleeps == [0.5]
        assert bucket.available_tokens == 0

    asyncio.run(scenario())


def test_concurrent_acquisitions_respect_rate_and_burst() -> None:
    async def scenario() -> None:
        clock = FakeClock()
        bucket = AsyncTokenBucket(
            rate=2,
            capacity=1,
            clock=clock,
            sleep=clock.sleep,
        )
        completed_at: list[float] = []

        async def acquire() -> None:
            await bucket.acquire()
            completed_at.append(clock())

        async with asyncio.TaskGroup() as task_group:
            for _ in range(3):
                task_group.create_task(acquire())

        assert sorted(completed_at) == [0, 0.5, 1.0]

    asyncio.run(scenario())


def test_cancelled_waiter_does_not_consume_future_token() -> None:
    async def scenario() -> None:
        wait_started = asyncio.Event()

        async def blocking_sleep(delay: float) -> None:
            assert delay == 1
            wait_started.set()
            await asyncio.Event().wait()

        bucket = AsyncTokenBucket(
            rate=1,
            capacity=1,
            clock=lambda: 0,
            sleep=blocking_sleep,
        )
        await bucket.acquire()
        waiter = asyncio.create_task(bucket.acquire())
        await wait_started.wait()
        waiter.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiter

        assert bucket.available_tokens == 0

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("rate", "capacity"),
    [(0, 1), (-1, 1), (1, 0), (1, -1), (math.inf, 1), (1, math.nan)],
)
def test_bucket_rejects_invalid_configuration(
    rate: float, capacity: float
) -> None:
    with pytest.raises(ValueError):
        AsyncTokenBucket(rate=rate, capacity=capacity)


@pytest.mark.parametrize("amount", [0, -1, 2, math.inf, math.nan])
def test_bucket_rejects_invalid_acquisition(amount: float) -> None:
    async def scenario() -> None:
        bucket = AsyncTokenBucket(rate=1, capacity=1)
        with pytest.raises(ValueError):
            await bucket.acquire(amount)

    asyncio.run(scenario())
