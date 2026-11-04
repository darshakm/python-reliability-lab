# Changelog

All notable changes to this project will be documented here. The format follows
Keep a Changelog, and version numbers follow Semantic Versioning.

## Unreleased

### Added

- No changes yet.

## 1.0.0 — Unreleased

### Added

- Immutable typed `Order` model with strict boundary validation.
- Authenticated, timeout-bounded HTTP client and public exception hierarchy.
- Fixed-size async worker with ordering modes, partial failures, deadlines, and
  structured cancellation.
- Safe/idempotent retry policy with bounded backoff, jitter, `Retry-After`, and
  attempt and elapsed-time budgets.
- Concurrent token-bucket rate limiter.
- Closed/open/half-open circuit breaker with a controlled recovery probe.
- Bounded TTL/LRU cache with single-flight loading, generation-aware
  invalidation, and classified stale fallback.
- Deterministic and loopback-HTTP integration harnesses, failure matrix,
  correlated events, load benchmark, and CPU/memory profiling evidence.
