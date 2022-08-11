import { CompositePropagator, W3CBaggagePropagator, W3CTraceContextPropagator } from '@opentelemetry/core';
import { WebTracerProvider } from '@opentelemetry/sdk-trace-web';
import { BatchSpanProcessor } from '@opentelemetry/sdk-trace-base';
import { registerInstrumentations } from '@opentelemetry/instrumentation';
import { ZoneContextManager } from '@opentelemetry/context-zone';
import { getWebAutoInstrumentations } from '@opentelemetry/auto-instrumentations-web';
import { Resource } from '@opentelemetry/resources';
import { SemanticResourceAttributes } from '@opentelemetry/semantic-conventions';
import { OTLPTraceExporter } from '@opentelemetry/exporter-trace-otlp-http';

interface ITracer {
  getTracer(): void;
}

const FrontendTracer = (): ITracer => ({
  getTracer() {
    const provider = new WebTracerProvider({
      resource: new Resource({
        [SemanticResourceAttributes.SERVICE_NAME]: process.env.NEXT_PUBLIC_OTEL_SERVICE_NAME,
      }),
    });

    provider.addSpanProcessor(
      new BatchSpanProcessor(
        new OTLPTraceExporter({
          url: process.env.NEXT_PUBLIC_OTEL_EXPORTER_OTLP_TRACES_PUBLIC_ENDPOINT,
        })
      )
    );

    provider.register({
      contextManager: new ZoneContextManager(),
      propagator: new CompositePropagator({
        propagators: [new W3CBaggagePropagator(), new W3CTraceContextPropagator()],
      }),
    });

    registerInstrumentations({
      instrumentations: [
        getWebAutoInstrumentations({
          '@opentelemetry/instrumentation-fetch': {
            propagateTraceHeaderCorsUrls: /.*/,
            clearTimingResources: true,
          },
        }),
      ],
    });
  },
});

export default FrontendTracer();
