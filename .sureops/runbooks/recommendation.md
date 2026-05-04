# recommendation runbook

The recommendation service generates personalized product recommendations
shown on the homepage and product detail pages. Failures here degrade
discovery but don't block purchases — checkout works without it.

## Primary signals

- `http_server_request_duration_seconds_count{service="recommendation", status_code=~"5.."}` — 5xx rate
- `process_resident_memory_bytes{service="recommendation"}` — memory growth
- Pod metrics: OOMKilled events, restart count
- `app.recommendations.counter` — successful recommendation count

## Symptoms → severity guide

| Pattern | Severity |
|---|---|
| Memory growth > 50%/hour with no traffic increase | P3 (will OOM) |
| OOMKilled within last hour | P2 (cascading restarts) |
| 5xx rate > 10% sustained | P3 (homepage degraded) |
| p95 latency > 5s | P3 (slow homepage) |

## Common causes

1. **Memory leak in caching layer** — the recommendation service caches
   computed results to avoid recomputing for repeat requests. A leak in the
   cache eviction logic causes memory to grow unboundedly until OOMKill.
   This is the **most common failure mode**; check first.
2. **Slow upstream catalog** — recommendation calls product-catalog to
   fetch product metadata. If product-catalog is slow, recommendation
   accumulates pending requests in memory.
3. **Bad recent deploy** — code change in `src/recommendation/` that
   introduced a regression.
4. **Downstream model service slow (LLM)** — if the recommendation
   service calls an external LLM API, slow responses lead to elongated
   request lifetimes and increased memory pressure.

## Triage steps

1. **Check memory trajectory**:
   ```
   kubectl top pod -l app=recommendation
   ```
   If memory is monotonically increasing with no plateau, that's a leak,
   not just load.

2. **Check restart history**:
   ```
   kubectl get pod -l app=recommendation -o jsonpath='{.items[*].status.containerStatuses[*].restartCount}'
   ```
   Restart count > 3 in the last hour = recurring OOM.

3. **Look at the source for cache logic**:
   ```
   git log --oneline -10 src/recommendation/
   grep -rn "cache" src/recommendation/recommendation_server.py
   ```

4. **Tail logs**:
   ```
   {service="recommendation"} | json | level="error"
   ```

5. **Check upstream**:
   - product-catalog latency: trace `recommendation → product-catalog` p95
   - LLM service (if used): external HTTP call durations from traces

## Common fixes

| Diagnosis | Fix |
|---|---|
| Memory leak in cache | Find unbounded data structure in `recommendation_server.py`; bound it with LRU or fix eviction. PR against `src/recommendation/`. |
| Slow upstream | Add timeout + circuit breaker in `recommendation_server.py` for product-catalog calls. |
| Bad deploy | Revert offending commit. |
| LLM-induced slowness | Add timeout for the LLM call; degrade to non-personalized fallback. |

## What "good" looks like

- Memory usage stable < 70% of limit, sawtooth pattern (cache-fill → eviction)
- 5xx rate < 0.1%
- p95 latency < 1s
- Zero OOMKilled events in last 24h

## Related services

- **product-catalog** — recommendation calls it for each request. Recommendation
  perf is often capped by catalog perf.
- **frontend** — consumes recommendations. Empty recommendation lists usually
  indicate this service is degraded.
