// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const {NodeSDK} = require('@opentelemetry/sdk-node');
const {getNodeAutoInstrumentations} = require('@opentelemetry/auto-instrumentations-node');
const {OTLPTraceExporter} = require('@opentelemetry/exporter-trace-otlp-grpc');
const {OTLPMetricExporter} = require('@opentelemetry/exporter-metrics-otlp-grpc');
const {OTLPLogExporter} = require('@opentelemetry/exporter-logs-otlp-grpc');
const {BatchSpanProcessor} = require('@opentelemetry/sdk-trace');
const {BatchLogRecordProcessor} = require('@opentelemetry/sdk-logs');
const {PeriodicExportingMetricReader} = require('@opentelemetry/sdk-metrics');
const {alibabaCloudEcsDetector} = require('@opentelemetry/resource-detector-alibaba-cloud');
const {awsEc2Detector, awsEksDetector} = require('@opentelemetry/resource-detector-aws');
const {containerDetector} = require('@opentelemetry/resource-detector-container');
const {gcpDetector} = require('@opentelemetry/resource-detector-gcp');
const {envDetector, hostDetector, osDetector, processDetector} = require('@opentelemetry/resources');

const sdk = new NodeSDK({
  instrumentations: getNodeAutoInstrumentations(),
  spanProcessors: [
    new BatchSpanProcessor({ exporter: new OTLPTraceExporter() })
  ],
  logRecordProcessors: [
    new BatchLogRecordProcessor({ exporter: new OTLPLogExporter() })
  ],
  metricReaders: [
    new PeriodicExportingMetricReader({ exporter: new OTLPMetricExporter() }),
  ],
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
