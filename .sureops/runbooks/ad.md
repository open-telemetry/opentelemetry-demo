# ad runbook

The ad service (serves contextual ads on the frontend (banner, sidebar, recommendation panel)).

## Primary signals

- `http_server_request_duration_seconds_count{service="ad", status_code=~"5.."}` — 5xx rate
- p95 latency on the service's primary RPC/endpoints
- JVM heap usage: `jvm_memory_used_bytes{area="heap"}` — leaks cause OOM
- GC pause times: `jvm_gc_pause_seconds`

## Symptoms → severity guide

| Pattern | Severity |
|---|---|
| 5xx rate on `/ad/get` > 5% | P3 (ads degraded, non-blocking) |
| JVM heap > 90% of max for >5min | P3 (GC thrashing imminent) |
| OOMKilled in last hour | P2 (cascading restarts) |
| p95 latency > 1s | P3 (slow page render) |

## Common causes

1. **Bad deploy in `src/ad/`** — Most common; check `git log -10 src/ad/`.
2. **JVM heap leak** — Long-running pods accumulate heap; eventually OOM. Often the same root cause as a deploy regression.
3. **Excessive GC pressure** — Either heap is too small for current load or there's an allocation hot path in code.
4. **Slow upstream (product-catalog)** — Ad service calls product-catalog to filter ads by relevance.

## Triage steps

1. **Check recent deploys**: `git log --oneline -10 src/ad/`
2. **Tail logs**: `{service="ad"} | json | level=~"error|warn"`
3. **Pull error spans from Tempo**: `service.name = "ad" AND status = ERROR`, group by `attributes.error.message`
4. **Check pod health**: `kubectl top pod -l app=ad; kubectl get pod -l app=ad -o wide`
5. **Check downstream dependencies** (see Related Services below) — failures often cascade from upstream

## Common fixes

| Diagnosis | Fix |
|---|---|
| Bad deploy | Revert offending commit on `src/ad/`. |
| Heap leak | Find allocation hot path in code; add heap dump on OOM via `chart/values.yaml`. Patch source to bound the leak. |
| GC pressure | Bump JVM heap in `chart/values.yaml` `components.ad.env.JAVA_TOOL_OPTIONS`; or fix allocation patterns in code. |

## What "good" looks like

5xx rate < 0.1%, p95 < 300ms, JVM heap stable < 70% of max, zero OOMKilled events.

## Related services

- **product-catalog** — see `product-catalog.md` runbook for triage steps
- **frontend** — see `frontend.md` runbook for triage steps
