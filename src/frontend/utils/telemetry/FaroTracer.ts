// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Faro browser telemetry (RUM): console/errors, web vitals, document-load, fetch/XHR
// and user interaction spans — sent as Faro payloads to the estate's faro-collector
// (GRAFANA_FARO_ENDPOINT, e.g. https://faro.stackgen.run), which fans out to
// ObserveNow via data-recipes-traces-relay.
//
// Only one browser tracer can own the page's global OTel provider (fetch/XHR are
// patched once). Faro owns it when enabled, exporting spans through its payloads
// with the faro receiver — so _app.tsx runs EITHER FaroTracer (endpoint configured)
// OR FrontendTracer (plain OTLP web tracing), never both.
//
// Endpoint injection: pages/_document.tsx puts GRAFANA_FARO_ENDPOINT into
// window.ENV as NEXT_GRAFANA_FARO_ENDPOINT (server-side, no client build-time env).
// The 'faroCollectorUrl' cookie mirrors the grafana/opentelemetry-demo fork's
// runtime override knob.

import { getWebInstrumentations, initializeFaro } from '@grafana/faro-web-sdk';
import { TracingInstrumentation } from '@grafana/faro-web-tracing';
import { CompositePropagator, W3CBaggagePropagator, W3CTraceContextPropagator } from '@opentelemetry/core';
import { DocumentLoadInstrumentation } from '@opentelemetry/instrumentation-document-load';
import { FetchInstrumentation } from '@opentelemetry/instrumentation-fetch';
import { XMLHttpRequestInstrumentation } from '@opentelemetry/instrumentation-xml-http-request';
import { UserInteractionInstrumentation } from '@opentelemetry/instrumentation-user-interaction';

const { NEXT_PUBLIC_OTEL_SERVICE_NAME = '', NEXT_GRAFANA_FARO_ENDPOINT = '' } =
  typeof window !== 'undefined' ? window.ENV : ({} as Record<string, string>);

const Faro = async (collectorString: string) => {
  const url = NEXT_GRAFANA_FARO_ENDPOINT || collectorString;
  if (!url) {
    return;
  }

  const faro = initializeFaro({
    url,
    app: { name: NEXT_PUBLIC_OTEL_SERVICE_NAME || 'frontend-web', version: '2.1.3' },
    instrumentations: [
      ...getWebInstrumentations(),
      new TracingInstrumentation({
        propagator: new CompositePropagator({
          propagators: [new W3CBaggagePropagator(), new W3CTraceContextPropagator()],
        }),
        instrumentations: [
          new DocumentLoadInstrumentation(),
          new FetchInstrumentation({
            clearTimingResources: true,
            applyCustomAttributesOnSpan(span) {
              span.setAttribute('app.synthetic_request', 'false');
            },
            // don't trace the Faro collector itself (feedback loop)
            ignoreUrls: [url],
          }),
          new XMLHttpRequestInstrumentation(),
          new UserInteractionInstrumentation(),
        ],
      }),
    ],
  });

  // expose for demos/debugging in the console
  (window as unknown as { faro?: typeof faro }).faro = faro;
};

export default Faro;
