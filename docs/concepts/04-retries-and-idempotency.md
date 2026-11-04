# 4. Retries and Idempotency

**Problem:** Transient failures may recover, but blind retries multiply load and
can duplicate side effects.

**Invariant:** Only safe or server-idempotent operations retry, only classified
transient failures qualify, and attempt plus elapsed-time budgets are bounded.

Backoff creates recovery space; jitter avoids synchronized clients; bounded
`Retry-After` incorporates server guidance. Attempt history preserves diagnosis.

**Does not solve:** Sustained outage isolation or request-rate control.

**Tradeoff:** More attempts may improve isolated success while worsening tail
latency and dependency load.

**Explore:** Vary failures and retry budget with `reliability-lab outage`. Then
explain why a POST without a server-enforced idempotency key is unsafe.
