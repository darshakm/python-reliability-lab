# 8. Observability and Correlation

**Problem:** A logical request can produce several physical attempts across
layers, making failures hard to reconstruct.

**Invariant:** A trace ID correlates logical start/outcome events with dependency
attempt observations without storing credentials, payloads, or sensitive error
messages.

Useful signals include attempts per request, active and peak concurrency,
outcome class, breaker state, rate-limit wait, cache behavior, and tail latency.

**Does not solve:** Production telemetry transport, retention, sampling, or
cardinality governance.

**Tradeoff:** More detail improves diagnosis but increases cost and privacy risk.

**Explore:** Trace the context variable from `TracedOrderReader` into
`ScriptedOrderSource` and list which fields you would exclude in production.
