# quote runbook

The quote service (calculates shipping quotes based on weight + distance. Called by shipping service.).

## Primary signals

- `http_server_request_duration_seconds_count{service="quote", status_code=~"5.."}` — 5xx rate
- p95 latency on the service's primary RPC/endpoints
- HTTP server metrics from PHP-FPM
- p95 latency

## Symptoms → severity guide

| Pattern | Severity |
|---|---|
| 5xx > 5% | P3 (shipping quote unavailable, fallback to default) |
| p95 > 1s | P3 (slow checkout) |

## Common causes

1. **Bad deploy in `src/quote/`** — Check git log.
2. **PHP-FPM worker exhaustion under load** — Spike in checkout traffic exhausts the worker pool.
3. **Slow PHP page in calculation** — Specific weight/distance inputs trigger slow code paths.

## Triage steps

1. **Check recent deploys**: `git log --oneline -10 src/quote/`
2. **Tail logs**: `{service="quote"} | json | level=~"error|warn"`
3. **Pull error spans from Tempo**: `service.name = "quote" AND status = ERROR`, group by `attributes.error.message`
4. **Check pod health**: `kubectl top pod -l app=quote; kubectl get pod -l app=quote -o wide`
5. **Check downstream dependencies** (see Related Services below) — failures often cascade from upstream

## Common fixes

| Diagnosis | Fix |
|---|---|
| Bad deploy | Revert. |
| Worker exhaustion | Increase `pm.max_children` in PHP-FPM config in `src/quote/`. |
| Slow calculation | Profile PHP execution; optimize hot path. |

## What "good" looks like

5xx < 0.5%, p95 < 200ms.

## Related services

- **shipping** — see `shipping.md` runbook for triage steps
