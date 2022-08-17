import { context, trace, Tracer, Span, Context, SpanOptions, SpanStatusCode, Exception } from '@opentelemetry/api';

interface ITracer {
  getTracer(): Tracer;
  createSpanFromContext(name: string, ctx: Context, options?: SpanOptions | undefined): Span;
  runWithSpan<T>(parentSpan: Span, fn: () => Promise<T>): Promise<T>;
}

const BackendTracer = (): ITracer => ({
  getTracer() {
    return trace.getTracer(process.env.OTEL_SERVICE_NAME as string);
  },
  createSpanFromContext(name, ctx, options) {
    const tracer = this.getTracer();

    if (!ctx) return tracer.startSpan(name, options, context.active());

    return tracer.startSpan(name, options, ctx);
  },
  async runWithSpan(parentSpan, fn) {
    const ctx = trace.setSpan(context.active(), parentSpan);

    try {
      return await context.with(ctx, fn);
    } catch (error) {
      parentSpan.recordException(error as Exception);
      parentSpan.setStatus({ code: SpanStatusCode.ERROR });

      throw error;
    }
  },
});

export default BackendTracer();
