# fraud-detection runbook

The fraud-detection service (consumes order events from kafka and applies fraud heuristics; flags suspicious orders).

## Primary signals

- `http_server_request_duration_seconds_count{service="fraud-detection", status_code=~"5.."}` — 5xx rate
- p95 latency on the service's primary RPC/endpoints
- Kafka consumer lag: `kafka_consumergroup_lag{group="fraud-detection"}`
- `app_fraud_flags_total` — flag rate

## Symptoms → severity guide

| Pattern | Severity |
|---|---|
| Consumer lag > 1000 | P3 (fraud check delayed) |
| Flag rate spikes 10x baseline | P3 (either model regression or actual fraud surge) |
| CrashLoopBackOff | P2 |

## Common causes

1. **Bad deploy in `src/fraud-detection/`** — Check git log.
2. **Slow JVM startup** — Cold pods take time to warm up.
3. **Model logic regression** — Recent change increased false-positive rate.

## Triage steps

1. **Check recent deploys**: `git log --oneline -10 src/fraud-detection/`
2. **Tail logs**: `{service="fraud-detection"} | json | level=~"error|warn"`
3. **Pull error spans from Tempo**: `service.name = "fraud-detection" AND status = ERROR`, group by `attributes.error.message`
4. **Check pod health**: `kubectl top pod -l app=fraud-detection; kubectl get pod -l app=fraud-detection -o wide`
5. **Check downstream dependencies** (see Related Services below) — failures often cascade from upstream

## Common fixes

| Diagnosis | Fix |
|---|---|
| Bad deploy | Revert. |
| Slow startup | Increase startup probe initial delay in `chart/values.yaml`. |
| Logic regression | Patch heuristics in `src/fraud-detection/`. |

## What "good" looks like

Consumer lag < 100, flag rate within baseline range, no crash loops.

## Related services

- **kafka** — see `kafka.md` runbook for triage steps
- **checkout** — see `checkout.md` runbook for triage steps
