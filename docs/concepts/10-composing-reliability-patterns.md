# 10. Composing Reliability Patterns

**Problem:** Individually correct patterns can interact badly when their
boundaries or ownership are unclear.

**Invariant:** Cache handles reuse and approved stale fallback; breaker isolates
sustained availability failure; retry handles bounded transient recovery; limiter
controls every physical attempt; client and model enforce the external contract.

The composition is:

```text
cache -> breaker -> retry -> rate limiter -> dependency
```

**Does not solve:** Product policy. Whether stale data, latency, or rejection is
acceptable remains a customer/workflow decision.

**Tradeoff:** More layers improve control but add configuration, state, telemetry,
and failure interactions.

**Explore:** For authentication failure, 429, timeout, malformed JSON, and 503,
state which layers act and why. Then repeat for a cache hit.
