# Python Reliability Lab

A typed Python integration that stays predictable when an upstream API is slow,
malformed, rate-limited, or unavailable. The project is a learning and portfolio
artifact built with synthetic data; it is not a production service.

## What it demonstrates

- Immutable domain validation at an untrusted API boundary
- Authenticated HTTP with explicit public failure types
- Bounded async concurrency, deadlines, partial results, and cancellation
- Safe/idempotent retries with backoff, jitter, `Retry-After`, and budgets
- Concurrent token-bucket rate limiting
- Closed/open/half-open circuit breaking
- Bounded TTL/LRU caching, stampede control, invalidation, and stale fallback
- Deterministic and real loopback fault injection
- Correlated events, load measurement, CPU/memory profiling, and optimization

## Five-minute path

Python 3.12 or newer is required.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install '.[dev]'

python3 -m pytest
python3 -m ruff check .
python3 -m mypy
python3 examples/order_model.py
python3 examples/resilient_read.py
```

Expected verification snapshot on the documented local environment: 159 tests,
Ruff, and strict mypy pass. Exact test count may increase as the project evolves.

## Architecture

```text
Batch worker
    -> resilient order reader
        -> TTL/LRU cache
            -> circuit breaker
                -> safe-operation retry policy
                    -> token bucket per physical attempt
                        -> typed HTTP client
                            -> Order boundary validation
```

A fresh cache hit performs no dependency work. A miss is admitted by the circuit
breaker, retried only when safe, rate-limited on every physical attempt, parsed by
the HTTP client, and validated into an immutable `Order`.

## Basic model example

```python
from reliability_lab import Order

order = Order.from_dict(
    {
        "id": "ord_123",
        "customer_id": "cust_456",
        "status": "shipped",
        "amount": "149.99",
        "currency": "USD",
        "created_at": "2026-10-25T14:30:00Z",
    }
)

print(order.amount)      # Decimal('149.99')
print(order.created_at)  # 2026-10-25 14:30:00+00:00
```

Runnable examples are in [`examples/`](examples/). The HTTP client requires a
real endpoint; tests use an injected transport and a loopback fault server rather
than placeholder URLs.

## Reliability contracts

- External payloads become trusted only after exact known-field validation.
- Ordinary batch failures retain their input ID; cancellation propagates.
- Unsafe writes are never retried automatically.
- Every physical retry consumes rate-limit capacity.
- The breaker counts final logical availability failures, not every retry.
- Stale values are returned only within a bounded window and only for explicitly
  classified availability failures.
- Correlation records omit credentials, full payloads, and exception messages.

## Evidence

- [Async worker design](docs/unit-2-async-design.md) and
  [concurrency benchmark](docs/unit-2-benchmark.md)
- [Retry/rate-limit design](docs/unit-3-retry-design.md) and
  [failure matrix](docs/unit-3-failure-matrix.md)
- [Circuit-breaker/cache design](docs/unit-4-circuit-breaker-design.md)
- [Integration, load, and profiling report](docs/unit-5-integration-load-profile-report.md)
- [Technical article](docs/reliable-python-integrations.md)
- [Changelog](CHANGELOG.md) and
  [draft 1.0.0 release notes](docs/release-notes-1.0.0-draft.md)

All performance results are controlled local synthetic measurements. They are not
production capacity claims; each report records its workload and limitations.

## Project layout

```text
src/reliability_lab/   package implementation
tests/                 unit, integration, fault, and example tests
examples/              runnable five-minute demonstrations
benchmarks/            reproducible concurrency and load scripts
docs/                  decisions, designs, reports, article, and release material
```

## Build and inspect

```bash
python3 -m build
python3 -m pip install dist/python_reliability_lab-1.0.0-py3-none-any.whl
```

Release preparation does not authorize publication. See the
[release checklist](docs/release-checklist.md). No remote, tag, package upload, or
public release should be created without explicit approval.

## License

MIT. See [LICENSE](LICENSE).
