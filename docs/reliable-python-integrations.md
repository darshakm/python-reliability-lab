# Reliable Python Integrations Under Partial Failure

External APIs rarely fail in one clean way. They become slow, reject bursts,
return malformed data, disconnect mid-response, recover unevenly, and sometimes
complete a request even though the caller times out. A dependable integration is
therefore less about issuing HTTP requests and more about defining boundaries:
what is trusted, what may be repeated, how much work is allowed, and what degraded
behavior is acceptable.

This article describes a synthetic Python lab built to make those boundaries
explicit and testable. It is an educational system, not a production service.

## Start with a trusted domain boundary

The HTTP response is untrusted until it becomes a validated `Order`. The model is
immutable, uses `Decimal` for money, requires timezone-aware timestamps, validates
closed status values, and rejects missing or unexpected known-schema fields.

Transport and domain failures remain distinct. Authentication, timeout, upstream
status, invalid JSON, and invalid order shape become different public exceptions.
That lets callers choose correction, retry, quarantine, or failure instead of
treating every error as “the API failed.”

## Bound concurrency and preserve cancellation

The async worker uses a fixed-size worker pool rather than creating one task per
input. A semaphore can bound active requests while still leaving an unbounded
number of waiting tasks. A worker pool bounds both dependency concurrency and
scheduler/memory overhead.

`TaskGroup` gives the batch a structured lifetime. Cancellation reaches sibling
tasks, cleanup runs, and no asyncio worker remains detached. Ordinary item errors
are retained with their input IDs; cancellation propagates because it is workflow
control rather than one order's business result.

## Retry less, not more

Retries are permitted only for safe or server-idempotent operations and transient
failures such as timeouts, network errors, HTTP 429, and selected 5xx responses.
Authentication, malformed payloads, and permanent 4xx errors require correction.

The retry policy combines capped exponential backoff, proportional jitter,
bounded `Retry-After`, maximum attempts, and a maximum elapsed budget. Sleep,
randomness, and time are injected so tests can assert exact schedules without
waiting or depending on chance.

Every physical attempt acquires a token from a concurrent token bucket. This is
important: rate-limiting only the initial call would allow retries to amplify an
outage and bypass the intended traffic policy.

## Isolate sustained failure

Retries handle isolated faults; a circuit breaker handles sustained availability
failure. The breaker moves from closed to open after a threshold of logical
failures, rejects calls locally during recovery, and permits exactly one half-open
probe. Probe success closes the circuit; failure reopens it from the new failure
time.

The breaker wraps the complete retry operation, so one logical call does not
consume the threshold with several physical attempts. Rate limiting remains
inside the retry loop and still applies to every request.

## Cache intentionally

The cache combines a TTL with a bounded LRU capacity. Concurrent misses for one
key share a single load, preventing a cache stampede. Cancelling one waiter does
not cancel the load needed by others.

Invalidation uses per-key generations. If a load starts before invalidation and
finishes afterward, its outdated generation prevents it from resurrecting stale
state in the cache.

Stale fallback is both time-bounded and failure-specific. It may be appropriate
during dependency unavailability or an open circuit, but it must not hide
authentication, malformed data, or caller errors. A historical display and a
refund authorization have different freshness requirements.

## Test the composition, not only the parts

The lab uses two fault boundaries. A scripted in-memory dependency provides exact
response sequences, latency, attempt counts, peak concurrency, and correlation.
A loopback HTTP server exercises real headers, parsing, sockets, disconnects,
timeouts, statuses, and recovery.

The end-to-end matrix covers transient recovery, sustained outage, stale
degradation, authentication failure, malformed data, disconnect, timeout, and ten
concurrent misses collapsing into one dependency request. Correlation IDs flow
through context-local state into dependency observations without recording API
keys, full payloads, or exception messages.

## Measure before optimizing

A synthetic load run of 500 unique reads with 2 ms dependency latency produced
approximately 392, 2,765, and 12,085 reads per second at concurrency 1, 8, and 32.
The corresponding p95 values were 2.706, 3.199, and 3.386 ms. These measurements
describe one local deterministic workload, not production capacity.

Profiling found a clear retention problem in the test harness: after 20,000
responses, it retained empty scripts and every observation, using about 19.6 MB.
Removing exhausted scripts and bounding observations reduced retained memory to
about 2.6 MB, an 86.6% decrease.

The HTTP integration suite also spent most of its time waiting for the local
server's default shutdown poll. Reducing only that test-server interval changed
the suite from 3.21 seconds to 0.23 seconds while all behavior tests continued to
pass.

## What remains production-specific

The lab deliberately omits production identity, distributed telemetry, persistent
cache infrastructure, real customer data, deployment automation, and a native
async HTTP transport. The thread adapter cannot terminate an already-running
blocking request when its awaiter is cancelled. Thresholds and stale policies are
hypotheses that must be recalibrated against a real dependency and user outcome.

The durable lesson is not a particular retry count or cache TTL. It is to make
failure policy explicit, compose limits in the correct order, test interactions
under controlled faults, and attach every performance claim to reproducible
evidence and visible limitations.

## Authorship note

This artifact was developed with material AI assistance for implementation,
testing, documentation, and review. The learner reviewed the architecture and
passed understanding checks covering the principal code paths and tradeoffs.
