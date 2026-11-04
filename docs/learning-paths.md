# Learning Paths

## 30-minute tour

1. Read the [customer scenario](customer-scenario.md).
2. Run the four commands in the README experiment table.
3. Compare single-flight `on` and `off`.
4. Trace the architecture in [diagrams](diagrams.md).
5. Answer Exercises 1–3 in [exercises](exercises.md).

## Two-hour system-design study

1. Read Concepts 1–5 in order.
2. Run the concurrency experiment with workers `1`, `4`, `8`, and `32` while
   holding upstream capacity at `4`.
3. Run outage recovery with different failure and retry budgets.
4. Explain why concurrency, rate, and retry budgets are separate controls.
5. Complete the trace and diagnosis exercises before reading solutions.

## Half-day reliability workshop

1. Complete all ten concept chapters.
2. Run protected and unprotected stampede experiments.
3. Trace breaker recovery and inspect the corresponding tests.
4. Complete all exercises and compare with the solutions.
5. Use the [interview guide](interview-guide.md) for a design-defense review.
6. Read the [production evolution](production-evolution.md) document and propose
   a multi-instance architecture.

## Source-reading map

| Question | Start here |
|---|---|
| Where is external data trusted? | `models.py`, `client.py` |
| How is batch work bounded? | `async_worker.py` |
| Which failures retry? | `retry.py`, `exceptions.py` |
| How is request rate controlled? | `rate_limit.py` |
| How does outage isolation work? | `circuit_breaker.py` |
| How are cache misses coalesced? | `cache.py` |
| How are components composed? | `resilient_reader.py` |
| How are failures simulated? | `integration_harness.py`, `local_flaky_api.py` |
| How do experiments expose behavior? | `demo.py` |
