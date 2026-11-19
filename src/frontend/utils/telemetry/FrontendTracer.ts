// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { startBrowserSdk } from '@opentelemetry/browser-sdk';
import { FetchInstrumentation } from '@opentelemetry/browser-instrumentation/experimental/fetch';
import { SessionIdProcessor } from './SessionIdProcessor';

const {
  NEXT_PUBLIC_OTEL_SERVICE_NAME = '',
  NEXT_PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = '',
  IS_SYNTHETIC_REQUEST = '',
} = typeof window !== 'undefined' ? window.ENV : {};

const FrontendTracer = async () => {
  const sdk = startBrowserSdk({
    serviceName: NEXT_PUBLIC_OTEL_SERVICE_NAME,
    traces: {
      processors: [new SessionIdProcessor()],
      exportConfig: {
        url:
          NEXT_PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT ||
          'http://localhost:4318/v1/traces',
      },
      batchProcessorConfig: {
        scheduledDelayMillis: 500,
      },
    },
    instrumentations: [
      new FetchInstrumentation({
        propagateTraceHeaderCorsUrls: [/.*/],
        applyCustomAttributesOnSpan(span) {
          span.setAttribute('demo.synthetic_request', IS_SYNTHETIC_REQUEST);
        },
      }),
    ],
  });

  if (sdk.invalidConfig) {
    throw new Error(
      'Browser SDK failed to start due to an invalid configuration',
    );
  }
};

export default FrontendTracer;
