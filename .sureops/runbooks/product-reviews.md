# product-reviews runbook

The product-reviews service (serves product review data on product detail pages).

## Primary signals

- `http_server_request_duration_seconds_count{service="product-reviews", status_code=~"5.."}` — 5xx rate
- p95 latency on the service's primary RPC/endpoints
- HTTP server metrics, p95 latency

## Symptoms → severity guide

| Pattern | Severity |
|---|---|
| 5xx > 5% | P3 (review section broken on PDPs) |
| p95 > 500ms | P3 (slow PDP) |

## Common causes

1. **Bad deploy in `src/product-reviews/`** — Check git log.
2. **Slow data fetch** — Reviews loaded from disk/embedded data; cold starts slow.

## Triage steps

1. **Check recent deploys**: `git log --oneline -10 src/product-reviews/`
2. **Tail logs**: `{service="product-reviews"} | json | level=~"error|warn"`
3. **Pull error spans from Tempo**: `service.name = "product-reviews" AND status = ERROR`, group by `attributes.error.message`
4. **Check pod health**: `kubectl top pod -l app=product-reviews; kubectl get pod -l app=product-reviews -o wide`
5. **Check downstream dependencies** (see Related Services below) — failures often cascade from upstream

## Common fixes

| Diagnosis | Fix |
|---|---|
| Bad deploy | Revert. |
| Slow fetch | Optimize data loading; consider pre-warm. |

## What "good" looks like

5xx < 0.1%, p95 < 100ms.

## Related services

- **frontend** — see `frontend.md` runbook for triage steps
- **product-catalog** — see `product-catalog.md` runbook for triage steps
