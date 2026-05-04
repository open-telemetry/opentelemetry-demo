# accounting runbook

The accounting service (consumes order events from kafka and writes to postgresql for finance reporting).

## Primary signals

- `http_server_request_duration_seconds_count{service="accounting", status_code=~"5.."}` — 5xx rate
- p95 latency on the service's primary RPC/endpoints
- Kafka consumer lag: `kafka_consumergroup_lag{group="accounting"}`
- Postgres connection pool metrics

## Symptoms → severity guide

| Pattern | Severity |
|---|---|
| Kafka consumer lag > 1000 messages | P3 (finance data behind) |
| Postgres connection failures | P2 (writes failing) |
| Pod CrashLoopBackOff | P2 (no events being processed) |

## Common causes

1. **Postgres unreachable** — DB pod down or connection issue.
2. **Bad deploy in `src/accounting/`** — Check git log.
3. **Slow consume loop** — Code is slow at processing each kafka message; lag grows.

## Triage steps

1. **Check recent deploys**: `git log --oneline -10 src/accounting/`
2. **Tail logs**: `{service="accounting"} | json | level=~"error|warn"`
3. **Pull error spans from Tempo**: `service.name = "accounting" AND status = ERROR`, group by `attributes.error.message`
4. **Check pod health**: `kubectl top pod -l app=accounting; kubectl get pod -l app=accounting -o wide`
5. **Check downstream dependencies** (see Related Services below) — failures often cascade from upstream

## Common fixes

| Diagnosis | Fix |
|---|---|
| Postgres down | Restart postgresql pod; investigate root cause. |
| Bad deploy | Revert. |
| Slow consume | Profile consume loop; batch operations; PR against `src/accounting/`. |

## What "good" looks like

Consumer lag < 50 messages, zero crash loops, postgres pool healthy.

## Related services

- **kafka** — see `kafka.md` runbook for triage steps
- **postgresql** — see `postgresql.md` runbook for triage steps
- **checkout** — see `checkout.md` runbook for triage steps
