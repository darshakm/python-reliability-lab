from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from reliability_lab.async_worker import (
    BatchDeadlineExceeded,
    OrderFetchResult,
    fetch_order_in_thread,
    fetch_orders,
)
from reliability_lab.exceptions import RequestTimeoutError, UpstreamServiceError
from reliability_lab.models import Order


def make_order(order_id: str) -> Order:
    return Order(
        id=order_id,
        customer_id="cust_123",
        status="pending",
        amount=Decimal("10.00"),
        currency="USD",
        created_at=datetime(2026, 11, 2, tzinfo=UTC),
    )


def test_fetch_orders_preserves_input_order_and_bounds_concurrency() -> None:
    async def scenario() -> None:
        active = 0
        peak = 0

        async def fetch(order_id: str) -> Order:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                await asyncio.sleep(0.001)
                return make_order(order_id)
            finally:
                active -= 1

        results = await fetch_orders(
            ["ord_3", "ord_1", "ord_2", "ord_4"],
            fetch,
            max_concurrency=2,
        )

        assert peak == 2
        assert [result.order_id for result in results] == [
            "ord_3",
            "ord_1",
            "ord_2",
            "ord_4",
        ]
        assert all(result.succeeded for result in results)

    asyncio.run(scenario())


def test_fetch_orders_retains_partial_failure_context() -> None:
    async def scenario() -> None:
        async def fetch(order_id: str) -> Order:
            if order_id == "ord_bad":
                raise UpstreamServiceError("service unavailable", status_code=503)
            return make_order(order_id)

        results = await fetch_orders(
            ["ord_1", "ord_bad", "ord_2"], fetch, max_concurrency=3
        )

        assert [result.succeeded for result in results] == [True, False, True]
        assert results[1].order_id == "ord_bad"
        assert isinstance(results[1].error, UpstreamServiceError)

    asyncio.run(scenario())


def test_fetch_orders_converts_per_request_timeout_to_result() -> None:
    async def scenario() -> None:
        async def fetch(order_id: str) -> Order:
            await asyncio.sleep(1)
            return make_order(order_id)

        results = await fetch_orders(
            ["ord_slow"],
            fetch,
            max_concurrency=1,
            per_request_timeout=0.001,
        )

        assert results[0].order_id == "ord_slow"
        assert isinstance(results[0].error, RequestTimeoutError)

    asyncio.run(scenario())


def test_fetch_orders_can_return_completion_order() -> None:
    async def scenario() -> None:
        delays = {"ord_slow": 0.02, "ord_fast": 0.001, "ord_middle": 0.01}

        async def fetch(order_id: str) -> Order:
            await asyncio.sleep(delays[order_id])
            return make_order(order_id)

        results = await fetch_orders(
            ["ord_slow", "ord_fast", "ord_middle"],
            fetch,
            max_concurrency=3,
            result_order="completion",
        )

        assert [result.order_id for result in results] == [
            "ord_fast",
            "ord_middle",
            "ord_slow",
        ]

    asyncio.run(scenario())


def test_overall_deadline_reports_completed_and_cleans_up_pending_tasks() -> None:
    async def scenario() -> None:
        slow_cleaned_up = False

        async def fetch(order_id: str) -> Order:
            nonlocal slow_cleaned_up
            if order_id == "ord_fast":
                return make_order(order_id)
            try:
                await asyncio.Event().wait()
                raise AssertionError("unreachable")
            finally:
                slow_cleaned_up = True

        with pytest.raises(BatchDeadlineExceeded) as caught:
            await fetch_orders(
                ["ord_fast", "ord_slow"],
                fetch,
                max_concurrency=2,
                overall_timeout=0.01,
            )

        assert [
            result.order_id for result in caught.value.completed_results
        ] == ["ord_fast"]
        assert caught.value.pending_order_ids == ("ord_slow",)
        assert slow_cleaned_up

    asyncio.run(scenario())


def test_sync_client_adapter_runs_get_order() -> None:
    class FakeClient:
        def get_order(self, order_id: str) -> Order:
            return make_order(order_id)

    async def scenario() -> None:
        order = await fetch_order_in_thread(FakeClient(), "ord_123")
        assert order.id == "ord_123"

    asyncio.run(scenario())


def test_cancellation_cleans_up_started_tasks() -> None:
    async def scenario() -> None:
        started = 0
        cleaned_up = 0
        all_started = asyncio.Event()

        async def fetch(order_id: str) -> Order:
            nonlocal started, cleaned_up
            started += 1
            if started == 2:
                all_started.set()
            try:
                await asyncio.Event().wait()
                raise AssertionError("unreachable")
            finally:
                cleaned_up += 1

        batch = asyncio.create_task(
            fetch_orders(["ord_1", "ord_2"], fetch, max_concurrency=2)
        )
        await all_started.wait()
        batch.cancel()

        with pytest.raises(asyncio.CancelledError):
            await batch

        assert cleaned_up == 2

    asyncio.run(scenario())


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"max_concurrency": 0}, "max_concurrency"),
        (
            {"max_concurrency": 1, "per_request_timeout": 0},
            "per_request_timeout",
        ),
        (
            {"max_concurrency": 1, "overall_timeout": 0},
            "overall_timeout",
        ),
    ],
)
def test_fetch_orders_rejects_invalid_configuration(
    kwargs: dict[str, Any], message: str
) -> None:
    async def scenario() -> None:
        async def fetch(order_id: str) -> Order:
            return make_order(order_id)

        with pytest.raises(ValueError, match=message):
            await fetch_orders([], fetch, **kwargs)

    asyncio.run(scenario())


def test_fetch_orders_rejects_invalid_result_order() -> None:
    async def scenario() -> None:
        async def fetch(order_id: str) -> Order:
            return make_order(order_id)

        with pytest.raises(ValueError, match="result_order"):
            await fetch_orders(
                [],
                fetch,
                max_concurrency=1,
                result_order="invalid",  # type: ignore[arg-type]
            )

    asyncio.run(scenario())


def test_result_requires_exactly_one_outcome() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        OrderFetchResult(order_id="ord_1")
