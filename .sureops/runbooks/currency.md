# currency runbook

The currency service (converts product prices between currencies. Called at every product render and checkout.).

## Primary signals

- `http_server_request_duration_seconds_count{service="currency", status_code=~"5.."}` — 5xx rate
- p95 latency on the service's primary RPC/endpoints
- Trace span `currency.Convert`
- gRPC error rate

## Symptoms → severity guide

| Pattern | Severity |
|---|---|
| 5xx > 5% | P2 (price rendering broken) |
| p95 > 100ms | P3 (page slow) |

## Common causes

1. **Bad deploy in `src/currency/`** — Check `git log -10 src/currency/`.
2. **Stale exchange rate data** — If rates are loaded from disk/external source and the source is broken.
3. **Crash on specific currency code** — Some inputs trigger a crash; symptoms concentrate on specific source/target currency pairs.

## Triage steps

1. **Check recent deploys**: `git log --oneline -10 src/currency/`
2. **Tail logs**: `{service="currency"} | json | level=~"error|warn"`
3. **Pull error spans from Tempo**: `service.name = "currency" AND status = ERROR`, group by `attributes.error.message`
4. **Check pod health**: `kubectl top pod -l app=currency; kubectl get pod -l app=currency -o wide`
5. **Check downstream dependencies** (see Related Services below) — failures often cascade from upstream

## Common fixes

| Diagnosis | Fix |
|---|---|
| Bad deploy | Revert. |
| Stale data | Rebuild image with fresh rate data, or fix the loader to handle missing data gracefully. |
| Crash on input | Patch validation in `src/currency/`. |

## What "good" looks like

5xx < 0.01%, p95 < 50ms.

## Related services

- **product-catalog** — see `product-catalog.md` runbook for triage steps
- **checkout** — see `checkout.md` runbook for triage steps
