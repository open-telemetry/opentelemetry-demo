// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const opentelemetry = require("@opentelemetry/sdk-node")
const {getNodeAutoInstrumentations} = require("@opentelemetry/auto-instrumentations-node")
const {OTLPTraceExporter} = require('@opentelemetry/exporter-trace-otlp-grpc')
const {OTLPMetricExporter} = require('@opentelemetry/exporter-metrics-otlp-grpc')
const {PeriodicExportingMetricReader} = require('@opentelemetry/sdk-metrics')
const {alibabaCloudEcsDetector} = require('@opentelemetry/resource-detector-alibaba-cloud')
const {awsEc2Detector, awsEksDetector} = require('@opentelemetry/resource-detector-aws')
const {containerDetector} = require('@opentelemetry/resource-detector-container')
const {gcpDetector} = require('@opentelemetry/resource-detector-gcp')
const {envDetector, hostDetector, osDetector, processDetector} = require('@opentelemetry/resources')
const {RuntimeNodeInstrumentation} = require('@opentelemetry/instrumentation-runtime-node')

const sdk = new opentelemetry.NodeSDK({
  traceExporter: new OTLPTraceExporter(),
  instrumentations: [
    getNodeAutoInstrumentations({
      // only instrument fs if it is part of another trace
      '@opentelemetry/instrumentation-fs': {
        requireParentSpan: true,
      },
    }),
    new RuntimeNodeInstrumentation({
      monitoringPrecision: 5000,
    })
  ],
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

sdk.start();

// Continuous profiling: @pyroscope/nodejs pushes wall/heap profiles to the estate
// Pyroscope when PYROSCOPE_SERVER_ADDRESS is set (deploy/telemetry-env-patches.yaml).
// Wrapped so local runs without the estate stay unchanged. Profiling must never take
// the service down, so any failure here is non-fatal.
try {
  const pyroscopeServerAddress = process.env.PYROSCOPE_SERVER_ADDRESS;
  if (pyroscopeServerAddress) {
    const Pyroscope = require('@pyroscope/nodejs');
    Pyroscope.init({
      appName: process.env.OTEL_SERVICE_NAME || 'payment',
      serverAddress: pyroscopeServerAddress,
      basicAuthUser: process.env.PYROSCOPE_BASIC_AUTH_USER,
      basicAuthPassword: process.env.PYROSCOPE_BASIC_AUTH_PASSWORD,
      tags: { service_namespace: 'opentelemetry-demo' },
    });
    Pyroscope.start();
  }
} catch (e) {
  console.warn('pyroscope profiler disabled:', e?.message || e);
}
