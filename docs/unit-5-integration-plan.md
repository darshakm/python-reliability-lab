# Unit 5 — Integration, Testing, and Profiling Plan

## Initial vertical slice

`ScriptedOrderSource` is a finite deterministic dependency. Each order ID has an
explicit sequence of successes, exceptions, and simulated latencies. It records
attempt number, active-request count, peak concurrency, and outcome without
depending on external network state.

The first integration suite verifies the complete cache → breaker → retry →
limiter → dependency path for transient recovery, sustained outage with stale
degradation, concurrent cache misses, and non-retryable authentication failure.
`TracedOrderReader` adds secret-free logical start/success/failure events carrying
a caller-supplied trace ID.

## Completed technical work

- Actual loopback HTTP boundary for malformed data, disconnect, timeout, status,
  authentication, and recovery scenarios
- Automated end-to-end failure matrix
- Correlated logical and dependency-attempt observations
- Reproducible throughput and p50/p95 measurements
- CPU and tracemalloc profiling
- Measured memory-retention and HTTP-test shutdown optimizations
- Final report in `unit-5-integration-load-profile-report.md`

The remaining completion step is the Unit 5 understanding review.
