# email runbook

The email service (sends order confirmation emails after a successful checkout (mock SMTP send in demo)).

## Primary signals

- `http_server_request_duration_seconds_count{service="email", status_code=~"5.."}` — 5xx rate
- p95 latency on the service's primary RPC/endpoints
- `process_resident_memory_bytes{service="email"}` — memory growth
- Trace span `email.SendOrderConfirmation`

## Symptoms → severity guide

| Pattern | Severity |
|---|---|
| Memory growth without traffic increase | P3 (will OOM) |
| OOMKilled in last hour | P2 (emails being lost) |
| 5xx on send > 5% | P3 (email delivery failing) |

## Common causes

1. **Memory leak in template/state caching** — Most common cause of OOM here. Email templates can hold references that aren't GC'd.
2. **Bad deploy in `src/email/`** — Less common.
3. **Mock SMTP / external SMTP slow** — Long send times pile up in-flight requests in memory.

## Triage steps

1. **Check recent deploys**: `git log --oneline -10 src/email/`
2. **Tail logs**: `{service="email"} | json | level=~"error|warn"`
3. **Pull error spans from Tempo**: `service.name = "email" AND status = ERROR`, group by `attributes.error.message`
4. **Check pod health**: `kubectl top pod -l app=email; kubectl get pod -l app=email -o wide`
5. **Check downstream dependencies** (see Related Services below) — failures often cascade from upstream

## Common fixes

| Diagnosis | Fix |
|---|---|
| Memory leak | Find unbounded data structure in `src/email/`; bound it. PR + deploy. |
| Bad deploy | Revert. |
| Slow SMTP | Add timeout in `src/email/`; degrade gracefully (queue for later) instead of holding the request open. |

## What "good" looks like

Memory stable < 60% of limit, 5xx < 0.5%, send latency p95 < 1s.

## Related services

- **checkout** — see `checkout.md` runbook for triage steps
