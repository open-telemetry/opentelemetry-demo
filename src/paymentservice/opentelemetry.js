// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const { NodeSDK, tracing } = require("@opentelemetry/sdk-node");

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
} = require("@opentelemetry/resources");

const sdk = new NodeSDK({
	traceExporter: new OTLPTraceExporter(),
	spanProcessor: new tracing.SimpleSpanProcessor(
		new tracing.ConsoleSpanExporter()
	),
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
