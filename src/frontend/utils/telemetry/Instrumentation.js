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
const {ConsoleSpanExporter, BatchSpanProcessor} = require('@opentelemetry/sdk-trace-node');
const {Span} = require('@opentelemetry/api');

class SpanNameProcessor {
      /**
       * Forces to export all finished spans
       */
      forceFlush() {}

      /**
       * Called when a {@link Span} is started, if the `span.isRecording()`
       * returns true.
       * @param span the Span that just started.
       */
      onStart(span, parentContext) {
        // bail if no nextjs context
        if (!span.attributes['next.span_type'] || !span.attributes['next.span_name']) {
            return;
        }

        const oldSpanName = span.name;

        // if span name contains query parameters, strip them
        const spanName = span.name.split("?")[0];

        // 'next.span_name': 'GET /_next/static/webpack/c0ba321a6e649482.webpack.hot-update.json',
        // 'next.span_type': 'BaseServer.handleRequest',
        // 'http.method': 'GET',
        // 'http.target': '/_next/static/webpack/c0ba321a6e649482.webpack.hot-update.json',
        if (span.attributes['http.target'] && span.attributes['http.target'].includes('/_next/static')) {
            spanName = `${span.attributes['http.method']} ${span.attributes['/_next/static']}`;
        }

        if (span.attributes['http.target'] && span.attributes['http.target'].includes('/_next/images')) {
            spanName = `${span.attributes['http.method']} ${span.attributes['/_next/images']}`;
        }

        if (span.attributes['http.target'] && span.attributes['http.target'].includes('/_next/data')) {
            spanName = `${span.attributes['http.method']} ${span.attributes['/_next/data']}`;
        }

        span.setAttribute('next.span_name', spanName);

        span.updateName(spanName);

        console.debug(`Span name ${oldSpanName} updated to ${spanName}`);
      }

      /**
       * Called when a {@link ReadableSpan} is ended, if the `span.isRecording()`
       * returns true.
       * @param span the Span that just ended.
       */
      onEnd(span) {}

      /**
       * Shuts down the processor. Called when SDK is shut down. This is an
       * opportunity for processor to do any cleanup required.
       */
      shutdown() {}
}

const traceExporter = process.env.OTEL_TRACES_EXPORTER === 'otlp' ? new OTLPTraceExporter() : new ConsoleSpanExporter();

const sdk = new opentelemetry.NodeSDK({
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
  spanProcessors: [
    new SpanNameProcessor(),
    new BatchSpanProcessor(traceExporter, {
      maxQueueSize: 4096, // default 2048
      maxExportBatchSize: 1024, // default 512
    }),
  ]
});

sdk.start();
