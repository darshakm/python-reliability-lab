# Guided Exercises

Use AI, documentation, and source navigation. The goal is explanation and design
judgment, not memorized typing. Check [`solutions.md`](solutions.md) only after
writing your reasoning.

## Trace

### 1. Retry recovery

Run:

```bash
reliability-lab outage --failures 2 --retries 3
```

Trace the call from `execute_resiliently()` through each attempt. Explain why the
reported physical-attempt count is three and where a rate limiter would run.

### 2. Cache miss

Trace a miss through `ResilientOrderReader.get_order()`. Identify where the
breaker, retry policy, limiter, domain validation, and cache store occur.

### 3. Batch timeout

Read `fetch_orders()`. Contrast an individual request timeout with the overall
deadline. What context does the caller retain in each case?

## Diagnose

### 4. More workers, same throughput

Run concurrency experiments with upstream capacity `4` and workers `4`, `8`,
and `32`. Explain why throughput eventually stops increasing and what overhead
can still grow.

### 5. Retry storm

Assume 100 clients retry a 503 at exactly one second. Explain the failure mode and
identify three controls in this project that reduce it.

### 6. Cache stampede

Run the stampede experiment with single-flight on and off. Which metric proves
the dependency was protected? Why is equality of returned values insufficient?

## Change

### 7. Tolerate unknown fields

Change the order schema boundary to ignore unknown fields. Identify the source,
tests, compatibility benefit, and loss of strict drift detection before editing.

### 8. Add an unsafe write

Design `create_order()`. State its retry rule without and with a server-enforced
idempotency key. Explain where the key belongs and how duplicate outcomes are
reconciled.

### 9. Multi-instance deployment

The lab runs in three processes. Identify which state is instance-local and what
must move or coordinate to enforce a fleet-wide dependency budget.

### 10. Stale-data policy

Choose one workflow where stale order data is acceptable and one where it is
unsafe. Define maximum staleness, eligible errors, and the user-visible signal.
