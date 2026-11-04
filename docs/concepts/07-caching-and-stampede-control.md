# 7. Caching and Stampede Control

**Problem:** Concurrent misses for one key can duplicate dependency work, while
unbounded caching creates memory risk.

**Invariant:** TTL controls freshness, LRU bounds size, and one shared load runs
per key. One waiter's cancellation does not cancel the shared load. Generation
tracking prevents an invalidated older load from restoring stale state.

**Does not solve:** Cross-process coordination or universal fallback safety.

**Tradeoff:** Serving stale data improves availability only where bounded
staleness is acceptable for the user action.

**Explore:** Run cache stampede with single-flight on and off. Use dependency-call
count—not equal returned values—as the protection evidence.
