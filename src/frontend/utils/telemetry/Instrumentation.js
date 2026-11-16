// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const opentelemetry = require('@opentelemetry/sdk-node');
const {getNodeAutoInstrumentations} = require('@opentelemetry/auto-instrumentations-node');
const {OTLPTraceExporter} = require('@opentelemetry/exporter-trace-otlp-grpc');
const {OTLPMetricExporter} = require('@opentelemetry/exporter-metrics-otlp-grpc');
const {PeriodicExportingMetricReader} = require('@opentelemetry/sdk-metrics');
const {alibabaCloudEcsDetector} = require('@opentelemetry/resource-detector-alibaba-cloud');
const {awsEc2Detector, awsEksDetector} = require('@opentelemetry/resource-detector-aws');
const {containerDetector} = require('@opentelemetry/resource-detector-container');
const {gcpDetector} = require('@opentelemetry/resource-detector-gcp');
const {envDetector, hostDetector, osDetector, processDetector} = require('@opentelemetry/resources');

const sdk = new opentelemetry.NodeSDK({
  traceExporter: new OTLPTraceExporter(),
  instrumentations: [
    getNodeAutoInstrumentations({
      // disable fs instrumentation to reduce noise
      '@opentelemetry/instrumentation-fs': {
        enabled: false,
      },
    })
  ],
  metricReader: new PeriodicExportingMetricReader({
    exporter: new OTLPMetricExporter(),
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
    gcpDetector,
  ],
});

sdk.start();

// Continuous profiling: @pyroscope/nodejs pushes wall/heap profiles for the Next.js
// server process to the estate Pyroscope when PYROSCOPE_SERVER_ADDRESS is set
// (deploy/telemetry-env-patches.yaml). The browser side is covered by Faro instead.
// Wrapped so local runs without the estate stay unchanged; failures are non-fatal.
try {
  const pyroscopeServerAddress = process.env.PYROSCOPE_SERVER_ADDRESS;
  if (pyroscopeServerAddress) {
    const Pyroscope = require('@pyroscope/nodejs');
    Pyroscope.init({
      appName: process.env.OTEL_SERVICE_NAME || 'frontend',
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
