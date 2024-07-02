// Copyright Honeycomb.io
// SPDX-License-Identifier: Apache-2.0

import { getWebAutoInstrumentations } from '@opentelemetry/auto-instrumentations-web';
import { HoneycombWebSDK, WebVitalsInstrumentation } from '@honeycombio/opentelemetry-web';
// ^ on github we use this, in the docs we omit WebVitals and do it piecemeal. IMO this should be explained if they're going to stay different.
import {SessionIdProcessor} from "./SessionIdProcessor";


const { NEXT_PUBLIC_OTEL_SERVICE_NAME = '', NEXT_PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = '', IS_SYNTHETIC_REQUEST = '' } =
  typeof window !== 'undefined' ? window.ENV : {};

const FrontendTracer = async () => {
  const sdk = new HoneycombWebSDK({
    skipOptionsValidation: true, // because we are not including apiKey
                                 // but WHY aren't we? It's because we're not direct sending to api, we're using the collector
    serviceName: NEXT_PUBLIC_OTEL_SERVICE_NAME,
    spanProcessor: new SessionIdProcessor(),
    endpoint: NEXT_PUBLIC_OTEL_EXPORTER_OTLP_TRACES_ENDPOINT || 'http://localhost:4318/v1/traces',
    instrumentations: [getWebAutoInstrumentations({
      '@opentelemetry/instrumentation-fetch': {
        propagateTraceHeaderCorsUrls: /.*/,
        clearTimingResources: true,
        applyCustomAttributesOnSpan(span) {
          span.setAttribute('app.synthetic_request', IS_SYNTHETIC_REQUEST);
        },
      },
    }), new WebVitalsInstrumentation()], // add automatic instrumentation
                                         // ^ update docs to explain what this means, it's supposed to mean that more instrumentation (like webvitals) should be added there, but it isn't clear imo.
  });
  sdk.start();
};

export default FrontendTracer;
