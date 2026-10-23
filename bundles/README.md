# Incident Bundles

Offline telemetry snapshots captured during live fault injections.
Each bundle is a frozen point-in-time snapshot of Prometheus metrics,
Jaeger traces, and OpenSearch logs taken while a fault was active.

## Structure

```
bundles/
├── incident_01_payment_failure/
│   ├── metrics.json    ← Prometheus API responses (all key queries)
│   ├── traces.json     ← Jaeger traces for all services
│   ├── logs.json       ← OpenSearch ERROR/WARN logs
│   └── metadata.json   ← Ground truth: fault name, correct diagnosis, correct fix
│
├── incident_02_cart_failure/
│   └── ...
```

## How to Capture a Bundle

1. Start the full demo stack:
   ```
   docker compose -f compose.yaml -f compose.full.yaml -f compose.observability.yaml up --no-build -d
   ```

2. Inject a fault:
   ```
   python scripts/faultctl.py inject paymentFailure --variant "100%"
   ```

3. Wait 2-3 minutes for metrics to build up.

4. Capture the bundle:
   ```
   python scripts/capture_bundle.py --name incident_01_payment_failure
   ```

5. Edit `bundles/incident_01_payment_failure/metadata.json` — fill in:
   - `affected_service`
   - `correct_diagnosis`
   - `correct_fix`

6. Reset the fault:
   ```
   python scripts/faultctl.py reset
   ```

## Known Faults to Capture

| Bundle Name                          | Flag                      | Variant  |
|--------------------------------------|---------------------------|----------|
| incident_01_payment_failure          | paymentFailure            | 100%     |
| incident_02_cart_failure             | cartFailure               | 100%     |
| incident_03_recommendation_cache     | recommendationCacheFailure| on       |
| incident_04_ad_high_cpu              | adHighCpu                 | on       |
| incident_05_ad_failure               | adFailure                 | on       |
| incident_06_email_memory_leak        | emailMemoryLeak           | 1000x    |
| incident_07_kafka_queue_problems     | kafkaQueueProblems        | 3sec     |
| incident_08_kafka_consumer_dead      | kafkaConsumerDead         | on       |
| incident_09_product_catalog_failure  | productCatalogFailure     | on       |
| incident_10_traffic_flood            | loadGeneratorFloodHomepage| on       |

## Note on Bundle Size

`metrics.json` and `traces.json` can be large (several MB each).
They are committed to git for offline agent testing.
Run `git lfs track "bundles/**/*.json"` if files exceed 50MB.
