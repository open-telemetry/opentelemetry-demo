# Eval summary (offline)

| scenario | expected | got | confidence | decision | score | verdict | steps | tokens | seconds |
|---|---|---|---|---|---|---|---|---|---|
| baseline | None / no_incident | None / no_incident | 0.85 | no_action | 1.0 | correct | 6 | 24878 | 127.1 |
| scenario-06 | valkey-cart / dependency_unavailable | valkey-cart / dependency_unavailable | 0.50 | escalate | 1.0 | correct | 7 | 29948 | 177.5 |
| scenario-07 | email / container_down | None / unknown | 0.00 | escalate | 0.0 | wrong | 3 | 3682 | 32.3 |
| scenario-08 | product-catalog / resource_cpu | None / unknown | 0.00 | escalate | 0.0 | wrong | 2 | 1387 | 20.0 |
| scenario-09 | recommendation / resource_memory | None / unknown | 0.00 | escalate | 0.0 | wrong | 1 | 0 | 16.0 |

**Total 2.0 / 5**, RED: 0

## Calibration
| confidence | runs | mean score |
|---|---|---|
| 0.0-0.3 | 3 | 0.00 |
| 0.3-0.5 | 0 | - |
| 0.5-0.7 | 1 | 1.00 |
| 0.7-0.9 | 1 | 1.00 |
| 0.9-1.0 | 0 | - |
