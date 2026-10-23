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
| 2026-10-23T17:37:08+00:00 | inject | cache-unavailable | container | valkey-cart | - | verified | container valkey-cart: running -> stopped (docker stop valkey-cart) |
| 2026-10-23T17:39:57+00:00 | reset | cache-unavailable | container | valkey-cart | - | verified | container valkey-cart: exited -> running and healthy (docker start valkey-cart) |
| 2026-10-23T17:42:05+00:00 | inject | payment-failure | flag | paymentFailure | 100% | verified | flag paymentFailure: 'off' -> '100%' (read all, change only this flag, write all, re-read) |
| 2026-10-23T17:43:50+00:00 | reset | payment-failure | flag | paymentFailure | off | verified | flag paymentFailure: '100%' -> 'off' (read all, change only this flag, write all, re-read) |
| 2026-10-23T17:56:34+00:00 | inject | payment-failure | flag | paymentFailure | 100% | verified | flag paymentFailure: 'off' -> '100%' (read all, change only this flag, write all, re-read) |
| 2026-10-23T18:02:48+00:00 | reset | payment-failure | flag | paymentFailure | off | verified | flag paymentFailure: '100%' -> 'off' (read all, change only this flag, write all, re-read) |
| 2026-10-23T18:02:51+00:00 | inject | cache-unavailable | container | valkey-cart | - | verified | container valkey-cart: running -> stopped (docker stop valkey-cart) |
| 2026-10-23T18:05:49+00:00 | reset | cache-unavailable | container | valkey-cart | - | verified | container valkey-cart: exited -> running and healthy (docker start valkey-cart) |
| 2026-10-23T18:27:40+00:00 | inject | payment-failure | flag | paymentFailure | 100% | verified | flag paymentFailure: 'off' -> '100%' (read all, change only this flag, write all, re-read) |
| 2026-10-23T18:29:52+00:00 | reset | payment-failure | flag | paymentFailure | off | verified | flag paymentFailure: '100%' -> 'off' (read all, change only this flag, write all, re-read) |
| 2026-10-23T18:29:52+00:00 | inject | cache-unavailable | container | valkey-cart | - | verified | container valkey-cart: running -> stopped (docker stop valkey-cart) |
| 2026-10-23T18:31:57+00:00 | reset | cache-unavailable | container | valkey-cart | - | verified | container valkey-cart: exited -> running and healthy (docker start valkey-cart) |
| 2026-10-23T18:36:55+00:00 | reset | cache-unavailable | container | valkey-cart | - | verified | container valkey-cart is already running; nothing to start |
| 2026-10-23T18:36:56+00:00 | reset | database-unavailable | container | astronomy-db | - | verified | container astronomy-db is already running; nothing to start |
| 2026-10-23T18:36:56+00:00 | reset | currency-down | container | currency | - | verified | container currency is already running; nothing to start |
| 2026-10-23T18:36:56+00:00 | reset | payment-failure | flag | paymentFailure | off | verified | flag paymentFailure is already 'off'; no write needed |
| 2026-10-23T18:36:56+00:00 | reset | cart-failure | flag | cartFailure | off | verified | flag cartFailure is already 'off'; no write needed |
| 2026-10-23T18:36:56+00:00 | reset | ad-failure | flag | adFailure | off | verified | flag adFailure is already 'off'; no write needed |
| 2026-10-23T18:36:56+00:00 | reset | product-catalog-failure | flag | productCatalogFailure | off | verified | flag productCatalogFailure is already 'off'; no write needed |
| 2026-10-23T18:36:56+00:00 | reset | product-catalog-lock-contention | flag | productCatalogLockContention | off | verified | flag productCatalogLockContention is already 'off'; no write needed |
| 2026-10-23T18:36:56+00:00 | reset | ad-high-cpu | flag | adHighCpu | off | verified | flag adHighCpu is already 'off'; no write needed |
| 2026-10-23T18:45:33+00:00 | inject | cache-unavailable | container | valkey-cart | - | verified | container valkey-cart: running -> stopped (docker stop valkey-cart) |
| 2026-10-23T18:47:38+00:00 | reset | cache-unavailable | container | valkey-cart | - | verified | container valkey-cart: exited -> running and healthy (docker start valkey-cart) |
| 2026-10-23T18:56:40+00:00 | inject | payment-failure | flag | paymentFailure | 100% | verified | flag paymentFailure: 'off' -> '100%' (read all, change only this flag, write all, re-read) |
| 2026-10-23T18:58:40+00:00 | reset | payment-failure | flag | paymentFailure | off | verified | flag paymentFailure: '100%' -> 'off' (read all, change only this flag, write all, re-read) |
| 2026-10-23T19:06:45+00:00 | reset | cache-unavailable | container | valkey-cart | - | verified | container valkey-cart is already running; nothing to start |
| 2026-10-23T19:06:45+00:00 | reset | database-unavailable | container | astronomy-db | - | verified | container astronomy-db is already running; nothing to start |
| 2026-10-23T19:06:45+00:00 | reset | currency-down | container | currency | - | verified | container currency is already running; nothing to start |
| 2026-10-23T19:06:45+00:00 | reset | payment-failure | flag | paymentFailure | off | verified | flag paymentFailure is already 'off'; no write needed |
| 2026-10-23T19:06:45+00:00 | reset | cart-failure | flag | cartFailure | off | verified | flag cartFailure is already 'off'; no write needed |
| 2026-10-23T19:06:45+00:00 | reset | ad-failure | flag | adFailure | off | verified | flag adFailure is already 'off'; no write needed |
| 2026-10-23T19:06:45+00:00 | reset | product-catalog-failure | flag | productCatalogFailure | off | verified | flag productCatalogFailure is already 'off'; no write needed |
| 2026-10-23T19:06:45+00:00 | reset | product-catalog-lock-contention | flag | productCatalogLockContention | off | verified | flag productCatalogLockContention is already 'off'; no write needed |
| 2026-10-23T19:06:45+00:00 | reset | ad-high-cpu | flag | adHighCpu | off | verified | flag adHighCpu is already 'off'; no write needed |
| 2026-10-23T19:15:32+00:00 | inject | cache-unavailable | container | valkey-cart | - | verified | container valkey-cart: running -> stopped (docker stop valkey-cart) |
| 2026-10-23T19:17:38+00:00 | reset | cache-unavailable | container | valkey-cart | - | verified | container valkey-cart: exited -> running and healthy (docker start valkey-cart) |
| 2026-10-23T19:23:53+00:00 | reset | cache-unavailable | container | valkey-cart | - | verified | container valkey-cart is already running; nothing to start |
| 2026-10-23T19:23:53+00:00 | reset | database-unavailable | container | astronomy-db | - | verified | container astronomy-db is already running; nothing to start |
| 2026-10-23T19:23:53+00:00 | reset | currency-down | container | currency | - | verified | container currency is already running; nothing to start |
| 2026-10-23T19:23:53+00:00 | reset | payment-failure | flag | paymentFailure | off | verified | flag paymentFailure is already 'off'; no write needed |
| 2026-10-23T19:23:53+00:00 | reset | cart-failure | flag | cartFailure | off | verified | flag cartFailure is already 'off'; no write needed |
| 2026-10-23T19:23:53+00:00 | reset | ad-failure | flag | adFailure | off | verified | flag adFailure is already 'off'; no write needed |
| 2026-10-23T19:23:53+00:00 | reset | product-catalog-failure | flag | productCatalogFailure | off | verified | flag productCatalogFailure is already 'off'; no write needed |
| 2026-10-23T19:23:53+00:00 | reset | product-catalog-lock-contention | flag | productCatalogLockContention | off | verified | flag productCatalogLockContention is already 'off'; no write needed |
| 2026-10-23T19:23:53+00:00 | reset | ad-high-cpu | flag | adHighCpu | off | verified | flag adHighCpu is already 'off'; no write needed |
| 2026-10-23T19:32:29+00:00 | inject | cache-unavailable | container | valkey-cart | - | verified | container valkey-cart: running -> stopped (docker stop valkey-cart) |
| 2026-10-23T19:34:42+00:00 | reset | cache-unavailable | container | valkey-cart | - | verified | container valkey-cart: exited -> running and healthy (docker start valkey-cart) |
