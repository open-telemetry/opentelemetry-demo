import { NextApiHandler } from 'next';
import Tracer from './BackendTracer';
import { context, propagation, SpanKind, SpanStatusCode, Exception } from '@opentelemetry/api';
import { SemanticAttributes } from '@opentelemetry/semantic-conventions';

const InstrumentationMiddleware = (handler: NextApiHandler): NextApiHandler => {
  const wrapper: NextApiHandler = async (request, response) => {
    const { headers, method, url } = request;

    const parentContext = propagation.extract(context.active(), headers);
    const span = await Tracer.createSpanFromContext(`${method} ${url}`, parentContext, { kind: SpanKind.SERVER });

    try {
      await Tracer.runWithSpan(span, async () => handler(request, response));
    } catch (error) {
      span.recordException(error as Exception);
      span.setStatus({ code: SpanStatusCode.ERROR });

      throw error;
    } finally {
      span.setAttributes({
        [SemanticAttributes.HTTP_STATUS_CODE]: request.statusCode,
        [SemanticAttributes.HTTP_ROUTE]: url,
        [SemanticAttributes.HTTP_METHOD]: method,
        [SemanticAttributes.HTTP_USER_AGENT]: headers['user-agent'] || '',
      });

      span.end();
    }
  };

  return wrapper;
};

export default InstrumentationMiddleware;
