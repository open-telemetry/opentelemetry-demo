# load-generator runbook

The load-generator service (synthetic load generator; simulates user traffic on the storefront for demo purposes).

## Primary signals

- `http_server_request_duration_seconds_count{service="load-generator", status_code=~"5.."}` — 5xx rate
- p95 latency on the service's primary RPC/endpoints
- locust user count
- Request rate generated

## Symptoms → severity guide

| Pattern | Severity |
|---|---|
| Pod down (no synthetic traffic) | P3 (demo loses realistic baseline traffic) |
| Request rate dropped to 0 | P3 (same) |

## Common causes

1. **Bad deploy in `src/load-generator/`** — Check git log.
2. **Pod resource limits hit** — Under high load, locust pod can OOM.

## Triage steps

1. **Check recent deploys**: `git log --oneline -10 src/load-generator/`
2. **Tail logs**: `{service="load-generator"} | json | level=~"error|warn"`
3. **Pull error spans from Tempo**: `service.name = "load-generator" AND status = ERROR`, group by `attributes.error.message`
4. **Check pod health**: `kubectl top pod -l app=load-generator; kubectl get pod -l app=load-generator -o wide`
5. **Check downstream dependencies** (see Related Services below) — failures often cascade from upstream

## Common fixes

| Diagnosis | Fix |
|---|---|
| Bad deploy | Revert. |
| Resources | Bump in `chart/values.yaml`. |

## What "good" looks like

Steady request rate; no crash loops.

## Related services

- **frontend** — see `frontend.md` runbook for triage steps
- **frontend-proxy** — see `frontend-proxy.md` runbook for triage steps
