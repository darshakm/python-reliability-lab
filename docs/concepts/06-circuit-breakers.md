# 6. Circuit Breakers

**Problem:** Repeated calls to a sustained failing dependency waste resources and
delay graceful degradation.

**Invariant:** Availability failures open the circuit after a threshold; open
calls reject quickly; one half-open probe determines recovery.

Authentication, malformed data, caller errors, and 429 capacity feedback are not
availability failures in the default policy. The breaker counts the final logical
retry outcome, not every attempt.

**Does not solve:** Retry recovery, fallback ownership, or rate limiting.

**Tradeoff:** Aggressive thresholds isolate quickly but risk rejecting traffic
during a brief failure cluster.

**Explore:** Run `reliability-lab recovery` and map every reported transition to
`AsyncCircuitBreaker` methods.
