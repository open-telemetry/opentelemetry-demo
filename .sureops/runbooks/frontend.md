# frontend runbook

The frontend service (the public web storefront — every customer-facing request lands here first).

## Primary signals

- `http_server_request_duration_seconds_count{service="frontend", status_code=~"5.."}` — 5xx rate
- p95 latency on the service's primary RPC/endpoints
- Frontend RUM metrics if exposed: page load time, error count
- Readiness probe pass/fail

## Symptoms → severity guide

| Pattern | Severity |
|---|---|
| Readiness probe failing > 1min | P1 (pod removed from service, customers can't reach the site) |
| 5xx on `/` > 5% | P1 (storefront broken) |
| p95 page load > 5s | P2 (UX degraded) |

## Common causes

1. **Bad deploy in `src/frontend/`** — Most common.
2. **Failed readiness probe** — Pod is up but the probe endpoint returns non-200. Check what the probe is checking.
3. **Downstream BFF call failures** — Frontend calls product-catalog, recommendation, ad, etc. via the frontend-proxy; cascading failures show up as 5xx here.

## Triage steps

1. **Check recent deploys**: `git log --oneline -10 src/frontend/`
2. **Tail logs**: `{service="frontend"} | json | level=~"error|warn"`
3. **Pull error spans from Tempo**: `service.name = "frontend" AND status = ERROR`, group by `attributes.error.message`
4. **Check pod health**: `kubectl top pod -l app=frontend; kubectl get pod -l app=frontend -o wide`
5. **Check downstream dependencies** (see Related Services below) — failures often cascade from upstream

## Common fixes

| Diagnosis | Fix |
|---|---|
| Bad deploy | Revert. |
| Readiness probe | If the probe checks downstream connectivity, the failure may be downstream — fix the actual dependency. If the probe checks an internal endpoint that's flaky, fix the probe in `chart/values.yaml`. |
| Cascading downstream | Triage the actual failing downstream service per its runbook. |

## What "good" looks like

Readiness probe consistently passing, 5xx < 0.1%, p95 page load < 2s.

## Related services

- **frontend-proxy** — see `frontend-proxy.md` runbook for triage steps
- **product-catalog** — see `product-catalog.md` runbook for triage steps
- **cart** — see `cart.md` runbook for triage steps
- **recommendation** — see `recommendation.md` runbook for triage steps
- **ad** — see `ad.md` runbook for triage steps
