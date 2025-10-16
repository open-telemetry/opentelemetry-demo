// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// const { start } = require('@splunk/otel');

// start({
//    serviceName: 'my-node-service',
//    endpoint: 'http://localhost:4317'
// });
// const opentelemetry = require("@opentelemetry/sdk-node")
// const {getNodeAutoInstrumentations} = require("@opentelemetry/auto-instrumentations-node")
// const {OTLPTraceExporter} = require('@opentelemetry/exporter-trace-otlp-grpc')
// const {OTLPMetricExporter} = require('@opentelemetry/exporter-metrics-otlp-grpc')
// const {PeriodicExportingMetricReader} = require('@opentelemetry/sdk-metrics')
// const {alibabaCloudEcsDetector} = require('@opentelemetry/resource-detector-alibaba-cloud')
// const {awsEc2Detector, awsEksDetector} = require('@opentelemetry/resource-detector-aws')
// const {containerDetector} = require('@opentelemetry/resource-detector-container')
// const {gcpDetector} = require('@opentelemetry/resource-detector-gcp')
// const {envDetector, hostDetector, osDetector, processDetector} = require('@opentelemetry/resources')
// const {RuntimeNodeInstrumentation} = require('@opentelemetry/instrumentation-runtime-node')

// const sdk = new opentelemetry.NodeSDK({
//   traceExporter: new OTLPTraceExporter(),
//   instrumentations: [
//     getNodeAutoInstrumentations({
//       // only instrument fs if it is part of another trace
//       '@opentelemetry/instrumentation-fs': {
//         requireParentSpan: true,
//       },
//     }),
//     new RuntimeNodeInstrumentation({
//       monitoringPrecision: 5000,
//     })
//   ],
//   metricReader: new PeriodicExportingMetricReader({
//     exporter: new OTLPMetricExporter()
//   }),
//   resourceDetectors: [
//     containerDetector,
//     envDetector,
//     hostDetector,
//     osDetector,
//     processDetector,
//     alibabaCloudEcsDetector,
//     awsEksDetector,
//     awsEc2Detector,
//     gcpDetector
//   ],
// })

// sdk.start();
const { start } = require('@splunk/otel');
// Print relevant OTEL/Splunk environment variables
console.log('=== OpenTelemetry Environment Variables ===');
[
  'OTEL_SERVICE_NAME',
  'OTEL_EXPORTER_OTLP_ENDPOINT',
  'OTEL_EXPORTER_OTLP_TRACES_ENDPOINT',
  //'OTEL_EXPORTER_OTLP_METRICS_ENDPOINT',
  'OTEL_RESOURCE_ATTRIBUTES',
  'SPLUNK_PROFILER_ENABLED',
  'SPLUNK_PROFILER_MEMORY_ENABLED',
  'SPLUNK_PROFILER_CALL_STACK_INTERVAL',
  'OTEL_PROFILER_LOGS_ENDPOINT',
  'OTEL_LOG_LEVEL'
].forEach((key) => {
  if (process.env[key]) {
    console.log(`${key}: ${process.env[key]}`);
  } else {
    console.log(`${key}: (not set)`);
  }
});

console.log('===========================================');

start();