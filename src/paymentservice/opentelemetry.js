// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const { NodeSDK, logs, tracing } = require('@opentelemetry/sdk-node');
const {
	getNodeAutoInstrumentations,
} = require('@opentelemetry/auto-instrumentations-node');
const {
	OTLPTraceExporter,
} = require('@opentelemetry/exporter-trace-otlp-grpc');
const {
	OTLPMetricExporter,
} = require('@opentelemetry/exporter-metrics-otlp-grpc');
const { PeriodicExportingMetricReader } = require('@opentelemetry/sdk-metrics');
const {
	alibabaCloudEcsDetector,
} = require('@opentelemetry/resource-detector-alibaba-cloud');
const {
	awsEc2Detector,
	awsEksDetector,
} = require('@opentelemetry/resource-detector-aws');
const {
	containerDetector,
} = require('@opentelemetry/resource-detector-container');
const { gcpDetector } = require('@opentelemetry/resource-detector-gcp');
const {
	envDetector,
	hostDetector,
	osDetector,
	processDetector,
} = require('@opentelemetry/resources');
const {
	BunyanInstrumentation,
} = require('@opentelemetry/instrumentation-bunyan');

const sdk = new NodeSDK({
	traceExporter: new OTLPTraceExporter(),
	spanProcessor: new tracing.SimpleSpanProcessor(
		new tracing.ConsoleSpanExporter()
	),
	logRecordProcessor: new logs.SimpleLogRecordProcessor(
		new logs.ConsoleLogRecordExporter()
	),
	instrumentations: [
		getNodeAutoInstrumentations({
			// only instrument fs if it is part of another trace
			'@opentelemetry/instrumentation-fs': {
				requireParentSpan: true,
			},
		}),
		new BunyanInstrumentation({
			// See below for Bunyan instrumentation options.
		}),
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
