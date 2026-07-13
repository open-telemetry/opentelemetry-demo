# Load Generator

The load generator creates simulated traffic to the demo using
[k6](https://k6.io/).

## Modifying the Load Generator

The load test script lives at [`script.js`](./script.js). See the [k6
documentation](https://grafana.com/docs/k6/latest/) for more on writing k6
scripts.

Tracing and log correlation are provided by a custom k6 extension,
[`xk6-otel`](./xk6-otel), which exposes a `Tracer` to the script (imported as
`k6/x/otel`) for creating OTel spans and injecting `traceparent` headers into
outgoing HTTP requests.

The extension also emits Go runtime metrics (memory, GC, goroutines) via the
OTel contrib `runtime` instrumentation. These are separate from k6's own
built-in test metrics, which are exported via the `--out opentelemetry` output
configured in the [`Dockerfile`](./Dockerfile).

## Controlling traffic and concurrency via feature flags

* `loadGeneratorTraffic` - pauses all synthetic traffic (both scenarios) when
  turned off, checked every iteration with no restart required.
* `loadGeneratorVUs` - sets the number of concurrent virtual users the HTTP
  scenario runs. k6's `constant-vus` executor can't resize its VU pool at
  runtime, so [`entrypoint.sh`](./entrypoint.sh) polls flagd and restarts k6
  with the new VU count only when this flag's value actually changes.
