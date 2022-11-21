const opentelemetry = require("@opentelemetry/sdk-node")
const { getNodeAutoInstrumentations } = require("@opentelemetry/auto-instrumentations-node")
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-grpc')
const { OTLPMetricExporter } = require('@opentelemetry/exporter-metrics-otlp-grpc')
const { PeriodicExportingMetricReader } = require('@opentelemetry/sdk-metrics');

const sdk = new opentelemetry.NodeSDK({
  traceExporter: new OTLPTraceExporter(),
  instrumentations: [ getNodeAutoInstrumentations() ],
  metricReader: new PeriodicExportingMetricReader({
    exporter: new OTLPMetricExporter()
  }),
})

sdk.start().then(() => require("./index"));
