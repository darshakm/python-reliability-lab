# 2. Bounded Concurrency

**Problem:** One task per input can create unbounded waiting work and memory even
when a semaphore limits active dependency calls.

**Invariant:** The worker pool creates at most `max_concurrency` workers while
retaining result context for every started input.

Input ordering supports deterministic downstream alignment; completion ordering
supports streaming-like follow-up work. Ordinary failures become item results,
while cancellation remains a workflow signal and propagates.

**Does not solve:** Requests-per-second quotas; that is rate limiting.

**Tradeoff:** A fixed pool is predictable but can exhibit head-of-line effects.

**Explore:** Run `reliability-lab concurrency` with an upstream capacity of four
and increase workers beyond four. Explain the throughput knee.
