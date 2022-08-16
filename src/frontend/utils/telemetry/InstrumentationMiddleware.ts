import { NextApiHandler } from 'next';
import Tracer from './BackendTracer';
import { context, propagation, SpanKind, SpanStatusCode, Exception } from '@opentelemetry/api';
import { SemanticAttributes } from '@opentelemetry/semantic-conventions';

const InstrumentationMiddleware = (handler: NextApiHandler): NextApiHandler => {
  const wrapper: NextApiHandler = async (request, response) => {
    const { headers, method, url = '', httpVersion } = request;
    const [target] = url.split('?');

    const parentContext = propagation.extract(context.active(), headers);
    const span = await Tracer.createSpanFromContext(`API HTTP ${method}`, parentContext, { kind: SpanKind.SERVER });

    try {
      await Tracer.runWithSpan(span, async () => handler(request, response));
    } catch (error) {
      span.recordException(error as Exception);
      span.setStatus({ code: SpanStatusCode.ERROR });

      throw error;
    } finally {
      span.setAttributes({
        [SemanticAttributes.HTTP_TARGET]: target,
        [SemanticAttributes.HTTP_STATUS_CODE]: response.statusCode,
        [SemanticAttributes.HTTP_ROUTE]: url,
        [SemanticAttributes.HTTP_METHOD]: method,
        [SemanticAttributes.HTTP_USER_AGENT]: headers['user-agent'] || '',
        [SemanticAttributes.HTTP_URL]: `${headers.host}${url}`,
        [SemanticAttributes.HTTP_FLAVOR]: httpVersion,
      });

      span.end();
    }
  };

  return wrapper;
};

export default InstrumentationMiddleware;
