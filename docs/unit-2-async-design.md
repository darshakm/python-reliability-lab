# Unit 2 — Bounded Async Worker Design

## Contract

`fetch_orders()` accepts order IDs, an asynchronous fetch function, a concurrency
limit, optional per-request and overall timeouts, and an ordering policy. Ordinary
item failures become `OrderFetchResult` values so successful work is retained.
External cancellation propagates instead of being converted into a result.

## Decisions

- A fixed-size worker pool bounds both active fetches and scheduled task count,
  preventing unbounded pressure and avoiding one waiting task per input record.
- `TaskGroup` provides structured concurrency: on cancellation, sibling tasks are
  cancelled and awaited before the worker exits.
- Input order is the default because it is easiest for callers to correlate.
  Completion order is optional for streaming-like consumers that value early work.
- A per-request timeout becomes an item failure. An overall timeout raises
  `BatchDeadlineExceeded` carrying completed results and pending IDs because the
  batch-level objective was not met.
- Ordinary item exceptions are retained with their input ID; `CancelledError` is
  not caught because cancellation is a control-flow signal, not a business result.

## Synchronous client adapter

`fetch_order_in_thread()` uses `asyncio.to_thread()` to make the existing blocking
client usable by the async worker. This is appropriate for incremental adoption
and small workloads. It is not a fully asynchronous HTTP stack: cancellation of
the awaiting task cannot stop a thread already performing blocking I/O, and thread
pool capacity becomes another resource limit. A native async transport is the
preferred later design for sustained high concurrency.

## Benchmark scope

The benchmark uses deterministic simulated I/O latency. It measures scheduling
and concurrency behavior, not network, server, serialization, or production
capacity. The useful concurrency level in a real system must also respect upstream
limits, connection pools, memory, tail latency, and error rates.
