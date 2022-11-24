import { TracingInstrumentation } from '@grafana/faro-web-tracing';
import { getWebInstrumentations, initializeFaro } from '@grafana/faro-web-sdk';
import { CompositePropagator, W3CBaggagePropagator, W3CTraceContextPropagator } from '@opentelemetry/core';
import { DocumentLoadInstrumentation } from '@opentelemetry/instrumentation-document-load';
import { FetchInstrumentation } from '@opentelemetry/instrumentation-fetch';
import { UserInteractionInstrumentation } from '@opentelemetry/instrumentation-user-interaction';
import { XMLHttpRequestInstrumentation } from '@opentelemetry/instrumentation-xml-http-request';
import { PerformanceTimelineInstrumentation } from '@grafana/faro-instrumentation-performance-timeline';

const { NEXT_PUBLIC_OTEL_SERVICE_NAME = '', NEXT_GRAFANA_FARO_ENDPOINT = '' } =
  typeof window !== 'undefined' ? window.ENV : {};

const Faro = async (collectorString: string) => {
  const url = NEXT_GRAFANA_FARO_ENDPOINT || collectorString;

  if (url) {
    initializeFaro({
      url: NEXT_GRAFANA_FARO_ENDPOINT || collectorString,

      // Mandatory, the identification label(s) of your application
      app: {
        name: NEXT_PUBLIC_OTEL_SERVICE_NAME,
        version: '1.0.0', // Optional, but recommended
      },

      instrumentations: [
        // Mandatory, overwriting the instrumentations array would cause the default instrumentations to be omitted
        ...getWebInstrumentations(),

        new PerformanceTimelineInstrumentation(),

        // Mandatory, initialization of the tracing package
        new TracingInstrumentation({
          // Overwrite default instrumentations
          instrumentations: [
            new DocumentLoadInstrumentation(),
            new FetchInstrumentation({
              clearTimingResources: true,
              applyCustomAttributesOnSpan(span) {
                span.setAttribute('app.synthetic_request', 'false');
              },
              ignoreUrls: [NEXT_GRAFANA_FARO_ENDPOINT],
            }),
            new XMLHttpRequestInstrumentation(),
            new UserInteractionInstrumentation(),
          ],
          propagator: new CompositePropagator({
            propagators: [new W3CBaggagePropagator(), new W3CTraceContextPropagator()],
          }),
        }),
      ],
    });
  }
};

export default Faro;
