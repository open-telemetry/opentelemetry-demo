# product-catalog runbook

The product-catalog service serves product metadata (name, description,
price, image URL) for the entire site. Every page load on the storefront
hits this service at least once.

## Primary signals

- `http_server_request_duration_seconds_count{service="product-catalog", status_code=~"5.."}` — 5xx rate
- p95 latency on `GetProduct` and `ListProducts` RPCs
- Trace span `product.GetProduct` — error rate per minute, often grouped by product ID
- `app_recommendations_counter` upstream — drops when this service is degraded

## Symptoms → severity guide

| Pattern | Severity |
|---|---|
| 5xx on a SPECIFIC product ID | P3 (one product unviewable) |
| 5xx rate site-wide > 5% | P2 (storefront degraded) |
| 5xx rate > 50% | P1 (storefront broken) |
| p95 > 2s | P3 (slow page loads) |

## Common causes

1. **Bad deploy in `src/product-catalog/`** — most common. Check `git log
   -10 src/product-catalog/`.
2. **Specific product data corruption** — a product's metadata in the
   embedded data file is malformed; service throws when serving that one
   product but is fine for everything else.
3. **Memory pressure** — under heavy listing load, the service can hold
   too many product records in memory.
4. **Slow startup** — service initializes its product index from disk on
   start; cold pods can be slow until warmed.

## Triage steps

1. **Identify whether errors are product-specific or service-wide**:
   ```
   service.name = "product-catalog" AND status = ERROR
   group by attributes.product.id
   ```
   If concentrated on one ID, that product's data is the problem. If
   spread across many IDs, the service itself.

2. **Check recent deploys**:
   ```
   git log --oneline -10 src/product-catalog/
   ```

3. **Tail logs**:
   ```
   {service="product-catalog"} | json | level="error"
   ```

4. **Check pod resources**:
   ```
   kubectl top pod -l app=product-catalog
   ```

## Common fixes

| Diagnosis | Fix |
|---|---|
| Bad deploy | Revert offending commit on `src/product-catalog/`. |
| One product breaking the service | Find and fix the malformed product entry in the embedded data file (or in the upstream product source if data is loaded externally). Patch in `src/product-catalog/`. |
| Memory pressure | Bump memory limit in `chart/values.yaml` `components.product-catalog.resources`; longer-term, fix the in-memory index strategy in code. |
| Slow startup | Add readiness probe with longer initial delay; or pre-load index more efficiently. |

## What "good" looks like

- 5xx rate < 0.1% on all product-catalog endpoints
- p95 < 200ms
- Stable memory usage well below limit
- All products in catalog return successfully when probed

## Related services

- **frontend** — calls product-catalog for every page render
- **recommendation** — calls for product metadata in recommendation list
- **checkout** — calls to validate products at checkout time
