# Python Reliability Lab 1.0.0 — Release Notes

**Status:** Approved for public GitHub release on 2026-11-03.

## Purpose

This learning and portfolio package demonstrates how to build a typed Python
integration that remains predictable under malformed data, latency, rate limits,
partial outages, concurrency, and recovery.

## Included capabilities

- Strict immutable order boundary model and typed HTTP client
- Bounded async batch retrieval and structured cancellation
- Safe/idempotent retries, backoff, jitter, `Retry-After`, and retry budgets
- Concurrent token-bucket rate limiting
- Explicit circuit-breaker state machine and controlled recovery probe
- Bounded TTL/LRU caching, stampede control, invalidation, and stale fallback
- Deterministic and real-loopback fault injection
- Correlated events, failure matrix, load measurements, and profiling reports

## Verification snapshot

- 159 automated tests passed on Python 3.14.6 and macOS arm64
- Ruff and strict mypy passed
- Wheel and source distribution built successfully
- Local synthetic benchmark methodology and limitations are documented
- Retained harness memory decreased from approximately 19.6 MB to 2.6 MB
- Local HTTP integration-suite time decreased from 3.21 seconds to 0.23 seconds

These measurements describe controlled local synthetic experiments, not
production capacity or universal performance claims.

## Compatibility and limitations

- Python 3.12 or newer is required.
- The production HTTP client is synchronous; async composition uses a thread
  adapter whose cancellation cannot stop an already-running thread.
- Test telemetry uses an in-memory sink, not a production observability backend.
- The local fault server and benchmarks use synthetic data and deterministic
  conditions.
- Stale fallback is suitable only where the caller explicitly accepts bounded
  staleness.

## Upgrade notes

This is the first stable release. The public source repository is
`https://github.com/darshakm/python-reliability-lab`. Compatibility claims remain
limited to the environments recorded above until additional versions are tested.
