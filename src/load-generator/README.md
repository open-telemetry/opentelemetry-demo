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

The extension also exposes a `Meter` for emitting OTel metrics. Every span
started via the `Tracer` automatically produces two metrics, labelled with the
span name (`span.name`):

* `loadgen.spans.started` — counter of spans started.
* `loadgen.span.duration` — histogram of span durations in milliseconds.

Scripts can emit custom metrics through the `Meter`:

```javascript
import { Meter } from 'k6/x/otel'

const meter = new Meter()
meter.addCounter('loadgen.checkouts', 1, { 'user.id': userId }) // value defaults to 1
meter.recordHistogram('loadgen.cart.items', itemCount, { currency: 'USD' })
```

Metrics from the `xk6-otel` extension are separate from k6's own built-in test
metrics, which are exported via the `--out opentelemetry` output configured in
the [`Dockerfile`](./Dockerfile).
