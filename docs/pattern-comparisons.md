# From Naive Code to Bounded Design

The useful question is not “Which pattern should I add?” It is “Which observed
failure violates an invariant, and what is the smallest mechanism that restores
it?”

## Batch concurrency

**Naive:** Create one task for every order and guard the HTTP call with a
semaphore.

**Failure:** Active calls are bounded, but waiting tasks and their memory are not.

**Bounded design:** Create a fixed number of workers that pull from the input.

**Evidence:** Run the concurrency experiment and inspect `fetch_orders()`.

## Retries

**Naive:** Retry every exception three times immediately.

**Failure:** Permanent errors waste work, unsafe writes can duplicate effects, and
clients synchronize into a retry storm.

**Bounded design:** Classify errors and operation safety; apply capped backoff,
jitter, server guidance, and attempt plus elapsed budgets.

**Evidence:** Compare outage runs where failures fit or exceed the retry budget.

## Traffic control

**Naive:** Use only a concurrency semaphore.

**Failure:** A fast dependency can still receive an excessive request rate, and
retries may bypass the intended quota.

**Bounded design:** Combine a worker bound with a token bucket acquired inside
each physical attempt.

**Evidence:** Trace `execute_resiliently()` and distinguish rate from active work.

## Sustained outage

**Naive:** Rely on timeout and retry for every caller throughout the outage.

**Failure:** The system repeatedly spends latency and resources on a dependency
that is unlikely to succeed.

**Bounded design:** Count final logical availability failures, open the breaker,
reject quickly, and permit one recovery probe.

**Evidence:** Run the recovery experiment and map its transitions to the state
machine diagram.

## Concurrent cache misses

**Naive:** Every caller that misses runs the loader.

**Failure:** A popular expired key creates a dependency request spike.

**Bounded design:** Store one in-flight task per key, shield it from individual
caller cancellation, and use generations to protect invalidation.

**Evidence:** Compare single-flight off and on; inspect `dependency_calls`.

## Package verification

**Naive:** Run tests from the source checkout and assume the wheel is correct.

**Failure:** Local imports and installed development dependencies can hide missing
files, package data, entry points, or runtime requirements.

**Bounded design:** Build in isolation, inspect archives, and install the wheel in
an external environment before importing and running its CLI.

**Evidence:** Follow the README build-and-inspect sequence and verify the module
path points to external `site-packages`.
