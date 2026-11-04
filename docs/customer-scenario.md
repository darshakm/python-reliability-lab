# Customer Scenario: Reliable Order Integration

## Situation

A retailer must read order status from a partner API during fulfillment and
support workflows. The partner is useful but unreliable: responses can be slow,
malformed, rate-limited, or temporarily unavailable. Traffic arrives in bursts,
and one failed order must not discard a successful batch.

## Customer outcomes

- Support agents receive useful order status during partial outages.
- Fulfillment batches finish without overwhelming the partner.
- Retries do not duplicate unsafe operations or bypass traffic policy.
- Failures identify the affected order and remain diagnosable.
- Recovery occurs without a new request storm.

## Constraints and assumptions

- Reads are safe to retry; writes require server-enforced idempotency.
- The partner has a finite concurrency and request-rate budget.
- Bounded stale data is acceptable only for explicitly approved read paths.
- Credentials and full order payloads must not enter telemetry.
- This lab is single-process and in-memory; distributed coordination is out of
  scope for the reference implementation.

## Success measures

| Measure | Target in this lab |
|---|---|
| Batch memory and active work | Bounded by worker count |
| Partial failure | Retains input order ID and successful results |
| Retry safety | Only safe/idempotent transient failures retry |
| Dependency pressure | Every physical attempt is rate-limited |
| Sustained outage | Breaker rejects quickly after its threshold |
| Concurrent cache miss | One dependency load per key |
| Diagnosis | Logical requests correlate to dependency attempts |

## Architecture decision

The read path composes cache → breaker → retry → rate limiter → HTTP boundary.
That order gives cheap cache hits, counts a retry sequence as one logical breaker
outcome, and makes every physical attempt consume rate capacity. See
[`diagrams.md`](diagrams.md) and the concept chapters for alternatives.

## What a production discovery phase would still ask

- What staleness is acceptable for each workflow?
- What are the partner's documented quotas and recovery behavior?
- Which writes have idempotency support?
- What latency and availability objectives matter to users?
- How many application instances share the dependency budget?
- What data classification and retention rules apply?
