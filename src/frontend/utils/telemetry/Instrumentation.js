const { CompositePropagator, W3CBaggagePropagator, W3CTraceContextPropagator } = require('@opentelemetry/core');
const { SemanticResourceAttributes } = require('@opentelemetry/semantic-conventions');
const { Resource } = require('@opentelemetry/resources');
const { BasicTracerProvider, SimpleSpanProcessor } = require('@opentelemetry/sdk-trace-base');
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-grpc');
const { getNodeAutoInstrumentations } = require('@opentelemetry/auto-instrumentations-node');
const { registerInstrumentations } = require('@opentelemetry/instrumentation');

const exporter = new OTLPTraceExporter({
  url: process.env.OTEL_EXPORTER_OTLP_ENDPOINT,
});

const provider = new BasicTracerProvider({
  resource: new Resource({
    [SemanticResourceAttributes.SERVICE_NAME]: process.env.OTEL_SERVICE_NAME,
  }),
});

provider.addSpanProcessor(new SimpleSpanProcessor(exporter));

provider.register({
  propagator: new CompositePropagator({
    propagators: [new W3CBaggagePropagator(), new W3CTraceContextPropagator()],
  }),
});

registerInstrumentations({
  instrumentations: [getNodeAutoInstrumentations()],
});
