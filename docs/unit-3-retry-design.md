# Unit 3 — Retry and Rate-Limit Design

## Contract

`retry_async()` executes one logical asynchronous operation under an explicit
attempt and delay budget. It retries only errors accepted by a classifier,
propagates permanent errors unchanged, and records transient attempt history when
the budget is exhausted.

## Decisions

- `max_attempts` includes the initial call. This avoids the ambiguous phrase
  “three retries,” which can mean three or four total requests.
- Backoff is exponential and capped before symmetric proportional jitter is
  applied. Jitter prevents many clients from retrying in lockstep.
- Sleep and randomness are injectable so tests do not wait or depend on chance.
- Authentication, malformed data, and permanent 4xx responses are not retryable.
  Timeouts, network failures, HTTP 429, and 5xx responses are transient candidates.
- `CancelledError` propagates because cancellation is workflow control, not a
  transient operation failure.
- Exhaustion raises `RetryExhaustedError` with every error and scheduled delay.
- `Retry-After` accepts delta-seconds or an HTTP date. The client normalizes it to
  seconds, and retry execution caps server guidance before combining it with
  client backoff.
- An elapsed-time budget prevents the next scheduled delay from exceeding the
  logical operation's deadline.
- `execute_resiliently()` retries only operations declared safe or idempotent.
  Unsafe operations receive one attempt even when the error appears transient.
- Every physical attempt acquires from the shared limiter before execution, so
  retries cannot bypass rate controls.

## Token bucket

`AsyncTokenBucket` starts full to allow a burst up to `capacity`, then refills at
`rate` tokens per second. A lock protects shared token state; waiting occurs
outside the lock. Time and sleep are injectable so refill, concurrent access, and
cancellation tests do not depend on wall-clock delays.

## Composition order

The worker establishes bounded concurrency. Each worker invokes
`execute_resiliently()`. Each initial attempt and retry acquires a token, performs
the operation, and then either returns, propagates a permanent error, or schedules
a bounded retry. Concurrency, rate, burst, attempt count, and elapsed time are
therefore independent limits.

See `unit-3-failure-matrix.md` for the automated retry policy. The remaining
completion step is the understanding review.
