# Python Reliability Lab

An executable study companion for learning how production integrations behave
under concurrency, overload, partial failure, and recovery. It combines typed
Python reference implementations, runnable experiments, guided exercises, and
the design reasoning expected in Forward Deployed Engineering work.

The project uses synthetic order data and a simulated dependency. It is a
learning and portfolio artifact, not a hosted production service.

## The customer problem

A retailer depends on an unreliable partner order API. Support and fulfillment
workflows need useful results even when responses are slow, malformed,
rate-limited, or temporarily unavailable. Bursts must not overwhelm the partner,
one failed order must not discard a batch, and recovery must not trigger another
traffic storm.

Read the full [customer scenario](docs/customer-scenario.md), including outcomes,
constraints, success measures, and discovery questions.

## What this demonstrates

| FDE competency | Evidence in this project |
|---|---|
| Customer problem framing | Scenario, constraints, success measures, and open discovery questions |
| Integration engineering | Authenticated HTTP, canonical domain validation, and explicit failure types |
| Reliability judgment | Bounded concurrency, deadlines, retries, limiting, breaker, and stale policy |
| System design | Composition diagrams, alternatives, invariants, and production evolution |
| Operational readiness | Correlated events, fault injection, runbook, load tests, and profiling |
| Technical communication | Ten concept chapters, guided exercises, ADRs, and interview prompts |
| Delivery discipline | Strict typing, linting, 165 tests, package verification, and releases |

## Five-minute experiment

Python 3.12 or newer and Git are required.

```bash
git clone https://github.com/darshakm/python-reliability-lab.git
cd python-reliability-lab
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install '.[dev]'

reliability-lab concurrency --orders 40 --workers 8 --upstream-capacity 4
reliability-lab outage --failures 2 --retries 3
reliability-lab cache-stampede --callers 20 --single-flight on
reliability-lab recovery --threshold 3 --recovery-timeout 10
```

Each command prints JSON with observable outcomes such as throughput, p50/p95,
physical attempts, dependency calls, peak concurrency, and breaker transitions.
Change one parameter at a time and explain why the result changes.

Try the most visible comparison:

```bash
reliability-lab cache-stampede --callers 50 --single-flight off
reliability-lab cache-stampede --callers 50 --single-flight on
```

With protection enabled, all callers share one dependency load. Equal returned
values alone do not prove protection; `dependency_calls` does.

## Architecture

```text
Batch worker
    -> resilient order reader
        -> TTL/LRU cache and per-key single-flight
            -> circuit breaker
                -> safe-operation retry policy
                    -> token bucket per physical attempt
                        -> typed HTTP client
                            -> immutable Order validation
```

A cache hit performs no dependency work. On a miss, the breaker admits one
logical operation; retry handles bounded transient recovery; every physical
attempt consumes rate capacity; the client parses the response; and the domain
model validates it before caching.

This ordering is deliberate: the breaker counts the final logical outcome, while
the limiter counts every physical attempt. See the complete
[architecture and failure diagrams](docs/diagrams.md).

## Study the concepts

| Chapter | Central design question |
|---|---|
| [1. Boundaries and domain models](docs/concepts/01-boundaries-and-domain-models.md) | Where does untrusted data become trusted? |
| [2. Bounded concurrency](docs/concepts/02-bounded-concurrency.md) | How do we bound waiting work, not only active calls? |
| [3. Timeouts and cancellation](docs/concepts/03-timeouts-and-cancellation.md) | Who owns time and workflow termination? |
| [4. Retries and idempotency](docs/concepts/04-retries-and-idempotency.md) | Which failures and operations are safe to repeat? |
| [5. Rate limiting and backpressure](docs/concepts/05-rate-limiting-and-backpressure.md) | How do rate, burst, and concurrency differ? |
| [6. Circuit breakers](docs/concepts/06-circuit-breakers.md) | When should dependency work stop? |
| [7. Caching and stampede control](docs/concepts/07-caching-and-stampede-control.md) | How do concurrent misses share work safely? |
| [8. Observability](docs/concepts/08-observability.md) | How does one logical request map to attempts? |
| [9. Load testing and capacity](docs/concepts/09-load-testing-and-capacity.md) | What does the measured bottleneck actually prove? |
| [10. Composition](docs/concepts/10-composing-reliability-patterns.md) | Which layer owns recovery, protection, and fallback? |

