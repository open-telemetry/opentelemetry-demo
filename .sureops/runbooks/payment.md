# payment runbook

The payment service authorizes credit-card charges during checkout. It's
called by the checkout service for every order; a failure here blocks
every customer purchase.

## Primary signals

- `http_server_request_duration_seconds_count{service="payment", status_code=~"5.."}` — 5xx rate
- `app_orders_failed_total` — counter incremented in checkoutservice when a downstream call fails
- Trace span `payment.charge` status — ERROR rate per minute
- Pod metrics: `container_memory_usage_bytes{container="payment"}` — leaks cause OOM

## Symptoms → severity guide

| Pattern | Severity |
|---|---|
| 5xx rate on `/charge` > 5% sustained for 5 min | P2 (revenue impact) |
| 5xx rate > 50% on `/charge` | P1 (checkout dead) |
| `payment.charge` p95 latency > 2s | P3 (degraded UX) |
| Pod restart loop (CrashLoopBackOff) | P1 |
| Memory growth toward limit (OOMKilled imminent) | P2 |

## Common causes

1. **Bad deploy** — most recent payment service deploy contains a regression in
   `charge.js`. Check `git log src/payment/` for recent merges. The single
   most common cause; check first.
2. **Upstream payment provider timeout** — Stripe/Adyen mock service slow.
   Check trace spans for the external HTTP call duration. Usually correlates
   with elevated p95 latency before the error rate spikes.
3. **Stale credentials** — payment provider API key rotated and the secret
   wasn't updated in the cluster. Surfaces as 401/403 from the provider in
   logs, then as 500 from `payment` to its callers.
4. **Memory pressure** — long-running payment pods can leak memory if the
   request validation layer accumulates state. Symptom: gradual memory
   growth, then OOMKill. Restarting the pod is a temporary mitigation;
   the leak source needs a code fix.
5. **Connection-pool exhaustion** — under high load, the payment service
   exhausts its outbound HTTP connection pool to the provider. Symptom:
   timeouts that correlate with traffic spikes, not deploys.

## Triage steps

1. **Pull recent error spans from Tempo**:
   ```
   service.name = "payment" AND status = ERROR
   range = last 30 min
   group by attributes.error.message
   ```
   The error message often points directly to the cause (e.g., "connection
   refused", "401 Unauthorized", "operation timed out").

2. **Tail current logs**:
   ```
   {service="payment"} | json | level="error"
   ```
   Group by error message; the top line is usually the root cause.

3. **Check for recent deploys**:
   ```
   git log --oneline -10 src/payment/
   ```
   If a recent commit touches `charge.js` and the error window aligns with
   the deploy time, suspect a regression. Consider rollback while
   investigating.

4. **Check pod health**:
   ```
   kubectl top pod -l app=payment
   kubectl get pod -l app=payment -o wide
   kubectl describe pod -l app=payment | grep -A5 "Last State"
   ```
   Look for: high memory usage approaching limit, recent OOMKilled events,
   image pull errors.

5. **Check downstream dependencies**:
   - Payment provider availability (external)
   - Trace fan-out from payment.charge — are downstream calls timing out?

## Common fixes

| Diagnosis | Fix |
|---|---|
| Recent deploy regression | Revert the offending commit on `src/payment/`; CI rebuilds image; ArgoCD redeploys. Often the fastest path. |
| Logic error in `charge.js` | Patch the function directly; open PR; CI builds; deploy. |
| Stale credentials | Rotate the secret and `kubectl rollout restart deployment/payment`. Code-side: ensure the secret is mounted via projected volume so rotation is automatic. |
| Connection pool exhaustion | Increase pool size in `chart/values.yaml` `components.payment.env.PAYMENT_HTTP_POOL_SIZE`, or add backpressure / circuit breaker in `charge.js`. |
| Memory leak | Find the leak source (heap profile if possible); fix in `charge.js`; deploy. Bump pod memory limit as a temporary mitigation in `chart/values.yaml`. |

## What "good" looks like

- 5xx rate < 0.5% on `/charge` under normal load
- p95 latency < 500ms
- Memory usage stable < 60% of limit across the last 24h
- Zero CrashLoopBackOff events

## Related services

- **checkout** — calls payment.charge for every order. checkout failures often
  trace back here.
- **accounting** — receives Kafka events from successful charges. Lag here
  ≠ payment problem (look at kafka first).
