# Exercise Discussion Guide

These are reasoning checkpoints, not unique answers.

1. Two 503 responses are retryable; the third call succeeds. A limiter belongs
   inside the retry operation so all three physical attempts consume capacity.
2. Cache checks first. A miss creates one shared loader. The breaker admits the
   logical retry operation; each retry is limited; the client parses and validates;
   success is stored if the cache generation is still current.
3. Request timeout becomes an `OrderFetchResult` error and the worker continues.
   Batch timeout cancels the task group and raises completed and pending context.
4. Capacity four is the bottleneck. Extra workers wait; task and scheduling
   overhead can rise without increasing dependency throughput.
5. Synchronized retry creates a second load spike. Exponential backoff, jitter,
   server `Retry-After`, retry budgets, and per-attempt limiting reduce it.
6. `dependency_calls == 1` proves protection. Equal values could still result
   from many duplicate loads.
7. Change `Order.from_dict()` and its unexpected-field test. Compatibility
   improves, but silent upstream drift becomes possible.
8. Do not retry an unsafe POST. With a server-enforced idempotency key, retry the
   same logical operation using the same key and reconcile the stored outcome.
9. Cache, breaker, limiter, and in-flight maps are local. Fleet-wide quotas need
   gateway enforcement or distributed coordination; shared cache is a separate
   consistency decision.
10. History display may accept bounded stale data; authorization for a refund
    may not. Policy must define duration, failure classes, and visible freshness.
