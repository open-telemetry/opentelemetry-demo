// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { ConsoleInstrumentation } from '@opentelemetry/browser-instrumentation/experimental/console';
import { DocumentLoadInstrumentation } from '@opentelemetry/browser-instrumentation/experimental/document-load';
import { ElementTimingInstrumentation } from '@opentelemetry/browser-instrumentation/experimental/element-timing';
import { ErrorsInstrumentation } from '@opentelemetry/browser-instrumentation/experimental/errors';
import { FetchInstrumentation } from '@opentelemetry/browser-instrumentation/experimental/fetch';
import { LongAnimationFrameInstrumentation } from '@opentelemetry/browser-instrumentation/experimental/long-animation-frame';
import { NavigationInstrumentation } from '@opentelemetry/browser-instrumentation/experimental/navigation';
import { NavigationTimingInstrumentation } from '@opentelemetry/browser-instrumentation/experimental/navigation-timing';
import { ResourceTimingInstrumentation } from '@opentelemetry/browser-instrumentation/experimental/resource-timing';
import { UserActionInstrumentation } from '@opentelemetry/browser-instrumentation/experimental/user-action';
import { WebVitalsInstrumentation } from '@opentelemetry/browser-instrumentation/experimental/web-vitals';
import { XhrInstrumentation } from '@opentelemetry/browser-instrumentation/experimental/xhr';
import { startBrowserSdk } from '@opentelemetry/browser-sdk';
import { browserDetector } from '@opentelemetry/browser-sdk/browser-detector';
import {
  createDocumentLogRecordProcessor,
  createDocumentSpanProcessor,
  createLocationDocumentProvider,
} from '@opentelemetry/browser-sdk/document';
import {
  createSessionLogRecordProcessor,
  createSessionSpanProcessor,
} from '@opentelemetry/browser-sdk/session';
import { sessionManager } from './BrowserSession';
import { EnduserIdLogRecordProcessor } from './EnduserIdLogRecordProcessor';
import { EnduserIdProcessor } from './EnduserIdProcessor';

const {
  NEXT_PUBLIC_OTEL_SERVICE_NAME = '',
  NEXT_PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = '',
  NEXT_PUBLIC_OTEL_EXPORTER_OTLP_LOGS_ENDPOINT = '',
  IS_SYNTHETIC_REQUEST = '',
} = typeof window !== 'undefined' ? window.ENV : {};

const tracesUrl = NEXT_PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT || 'http://localhost:4318/v1/traces';
const logsUrl = NEXT_PUBLIC_OTEL_EXPORTER_OTLP_LOGS_ENDPOINT || 'http://localhost:4318/v1/logs';
const exportUrls = [tracesUrl, logsUrl];

const batchProcessorConfig = { scheduledDelayMillis: 500 };

const FrontendTracer = async () => {
  await sessionManager.start();

  const documentProvider = createLocationDocumentProvider();

  const sdk = startBrowserSdk({
    serviceName: NEXT_PUBLIC_OTEL_SERVICE_NAME,
    resourceAttributes: browserDetector.detect().attributes,
    traces: {
      processors: [
        createSessionSpanProcessor(sessionManager),
        createDocumentSpanProcessor(documentProvider),
        new EnduserIdProcessor(),
      ],
      exportConfig: { url: tracesUrl },
      batchProcessorConfig,
    },
    logs: {
      processors: [
        createSessionLogRecordProcessor(sessionManager),
        createDocumentLogRecordProcessor(documentProvider),
        new EnduserIdLogRecordProcessor(),
      ],
      exportConfig: { url: logsUrl },
      batchProcessorConfig,
    },
    instrumentations: [
      new ConsoleInstrumentation(),
      new ElementTimingInstrumentation(),
      new ErrorsInstrumentation(),
      new LongAnimationFrameInstrumentation(),
      new NavigationInstrumentation(),
      new NavigationTimingInstrumentation(),
      new ResourceTimingInstrumentation({ ignoreUrls: exportUrls }),
      new UserActionInstrumentation(),
      new WebVitalsInstrumentation({ includeRawAttribution: true, reportAllChanges: true }),
      new DocumentLoadInstrumentation(),
      new FetchInstrumentation({
        propagateTraceHeaderCorsUrls: [/.*/],
        ignoreUrls: exportUrls,
        applyCustomAttributesOnSpan(span) {
          span.setAttribute('demo.synthetic_request', IS_SYNTHETIC_REQUEST);
        },
      }),
      new XhrInstrumentation({
        propagateTraceHeaderCorsUrls: [/.*/],
        ignoreUrls: exportUrls,
        applyCustomAttributesOnSpan(span) {
          span.setAttribute('demo.synthetic_request', IS_SYNTHETIC_REQUEST);
        },
      }),
    ],
  });

  if (sdk.invalidConfig) {
    throw new Error('Browser SDK failed to start due to an invalid configuration');
  }
};

export default FrontendTracer;
