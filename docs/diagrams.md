# Architecture and Failure Diagrams

## End-to-end read path

```mermaid
flowchart LR
    Caller --> Worker[Bounded worker pool]
    Worker --> Cache[TTL/LRU cache]
    Cache --> Breaker[Circuit breaker]
    Breaker --> Retry[Safe retry policy]
    Retry --> Limiter[Token bucket per attempt]
    Limiter --> Client[Typed HTTP client]
    Client --> Model[Order validation]
    Client --> API[Partner API]
```

## Why the order matters

```text
cache hit ───────────────────────────────────────────────> return
cache miss -> breaker admission -> logical retry operation
                                  ├─ limiter -> attempt 1
                                  ├─ limiter -> attempt 2
                                  └─ limiter -> attempt 3
final logical outcome -> breaker accounting -> cache/store or stale policy
```

The breaker sees one logical result, while the limiter sees every physical
attempt. Reversing those boundaries either opens the breaker too aggressively or
allows retries to bypass rate control.

## Circuit breaker state machine

```mermaid
stateDiagram-v2
    [*] --> Closed
    Closed --> Open: failure threshold reached
    Open --> Open: reject before recovery timeout
    Open --> HalfOpen: timeout elapsed
    HalfOpen --> Closed: one probe succeeds
    HalfOpen --> Open: probe fails
```

## Cache single-flight

```mermaid
sequenceDiagram
    participant A as Caller A
    participant B as Caller B
    participant C as Cache
    participant D as Dependency
    A->>C: get(key)
    C->>D: start shared load
    B->>C: get(key)
    C-->>B: await shared load
    D-->>C: value
    C-->>A: value
    C-->>B: value
```

## Deadline hierarchy

```text
overall batch deadline
├── worker 1: request timeout -> item failure -> next item
├── worker 2: success -> next item
└── worker 3: still active when batch deadline expires -> cancellation
```

Per-request timeout is an item outcome. Overall timeout stops the workflow and
returns completed and pending context through `BatchDeadlineExceeded`.
