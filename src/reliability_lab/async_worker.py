"""Bounded asynchronous order retrieval."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from reliability_lab.exceptions import RequestTimeoutError
from reliability_lab.models import Order

type AsyncOrderFetcher = Callable[[str], Awaitable[Order]]
type ResultOrder = Literal["input", "completion"]


class SyncOrderFetcher(Protocol):
    """A synchronous order source that can be adapted to the async worker."""

    def get_order(self, order_id: str) -> Order:
        """Retrieve one order synchronously."""


@dataclass(frozen=True, slots=True)
class OrderFetchResult:
    """The outcome of fetching one order, including its input context."""

    order_id: str
    order: Order | None = None
    error: Exception | None = None

    def __post_init__(self) -> None:
        if (self.order is None) == (self.error is None):
            raise ValueError("exactly one of order or error must be set")

    @property
    def succeeded(self) -> bool:
        """Whether this result contains a fetched order."""

        return self.order is not None


class BatchDeadlineExceeded(Exception):
    """The overall deadline elapsed after some batch work may have completed."""

    def __init__(
        self,
        *,
        completed_results: Sequence[OrderFetchResult],
        pending_order_ids: Sequence[str],
    ) -> None:
        super().__init__("order batch exceeded its overall deadline")
        self.completed_results = tuple(completed_results)
        self.pending_order_ids = tuple(pending_order_ids)


async def fetch_order_in_thread(client: SyncOrderFetcher, order_id: str) -> Order:
    """Adapt a blocking client for occasional use by the async worker.

    Cancelling the awaiting task does not stop a thread that is already executing.
    A natively asynchronous transport is preferable for sustained async workloads.
    """

    return await asyncio.to_thread(client.get_order, order_id)


async def fetch_orders(
    order_ids: Sequence[str],
    fetch_order: AsyncOrderFetcher,
    *,
    max_concurrency: int,
    per_request_timeout: float | None = None,
    overall_timeout: float | None = None,
    result_order: ResultOrder = "input",
) -> list[OrderFetchResult]:
    """Fetch orders concurrently with explicit ordering and deadline behavior.

    Ordinary item failures are returned with their ``order_id`` so one bad
    request does not discard successful results. Cancellation is deliberately
    not converted into a result; it propagates through the task group, which
    cancels and awaits sibling tasks before this function exits.
    """

    if max_concurrency < 1:
        raise ValueError("max_concurrency must be at least 1")
    if per_request_timeout is not None and per_request_timeout <= 0:
        raise ValueError("per_request_timeout must be positive")
    if overall_timeout is not None and overall_timeout <= 0:
        raise ValueError("overall_timeout must be positive")
    if result_order not in ("input", "completion"):
        raise ValueError("result_order must be 'input' or 'completion'")

    results: list[OrderFetchResult | None] = [None] * len(order_ids)
    completion_results: list[OrderFetchResult] = []
    next_index = 0

    def record_result(index: int, result: OrderFetchResult) -> None:
        results[index] = result
        completion_results.append(result)

    async def fetch_one(index: int, order_id: str) -> None:
        try:
            if per_request_timeout is None:
                order = await fetch_order(order_id)
            else:
                async with asyncio.timeout(per_request_timeout):
                    order = await fetch_order(order_id)
        except TimeoutError as error:
            timeout_error = RequestTimeoutError(
                f"order {order_id!r} exceeded its request timeout"
            )
            timeout_error.__cause__ = error
            record_result(
                index,
                OrderFetchResult(order_id=order_id, error=timeout_error),
            )
        except Exception as error:
            record_result(index, OrderFetchResult(order_id=order_id, error=error))
        else:
            record_result(index, OrderFetchResult(order_id=order_id, order=order))

    async def worker() -> None:
        nonlocal next_index
        while next_index < len(order_ids):
            index = next_index
            next_index += 1
            await fetch_one(index, order_ids[index])

    async def run_batch() -> None:
        async with asyncio.TaskGroup() as task_group:
            worker_count = min(max_concurrency, len(order_ids))
            for _ in range(worker_count):
                task_group.create_task(worker())

    try:
        if overall_timeout is None:
            await run_batch()
        else:
            async with asyncio.timeout(overall_timeout):
                await run_batch()
    except TimeoutError as error:
        completed = _ordered_results(results, completion_results, result_order)
        pending = [
            order_id
            for order_id, result in zip(order_ids, results, strict=True)
            if result is None
        ]
        raise BatchDeadlineExceeded(
            completed_results=completed,
            pending_order_ids=pending,
        ) from error

    return _ordered_results(results, completion_results, result_order)


def _ordered_results(
    input_results: Sequence[OrderFetchResult | None],
    completion_results: Sequence[OrderFetchResult],
    result_order: ResultOrder,
) -> list[OrderFetchResult]:
    if result_order == "completion":
        return list(completion_results)

    return [result for result in input_results if result is not None]
