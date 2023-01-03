# Payment Service

This service is responsible to process credit card payments for orders. It will
return an error if the credit card is invalid or the payment can not be
processed.

[Payment service source](../../src/paymentservice/)

## Initializing OpenTelemetry

It is recommended to `require` Node.js app using an initializer file that
initializes the SDK and auto-instrumentation. When initializing the
OpenTelemetry NodeJS SDK in that module, you optionally specify which
auto-instrumentation libraries to leverage, or make use of the
`getNodeAutoInstrumentations()` function which includes most popular frameworks.
The below example of an intiailizer file (`opentelemetry.js`) contains all code
required to initialize the SDK and auto-instrumentation based on standard
OpenTelemetry environment variables for OTLP export, resource attributes, and
service name. It then `require`s your app at `./index.js` to start it up once
the SDK is initialized.

```javascript
const opentelemetry = require("@opentelemetry/sdk-node")
const { getNodeAutoInstrumentations } = require("@opentelemetry/auto-instrumentations-node")
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-grpc')
const { OTLPMetricExporter } = require('@opentelemetry/exporter-metrics-otlp-grpc')
const { PeriodicExportingMetricReader } = require('@opentelemetry/sdk-metrics')
const { alibabaCloudEcsDetector } = require('@opentelemetry/resource-detector-alibaba-cloud')
const { awsEc2Detector, awsEksDetector } = require('@opentelemetry/resource-detector-aws')
const { containerDetector } = require('@opentelemetry/resource-detector-container')
const { gcpDetector } = require('@opentelemetry/resource-detector-gcp')
const { envDetector, hostDetector, osDetector, processDetector } = require('@opentelemetry/resources')

const sdk = new opentelemetry.NodeSDK({
  traceExporter: new OTLPTraceExporter(),
  instrumentations: [ getNodeAutoInstrumentations() ],
  metricReader: new PeriodicExportingMetricReader({
    exporter: new OTLPMetricExporter()
  }),
  resourceDetectors: [
    containerDetector,
    envDetector,
    hostDetector,
    osDetector,
    processDetector,
    alibabaCloudEcsDetector,
    awsEksDetector,
    awsEc2Detector,
    gcpDetector
  ],
})

sdk.start().then(() => require("./index"));
```

You can then use `opentelemetry.js` to start your app.
This can be done in the `ENTRYPOINT` command for the service's `Dockerfile`.

```dockerfile
ENTRYPOINT [ "node", "./opentelemetry.js" ]
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

### Creating Meters and Instruments

Meters can be created using the `@opentelemetry/api-metrics` package. You can
create meters as seen below, and then use the created meter to create
instruments.

```javascript
const { metrics } = require('@opentelemetry/api-metrics');

const meter = metrics.getMeter('paymentservice');
const transactionsCounter = meter.createCounter('app.payment.transactions')
```

Meters and Instruments are supposed to stick around. This means you should
get a Meter or an Instrument once , and then re-use it as needed, if possible.

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