Choose a [30-minute, two-hour, or half-day learning path](docs/learning-paths.md).
Then use the [guided exercises](docs/exercises.md), separate
[discussion guide](docs/solutions.md), and [interview guide](docs/interview-guide.md)
to trace, diagnose, change, and defend the design.

## Reliability contracts

- External payloads become trusted only after exact boundary validation.
- Batch creation and active dependency work remain bounded.
- Item failures retain their input ID; workflow cancellation propagates.
- Unsafe writes are not retried without server-enforced idempotency.
- Every physical retry consumes rate-limit capacity.
- The breaker counts final logical availability failures, not each retry.
- Concurrent misses for one key share a cancellation-protected load.
- Stale values require a bounded window and an explicitly eligible failure.
- Correlation excludes credentials, full payloads, and sensitive error text.

## Run and verify everything

```bash
python3 -m pytest
python3 -m ruff check .
python3 -m mypy
python3 examples/order_model.py
python3 examples/resilient_read.py
```

The current snapshot has 167 tests plus passing Ruff and strict mypy. The
`v1.0.0` release was verified on Python 3.14.6 and macOS arm64. The package
declares Python 3.12 or newer; 3.12 and 3.13 still require independent
compatibility verification.

## Evidence and operations

- [Concurrency benchmark](docs/unit-2-benchmark.md)
- [Retry/rate-limit design and failure matrix](docs/unit-3-retry-design.md)
- [Circuit-breaker/cache design](docs/unit-4-circuit-breaker-design.md)
- [Integration, load, and profiling report](docs/unit-5-integration-load-profile-report.md)
- [Technical article](docs/reliable-python-integrations.md)
- [Order integration runbook](docs/runbook.md)
- [Production evolution](docs/production-evolution.md)
- [Release verification](docs/release-verification.md)
- [Continuous verification](https://github.com/darshakm/python-reliability-lab/actions)
- [Changelog](CHANGELOG.md) and [1.0.0 release notes](docs/release-notes-1.0.0-draft.md)

Performance results are controlled local synthetic measurements, not production
capacity claims. Each report records its workload and limitations.

## Production boundaries

The reference implementation is single-process and in-memory. Its cache,
limiter, breaker, and single-flight map are not shared across instances. The
production HTTP client is synchronous; async composition uses a thread adapter
whose cancellation cannot stop an already-running thread. Telemetry is an
in-memory teaching implementation, not an observability backend.

The [production evolution guide](docs/production-evolution.md) explains when to
consider a native async client, shared cache, gateway or distributed limiting,
OpenTelemetry, contract testing, and external configuration.

## Project layout

```text
src/reliability_lab/   implementation and experiment CLI
tests/                 unit, integration, fault, and CLI tests
examples/              small model and resilient-read examples
benchmarks/            reproducible concurrency and load scripts
docs/concepts/         system-design study chapters
docs/                  scenario, exercises, diagrams, evidence, and runbook
```

## Build and inspect the package

Build from the development environment, inspect both archives, and install the
wheel into a separate consumer environment so local source and development
dependencies cannot hide packaging errors.

```bash
rm -rf dist
python3 -m build
python3 -m zipfile --list dist/python_reliability_lab-1.0.0-py3-none-any.whl
python3 -m tarfile --list dist/python_reliability_lab-1.0.0.tar.gz

deactivate
consumer_dir="$(mktemp -d /tmp/python-reliability-lab-wheel.XXXXXX)"
python3 -m venv "$consumer_dir/venv"
source "$consumer_dir/venv/bin/activate"
python3 -m pip install dist/python_reliability_lab-1.0.0-py3-none-any.whl
python3 -m pip check

cd /tmp
python3 -c 'from importlib.metadata import version; print(version("python-reliability-lab"))'
python3 -c 'import reliability_lab; print(reliability_lab.__file__)'
reliability-lab recovery --threshold 2
```

The expected version is `1.0.0`; the module and command should resolve from the
temporary consumer environment. Verified artifacts are attached to the public
[v1.0.0 release](https://github.com/darshakm/python-reliability-lab/releases/tag/v1.0.0).

## License

MIT. See [LICENSE](LICENSE).
