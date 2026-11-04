# 5. Rate Limiting and Backpressure

**Problem:** Concurrency limits active work; they do not bound how many fast
requests can start per second.

**Invariant:** Every physical dependency attempt consumes a token. Capacity
allows a controlled burst; refill rate governs sustained traffic.

Backpressure appears at two boundaries: the fixed worker pool bounds queued
application work, while the token bucket delays dependency attempts.

**Does not solve:** Fairness across processes or a fleet-wide quota.

**Tradeoff:** A local bucket is simple and failure-independent but each instance
can consume its own allowance.

**Explore:** Compare a dependency that completes in 1 ms with one that takes 1 s.
Explain why identical concurrency can produce very different request rates.
