# Unit 2 Async Worker Benchmark

## Question

How does throughput change as worker concurrency increases, and where does added
concurrency stop helping when the upstream dependency has finite capacity?

## Method

- 100 order fetches per run
- 20 ms deterministic simulated service latency
- Simulated upstream capacity: 8 active requests
- 5 repetitions per worker-concurrency setting
- Reported value: median elapsed time and derived throughput
- Environment: Python 3.14.6, macOS 26.6.2, arm64

Run from an installed development environment:

```bash
python3 benchmarks/async_worker_benchmark.py
```

## Results

| Worker concurrency | Median seconds | Orders/second |
|---:|---:|---:|
| 1 | 2.110291 | 47.39 |
| 2 | 1.052897 | 94.98 |
| 4 | 0.528086 | 189.36 |
| 8 | 0.274669 | 364.08 |
| 16 | 0.276299 | 361.93 |
| 32 | 0.275870 | 362.49 |

## Interpretation

The knee is concurrency 8, matching the fake dependency's capacity. Throughput
scales almost linearly through 8 and then plateaus. Increasing worker concurrency
to 16 or 32 adds queued work without improving throughput. For this scenario, 8
is the smallest setting that reaches maximum useful throughput.

This is not a production capacity claim. Real selection must measure connection
pools, dependency limits, tail latency, error rate, memory, and rate limiting.
The benchmark isolates the relationship between worker concurrency and a known
upstream capacity.
