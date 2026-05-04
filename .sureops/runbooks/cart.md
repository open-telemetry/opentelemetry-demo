# cart runbook

The cart service stores customer cart contents (product IDs + quantities)
in valkey-cart (Redis-compatible). Called by the frontend on every cart
mutation and by checkout when an order is placed. Failures here block
adding items to the cart and block checkout.

## Primary signals

- `http_server_request_duration_seconds_count{service="cart", status_code=~"5.."}` — 5xx rate
- Trace span `cart.add`, `cart.get`, `cart.empty` status
- `valkey_commands_processed_total` (from valkey-cart) — confirms whether the backend is reachable

## Symptoms → severity guide

| Pattern | Severity |
|---|---|
| 5xx rate on `/cart/add` > 5% | P2 (purchase blocked) |
| 5xx rate > 50% | P1 (cart broken) |
| valkey-cart unreachable | P1 (entire cart subsystem dead) |
| Slow `cart.get` p95 > 500ms | P3 (degraded UX) |

## Common causes

1. **valkey-cart down or unreachable** — backing store crashed or network policy
   misconfigured. cart returns 5xx on every operation.
2. **Bad deploy in `src/cart/`** — regression in cart service code,
   typically in the request validation or Redis client wrapper.
3. **valkey-cart memory pressure** — store hits its memory limit; writes
   start failing with OOM errors from Redis.
4. **Connection-pool exhaustion** — under high load, cart exhausts its
   pool of valkey-cart connections.

## Triage steps

1. **Check valkey-cart pod first**:
   ```
   kubectl get pod -l app=valkey-cart
   kubectl logs -l app=valkey-cart --tail=50
   ```
2. **Check cart service logs**:
   ```
   {service="cart"} | json | level=~"error|warn"
   ```
3. **Check trace fan-out**:
   ```
   service.name = "cart" AND status = ERROR
   group by attributes.error.type
   ```
4. **Check valkey-cart memory** if cart errors mention OOM:
   ```
   kubectl exec -it deploy/valkey-cart -- redis-cli INFO memory
   ```

## Common fixes

| Diagnosis | Fix |
|---|---|
| Bad cart deploy | Revert offending commit on `src/cart/`; CI rebuild; ArgoCD redeploy. |
| valkey-cart down | `kubectl rollout restart deployment/valkey-cart`. If recurring, investigate root cause (memory limit, persistent volume issues). |
| Connection pool exhausted | Bump `components.cart.env.REDIS_POOL_SIZE` in `chart/values.yaml`. |
| Code-side error handling | Patch `src/cart/` to handle Redis errors gracefully (return cached/empty state, surface clear error to frontend). |

## What "good" looks like

- 5xx rate < 0.1% on all cart endpoints
- p95 latency < 100ms
- valkey-cart memory stable, well below limit
- No CrashLoopBackOff on either pod

## Related services

- **valkey-cart** — backing store. cart's health depends entirely on this.
- **checkout** — reads cart contents at order time.
- **frontend** — primary consumer of cart APIs.
