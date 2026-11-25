# Cart Service

This service stores user shopping carts in Valkey.

## Local Build

Run `dotnet restore` and `dotnet build`.

## Docker Build

From the root directory of this repository, run:

```sh
docker compose build cart
```

## Metric cardinality overflow

Enable `cartMetricCardinalityOverflow` in the feature flag UI to deliberately add
`Activity.Current.TraceId` as `demo.cart.trace_id` on the get-cart latency metric.
After enough distinct traces exceed the SDK limit (2,000 by default), view the
**Metric cardinality overflow** section of the **Self-Observability** dashboard.
This simulates an incorrect attempt to correlate metrics with traces; use exemplars
instead (the cart service already enables them). The flag is off by default.

Turning the flag off stops adding trace IDs, but cumulative overflow can remain
visible. Restart cart with the flag off to reset SDK state; historical overflow
remains visible in dashboard time ranges that include it.

## Valkey memory pressure

Enable `valkeyMemoryPressure` in the feature flag UI to set Valkey's `maxmemory`
just below its current memory usage, with the `noeviction` policy. The cart
service checks the flag every 5 seconds and keeps `maxmemory` below used memory
while the flag is on, so cart writes fail with
`OOM command not allowed when used memory > 'maxmemory'`. Turning the flag off
resets `maxmemory` to `0` (no limit).

In the Valkey dashboard, the **Memory** panel shows `maxmemory` dropping below
used memory. The **Cart impact and logs** row shows AddItem errors rising, the
warning Valkey logs when `maxmemory` is set below current usage (collected by the
`file_log/valkey` receiver), and the OOM errors cart receives. Because Valkey
writes its server log to `/data/valkey.log`, `docker compose logs valkey-cart`
shows no output.
