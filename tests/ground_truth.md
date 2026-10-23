# Ground truth

Written by `dev/faultctl`, append-only: one row per inject or reset, including dry-runs,
refusals and failures. `time` is when the operation started. Operator-only: the agent
must never read this file.

| time | action | incident | mechanism | target | variant | outcome | note |
|---|---|---|---|---|---|---|---|
| 2026-10-23T17:25:02+00:00 | inject | payment-failure | flag | paymentFailure | 50% | dry-run | plan: flag paymentFailure: 'off' -> '50%' (read all, change only this flag, write all, re-read) |
| 2026-10-23T17:25:03+00:00 | inject | payment-failure | flag | paymentFailure | 50% | verified | flag paymentFailure: 'off' -> '50%' (read all, change only this flag, write all, re-read) |
| 2026-10-23T17:25:07+00:00 | reset | payment-failure | flag | paymentFailure | off | verified | flag paymentFailure: '50%' -> 'off' (read all, change only this flag, write all, re-read) |
| 2026-10-23T17:25:07+00:00 | reset | payment-failure | flag | paymentFailure | off | verified | flag paymentFailure is already 'off'; no write needed |
| 2026-10-23T17:25:16+00:00 | inject | cache-unavailable | container | valkey-cart | - | dry-run | plan: container valkey-cart: running -> stopped (docker stop valkey-cart) |
| 2026-10-23T17:25:17+00:00 | inject | cache-unavailable | container | valkey-cart | - | verified | container valkey-cart: running -> stopped (docker stop valkey-cart) |
| 2026-10-23T17:25:19+00:00 | reset | cache-unavailable | container | valkey-cart | - | verified | container valkey-cart: exited -> running and healthy (docker start valkey-cart) |
| 2026-10-23T17:25:26+00:00 | reset | cache-unavailable | container | valkey-cart | - | verified | container valkey-cart is already running; nothing to start |
| 2026-10-23T17:25:32+00:00 | inject | emitRawPii | - | - | - | refused | unknown incident 'emitRawPii'; `list` shows the allowlist |
