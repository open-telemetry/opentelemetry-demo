# image-provider runbook

The image-provider service (serves static product images. Called heavily on every page render.).

## Primary signals

- `http_server_request_duration_seconds_count{service="image-provider", status_code=~"5.."}` — 5xx rate
- p95 latency on the service's primary RPC/endpoints
- nginx access log latency distribution
- 4xx (missing image) vs 5xx (server error) rates

## Symptoms → severity guide

| Pattern | Severity |
|---|---|
| Image load p95 > 2s | P3 (slow page render) |
| 5xx > 5% | P2 (page render broken) |
| Disk full | P2 (no new images can be served) |

## Common causes

1. **Slow disk I/O** — Most common cause of latency. Check pod disk metrics.
2. **Misconfigured cache headers** — Browsers re-fetch images that should be cached.
3. **Bad nginx config in `src/image-provider/`** — Misroute or wrong root path.

## Triage steps

1. **Check recent deploys**: `git log --oneline -10 src/image-provider/`
2. **Tail logs**: `{service="image-provider"} | json | level=~"error|warn"`
3. **Pull error spans from Tempo**: `service.name = "image-provider" AND status = ERROR`, group by `attributes.error.message`
4. **Check pod health**: `kubectl top pod -l app=image-provider; kubectl get pod -l app=image-provider -o wide`
5. **Check downstream dependencies** (see Related Services below) — failures often cascade from upstream

## Common fixes

| Diagnosis | Fix |
|---|---|
| Slow disk I/O | Check the underlying volume; consider switching to a faster storage class. |
| Cache headers | Patch nginx config in `src/image-provider/` to set proper Cache-Control. |
| Bad config | Revert offending commit. |

## What "good" looks like

Image p95 < 100ms (cached) or < 500ms (cold), 5xx < 0.01%.

## Related services

- **frontend** — see `frontend.md` runbook for triage steps
