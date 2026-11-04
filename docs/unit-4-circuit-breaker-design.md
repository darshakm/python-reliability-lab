# Unit 4 — Circuit Breaker and Cache Design

## Purpose

Retries help isolated transient failures. A circuit breaker protects a dependency
and its callers when failures become sustained by rejecting work locally instead
of repeatedly waiting for doomed network calls.

## State machine

- **Closed:** calls are allowed. Counted consecutive failures open the circuit at
  the configured threshold; success resets the count.
- **Open:** calls fail fast with `CircuitOpenError`. After the recovery timeout,
  the first caller becomes the recovery probe.
- **Half-open:** exactly one probe runs. Other callers fail fast. Probe success
  closes the circuit; counted failure reopens it from the new failure time.

The lock protects transitions and probe admission but is never held during the
dependency call. Cancellation of a probe releases the probe slot without claiming
that the dependency recovered or failed.

## Failure policy

Timeouts, network errors, and 5xx responses count toward opening the circuit.
Authentication, permanent 4xx, malformed data, and HTTP 429 do not: those require
caller correction or rate-limit handling rather than outage isolation.

## Cache policy

`AsyncTTLCache` combines a maximum entry count with LRU eviction and a monotonic
TTL. A separate stale window does not make data fresh; it only defines how long a
previous value remains eligible for explicitly classified outage fallback.

Concurrent misses for the same key share one background load. Awaiters use
`asyncio.shield()`, so cancelling one caller does not cancel work needed by other
callers. Invalidation increments a per-key generation, preventing an older
in-flight load from silently repopulating a value invalidated by a write.

Stale orders are allowed only for dependency-availability failures, exhausted
availability retries, or an open circuit. Authentication, malformed data, and
permanent caller errors remain visible rather than being hidden by stale data.

## Composition order

The read path is:

```text
TTL/LRU cache
    -> circuit breaker
        -> safe-operation retry policy
            -> token-bucket acquisition per physical attempt
                -> dependency
```

A fresh cache hit performs no dependency work. The breaker observes the final
logical outcome after retries, avoiding a single logical call consuming the full
breaker threshold. The limiter still applies to every physical attempt. When the
breaker is open, the loader fails locally and the cache may return an eligible
stale value.

The remaining completion step is the Unit 4 understanding review.
