# shipping runbook

The shipping service (calculates shipping cost + ETA at checkout time, then publishes shipment-created events to kafka after order placement).

## Primary signals

- `http_server_request_duration_seconds_count{service="shipping", status_code=~"5.."}` — 5xx rate
- p95 latency on the service's primary RPC/endpoints
- Trace span `shipping.GetQuote`, `shipping.ShipOrder` status
- Kafka producer metrics: send rate, error rate, latency

## Symptoms → severity guide

| Pattern | Severity |
|---|---|
| 5xx on `GetQuote` > 5% | P2 (checkout impacted) |
| Kafka publish errors / lag | P3 (downstream consumers behind, not customer-facing) |
| p95 latency > 2s | P3 (slow checkout) |

## Common causes

1. **Bad deploy in `src/shipping/`** — Check `git log -10 src/shipping/`.
2. **Slow upstream quote service** — Shipping calls quote service for rate calculation.
3. **Kafka producer issues** — If the publish call hangs or backs up, request lifetimes inflate.

## Triage steps

1. **Check recent deploys**: `git log --oneline -10 src/shipping/`
2. **Tail logs**: `{service="shipping"} | json | level=~"error|warn"`
3. **Pull error spans from Tempo**: `service.name = "shipping" AND status = ERROR`, group by `attributes.error.message`
4. **Check pod health**: `kubectl top pod -l app=shipping; kubectl get pod -l app=shipping -o wide`
5. **Check downstream dependencies** (see Related Services below) — failures often cascade from upstream

## Common fixes

| Diagnosis | Fix |
|---|---|
| Bad deploy | Revert. |
| Slow upstream | Add timeout + degraded fallback in `src/shipping/`. |
| Kafka producer | Triage kafka per its runbook; consider async publish with retry. |

## What "good" looks like

5xx < 0.1%, p95 < 500ms, kafka publish success rate > 99.9%.

## Related services

- **quote** — see `quote.md` runbook for triage steps
- **checkout** — see `checkout.md` runbook for triage steps
- **kafka** — see `kafka.md` runbook for triage steps
