# System-Design Interview Guide

Use these prompts to defend the design. A strong answer names the invariant,
failure mode, tradeoff, and production boundary.

1. Why use a fixed worker pool instead of one task per order plus a semaphore?
2. What is the difference between concurrency control and rate limiting?
3. Which HTTP failures are safe to retry, and why is method alone insufficient?
4. Why must retries pass through the token bucket?
5. Why does the breaker count a logical retry operation as one outcome?
6. Why does a breaker not replace retries, timeouts, or fallback?
7. Why allow only one half-open probe?
8. How does per-key single-flight prevent a cache stampede?
9. Why shield the shared load from one caller's cancellation?
10. What race does cache generation tracking prevent?
11. When is stale data a safe degradation strategy?
12. What is the cancellation limitation of `asyncio.to_thread()`?
13. How do per-request and batch deadlines differ?
14. What evidence shows an optimization improved the measured problem?
15. What breaks when the service moves from one process to many?
16. How would traffic, latency, and cost change at 100× scale?
17. Which telemetry is useful, and what data must be excluded?
18. How would you explain this system to a support leader versus an engineer?

## Answer rubric

- **Incomplete:** names a pattern without its failure boundary.
- **Competent:** explains behavior, tradeoff, and evidence in this repository.
- **Senior/FDE:** connects the choice to customer outcomes, constraints,
  alternatives, operational ownership, and a staged production evolution.
