# Production Evolution

This lab intentionally keeps mechanisms inspectable. Production choices depend
on customer constraints and should not be implied by a reference implementation.

| Current boundary | Production evolution | Decision trigger |
|---|---|---|
| In-memory TTL/LRU cache | Redis or managed shared cache | Cross-instance reuse is worth consistency and operational cost |
| Process-local token bucket | API gateway or distributed limiter | Quota is fleet-wide rather than per instance |
| Process-local breaker | Local breakers plus fleet telemetry | Fast local isolation remains useful; shared state needs careful failure semantics |
| Synchronous HTTP + thread adapter | Native async pooled client | Sustained high async concurrency |
| In-memory trace recorder | OpenTelemetry metrics, logs, and traces | Production diagnosis and retention requirements |
| Synthetic fault source | Staging contract tests and controlled fault injection | Partner sandbox or safe test environment exists |
| Fixed package configuration | External typed configuration and secret manager | Multiple environments and credential rotation |
| One order schema | Versioned canonical model and migration policy | Multiple source systems or evolving contracts |

## Multi-instance architecture questions

- Is the dependency quota global, regional, tenant-specific, or credential-specific?
- Can stale values cross tenant or authorization boundaries?
- Does breaker state need to be shared, or would shared failure amplify outages?
- How are retries deduplicated after process loss?
- Which metrics have bounded cardinality?
- What is the rollback path for schema and cache changes?

## Suggested staged rollout

1. Add production telemetry while retaining local mechanisms.
2. Measure real limits and define user-facing SLOs.
3. Move only the state that requires cross-instance coordination.
4. Introduce canary traffic and compare error, latency, and dependency load.
5. Rehearse partner outage, credential failure, rollback, and stale-data disablement.
