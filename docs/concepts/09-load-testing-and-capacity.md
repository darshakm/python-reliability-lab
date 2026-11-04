# 9. Load Testing and Capacity

**Problem:** Correct code can still fail its latency or capacity objective under
realistic offered load.

**Invariant:** Claims name workload, environment, sample size, metric, and
limitations. Throughput and p50/p95 are interpreted with the dependency boundary.

The concurrency benchmark finds a knee rather than a universal best value. CPU
and memory profiles justify optimization only for the measured workload.

**Does not solve:** Production capacity prediction from synthetic local results.

**Tradeoff:** Deterministic tests improve reproducibility while omitting network,
hardware, and neighboring-service variation.

**Explore:** Plot worker count against throughput and p95 from repeated
`concurrency` experiments. Identify the bottleneck before proposing changes.
