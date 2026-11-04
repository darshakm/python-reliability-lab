# Unit 5 Integration, Load, and Profiling Report

## Scope

The suite exercises the complete cache → breaker → retry → limiter → dependency
path through both an in-memory scripted source and a real loopback HTTP server.
All data is synthetic.

## Automated failure matrix

| Scenario | Expected behavior | Evidence |
|---|---|---|
| Valid HTTP response | Authenticate, parse, validate, return `Order` | Local HTTP integration test |
| Malformed JSON | Raise `MalformedResponseError`; no retry | Local HTTP matrix |
| Disconnect | Translate to `UpstreamServiceError` | Local HTTP matrix |
| Request latency beyond timeout | Raise `RequestTimeoutError` | Local HTTP timeout test |
| HTTP 503 then success | Retry safe read and recover | Local HTTP recovery test |
| Sustained 503 | Exhaust retry, open breaker, serve eligible stale order | Full composition test |
| Authentication failure | Do not retry or hide with stale data | Scripted integration test |
| Ten concurrent misses for one key | One dependency call | Stampede integration test |
| Cancellation | Record cancellation and preserve structured cleanup | Unit and harness tests |

Correlation IDs flow from `TracedOrderReader` through context-local state into
dependency-attempt observations. Events record identifiers, outcome, and error
type without credential values, payloads, or exception messages.

## Load and tail latency

Command:

```bash
PYTHONPATH=src python3 benchmarks/unit5_load_profile.py
```

Method:

- 500 unique uncached order reads
- 2 ms deterministic dependency latency
- One attempt per logical operation
- Worker concurrency 1, 8, and 32
- Per-operation latency measured around the full resilient reader

| Concurrency | Throughput/s | p50 ms | p95 ms | Peak dependency concurrency |
|---:|---:|---:|---:|---:|
| 1 | 392.33 | 2.535 | 2.706 | 1 |
| 8 | 2,765.23 | 2.811 | 3.199 | 8 |
| 32 | 12,084.88 | 2.304 | 3.386 | 32 |

This synthetic workload remains latency-bound through concurrency 32. The result
does not establish a safe production setting: a real service adds connection-pool,
rate, CPU, network, and server-capacity constraints.

## CPU profile

The profile was generated locally with cProfile and intentionally excluded from
the release archives as generated binary output. Under cProfile at concurrency
32, the run completed 500 reads at 7,632/s with p95 5.008 ms; profiling overhead
makes these numbers unsuitable for comparison with the unprofiled load result.

Within project code, the largest cumulative paths were cache load/store (26 ms),
resilient-reader loading (20 ms), logical-operation composition (16 ms), scripted
dependency execution (13 ms), and cache lookup (10 ms). No CPU-heavy function
dominated; event-loop scheduling and simulated I/O remained the primary workload.

## Measured optimizations

### Retained harness memory

A 20,000-response tracemalloc experiment initially retained 20,000 empty script
queues and 20,000 observations:

| Version | Retained bytes | Observations | Empty script keys |
|---|---:|---:|---:|
| Before | 19,623,431 | 20,000 | 20,000 |
| After | 2,625,181 | 10,000 bounded | 0 |

Removing exhausted scripts and bounding diagnostic observations reduced retained
memory by approximately 86.6%. Peak allocation remains similar because all input
scripts are constructed up front; streaming script generation is outside this
harness's current scope.

### Local HTTP test shutdown

The standard server's default 500 ms shutdown polling dominated integration-suite
time. Reducing only the loopback test server's poll interval to 10 ms changed the
pytest-reported runtime from 3.21 seconds to 0.23 seconds, approximately 92.8%
faster, without changing request semantics. All behavioral checks continued to
pass.

## Limitations

- The server and load source are deterministic local fixtures, not production
  capacity models.
- Percentiles use 500 samples and one recorded run.
- Synthetic latency does not model network variance or connection-pool behavior.
- The trace recorder is an in-memory test sink, not a production telemetry backend.
- The profile guides this lab only; optimization decisions must be repeated under
  the eventual deployment workload.
