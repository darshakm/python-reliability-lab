# Unit 3 Failure Matrix

The classifier and composition tests automate these policies. “Retry” still
means bounded by maximum attempts, elapsed time, backoff, jitter, rate limiting,
and cancellation.

| Operation | Failure | Retry? | Reason |
|---|---|---:|---|
| Safe or idempotent | Request timeout | Yes | Outcome may be unknown, but repeating is safe by contract |
| Safe or idempotent | Network failure | Yes | Usually transient; no permanent client correction is identified |
| Safe or idempotent | HTTP 429 | Yes | Transient capacity signal; honor bounded `Retry-After` |
| Safe or idempotent | HTTP 500–599 | Yes | Server-side transient candidate |
| Safe or idempotent | HTTP 400/404 | No | Retrying unchanged input will not repair the request or missing resource |
| Safe or idempotent | HTTP 401/403 | No | Credentials or permissions require correction |
| Safe or idempotent | Malformed payload | No | Contract/data problem requires investigation or quarantine |
| Unsafe write | Any failure | No | Repetition may duplicate the side effect |
| Any operation | Cancellation | No | Workflow control must stop immediately |

Every physical attempt acquires a rate-limit token. This prevents retries from
bypassing the same upstream capacity policy applied to initial attempts.
