# checkout runbook

The checkout service (orchestrates the order placement flow — cart fetch → payment authorization → shipping calc → email confirmation → kafka publish for accounting/fraud).

## Primary signals

- `http_server_request_duration_seconds_count{service="checkout", status_code=~"5.."}` — 5xx rate
- p95 latency on the service's primary RPC/endpoints
- `app_orders_placed_total` — successful orders counter
- `app_orders_failed_total` — failure counter (incremented per failure cause)

## Symptoms → severity guide

| Pattern | Severity |
|---|---|
| 5xx rate on `/checkout/place` > 5% | P1 (revenue impact) |
| `app_orders_failed_total` increasing without 5xx (silent failure) | P1 (orders silently lost) |
| p95 latency > 5s | P2 (slow checkout) |

## Common causes

1. **Downstream failure cascading up** — Payment or shipping or cart returned an error; checkout faithfully propagated the failure. The first place to look is the trace fan-out for the failing order.
2. **Bad deploy in `src/checkout/`** — Less common but always check.
3. **Kafka publish failure** — Order succeeds but the post-order event publish to kafka fails; downstream services (accounting, fraud) miss the order.

## Triage steps

1. **Check recent deploys**: `git log --oneline -10 src/checkout/`
2. **Tail logs**: `{service="checkout"} | json | level=~"error|warn"`
3. **Pull error spans from Tempo**: `service.name = "checkout" AND status = ERROR`, group by `attributes.error.message`
4. **Check pod health**: `kubectl top pod -l app=checkout; kubectl get pod -l app=checkout -o wide`
5. **Check downstream dependencies** (see Related Services below) — failures often cascade from upstream

## Common fixes

| Diagnosis | Fix |
|---|---|
| Downstream service is the real culprit | Triage that service per its runbook; checkout heals when the downstream does. |
| Bad deploy | Revert offending commit on `src/checkout/`. |
| Kafka publish failure | Check kafka health; consider adding retry-with-backoff to the publish call in `src/checkout/`. |

## What "good" looks like

5xx rate < 0.1% on `/checkout/place`, p95 < 1.5s, every successful response has a corresponding kafka event consumed by accounting+fraud-detection.

## Related services

- **cart** — see `cart.md` runbook for triage steps
- **payment** — see `payment.md` runbook for triage steps
- **shipping** — see `shipping.md` runbook for triage steps
- **currency** — see `currency.md` runbook for triage steps
- **email** — see `email.md` runbook for triage steps
- **kafka** — see `kafka.md` runbook for triage steps
- **accounting** — see `accounting.md` runbook for triage steps
- **fraud-detection** — see `fraud-detection.md` runbook for triage steps
