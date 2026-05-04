# frontend-proxy runbook

The frontend-proxy service (edge proxy that routes / fans out frontend requests to backend services).

## Primary signals

- `http_server_request_duration_seconds_count{service="frontend-proxy", status_code=~"5.."}` — 5xx rate
- p95 latency on the service's primary RPC/endpoints
- envoy/nginx access log status code distribution
- Upstream connection error rates

## Symptoms → severity guide

| Pattern | Severity |
|---|---|
| 5xx > 5% | P1 (frontend can't reach backends) |
| Upstream connection failures spiking | P2 (degraded routing) |

## Common causes

1. **Bad config in `src/frontend-proxy/`** — Most common.
2. **Backend pod IPs stale (DNS issue)** — Service discovery not resolving.
3. **Backend service hard down** — Proxy 5xx = backend not reachable.

## Triage steps

1. **Check recent deploys**: `git log --oneline -10 src/frontend-proxy/`
2. **Tail logs**: `{service="frontend-proxy"} | json | level=~"error|warn"`
3. **Pull error spans from Tempo**: `service.name = "frontend-proxy" AND status = ERROR`, group by `attributes.error.message`
4. **Check pod health**: `kubectl top pod -l app=frontend-proxy; kubectl get pod -l app=frontend-proxy -o wide`
5. **Check downstream dependencies** (see Related Services below) — failures often cascade from upstream

## Common fixes

| Diagnosis | Fix |
|---|---|
| Bad config | Revert offending commit on `src/frontend-proxy/`. |
| DNS issue | Restart proxy; investigate cluster DNS. |
| Backend down | Triage the actual backend per its runbook. |

## What "good" looks like

5xx < 0.1%, all upstreams healthy.

## Related services

- **frontend** — see `frontend.md` runbook for triage steps
- **all backend services** — see `all backend services.md` runbook for triage steps
