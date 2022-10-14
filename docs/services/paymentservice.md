# Payment Service

This service is responsible to process credit card payments for orders. It will
return an error if the credit card is invalid or the payment can not be
processed.

[Payment service source](../../src/paymentservice/)

## SDK initialization

It is recommended to use a Node required module when starting your NodeJS
application to initialize the SDK and auto-instrumentation. When initializing
the OpenTelemetry NodeJS SDK, you optionally specify which auto-instrumentation
libraries to leverage, or make use of the `getNodeAutoInstrumentations()`
function which includes most popular frameworks. The `tracing.js` contains all
code required to initialize the SDK and auto-instrumentation based on standard
OpenTelemetry environment variables for OTLP export, resource attributes, and
service name.

```javascript
const opentelemetry = require("@opentelemetry/sdk-node")
const { getNodeAutoInstrumentations } = require("@opentelemetry/auto-instrumentations-node")
const { OTLPTraceExporter } =  require('@opentelemetry/exporter-trace-otlp-grpc')

const sdk = new opentelemetry.NodeSDK({
  traceExporter: new OTLPTraceExporter(),
  instrumentations: [ getNodeAutoInstrumentations() ]
})

sdk.start()
```

Node required modules are loaded using the `--require` command line argument.
This can be done in the `ENTRYPOINT` command for the service's `Dockerfile`.

```dockerfile
ENTRYPOINT [ "node", "--require", "./tracing.js", "./index.js" ]
```

## Traces

### Add attributes to auto-instrumented spans

Within the execution of auto-instrumented code you can get current span from
context.

```javascript
  const span = opentelemetry.trace.getActiveSpan();
```

Adding attributes to a span is accomplished using `setAttributes` on the span
object. In the `chargeServiceHandler` function an attributes is added to
the span as an anonymous object (map) for the attribute key/values pair.

```javascript
    span.setAttributes({
      'app.payment.amount': parseFloat(`${amount.units}.${amount.nanos}`)
    })
```

### Span Exceptions and status

You can use the span object's `recordException` function to create a span event
with the full stack trace of a handled error. When recording an exception also
be sure to set the span's status accordingly. You can see this in the
`chargeServiceHandler` function

```javascript
    span.recordException(err)
    span.setStatus({ code: opentelemetry.SpanStatusCode.ERROR })
```

## Metrics

TBD

## Logs

TBD

## Baggage

OpenTelemetry Baggage is leveraged in this service to check if the request is
synthetic (from the load generator). Synthetic requests will not be charged,
which is indicated with a span attribute. The `charge.js` file which does the
actual payment processing, has logic to check the baggage.

```javascript
  // check baggage for synthetic_request=true, and add charged attribute accordingly
  const baggage = propagation.getBaggage(context.active());
  if (baggage && baggage.getEntry("synthetic_request") && baggage.getEntry("synthetic_request").value == "true") {
    span.setAttribute('app.payment.charged', false);
  } else {
    span.setAttribute('app.payment.charged', true);
  }
```
