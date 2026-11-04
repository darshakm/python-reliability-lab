# Order Integration Runbook

## Signals

- Logical success/error rate and latency
- Physical attempts per logical request
- 429, timeout, network, 5xx, authentication, and malformed-response counts
- Token-bucket wait time
- Breaker state and rejected-call count
- Cache hit, miss, stale, eviction, and in-flight-load counts
- Batch completed, failed, and pending order counts

Never log credentials, full payloads, or unrestricted exception text.

## Triage sequence

1. Confirm user impact and affected workflows or tenants.
2. Separate caller/data errors from dependency availability failures.
3. Compare logical request volume with physical attempt volume.
4. Check breaker state, rate-limit waits, and upstream status distribution.
5. Determine whether stale fallback is active and safe for the workflow.
6. Correlate one logical trace with its dependency attempts.

## Common conditions

### Authentication failures

Do not retry or serve stale automatically. Validate secret source, rotation, and
scope. Escalate credential correction through the approved owner.

### 429 responses

Honor bounded `Retry-After`, verify per-attempt limiting, and reduce offered load.
Do not count 429 as an availability breaker failure by default.

### Sustained 5xx or timeouts

Expect bounded retries followed by breaker opening. Verify fast rejection and
approved stale behavior. Avoid manually increasing retries during an outage.

### Malformed responses

Treat as a contract/data problem, not a transient outage. Capture only sanitized
schema diagnostics and quarantine or escalate the source change.

## Recovery checks

- A single half-open probe runs after the recovery timeout.
- Successful probe closes the breaker; failed probe reopens it.
- Physical-attempt volume does not spike on recovery.
- Fresh cache values replace stale values.
- Error and tail-latency measures return to baseline.

## Rollback

Disable a new policy or deployment through the normal release rollback. Do not
delete diagnostic evidence. Record the customer impact, timeline, contributing
conditions, and owned follow-up actions.
