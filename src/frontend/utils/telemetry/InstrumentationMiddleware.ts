import {NextApiHandler} from 'next';
import Tracer from './BackendTracer';
import {context, Exception, propagation, SpanKind, SpanStatusCode, trace} from '@opentelemetry/api';
import {SemanticAttributes} from '@opentelemetry/semantic-conventions';
import {Span} from '@opentelemetry/sdk-trace-base';

const InstrumentationMiddleware = (handler: NextApiHandler): NextApiHandler => {
    return async (request, response) => {
        const {headers, method, url = '', httpVersion} = request;
        const [target] = url.split('?');

        let span;
        const baggage = propagation.getBaggage(context.active());
        if (baggage?.getEntry("synthetic_request")?.value == "true") {
            // if synthetic_request baggage is set, create a new trace linked to the span in context
            // this span will look similar to the auto-instrumented HTTP span
            const syntheticSpan = trace.getSpan(context.active()) as Span;
            span = Tracer.getTracer().startSpan(`HTTP ${method}`, {
                root: true,
                kind: SpanKind.SERVER,
                links: [{context: syntheticSpan.spanContext()}],
                attributes: {
                    "app.synthetic_request": true,
                    [SemanticAttributes.HTTP_TARGET]: target,
                    [SemanticAttributes.HTTP_STATUS_CODE]: response.statusCode,
                    [SemanticAttributes.HTTP_ROUTE]: url,
                    [SemanticAttributes.HTTP_METHOD]: method,
                    [SemanticAttributes.HTTP_USER_AGENT]: headers['user-agent'] || '',
                    [SemanticAttributes.HTTP_URL]: `${headers.host}${url}`,
                    [SemanticAttributes.HTTP_FLAVOR]: httpVersion,
                }
            });

        } else {
            // continue current trace/span
            span = trace.getSpan(context.active()) as Span;
        }

        try {
            await Tracer.runWithSpan(span, async () => handler(request, response));
        } catch (error) {
            span.recordException(error as Exception);
            span.setStatus({code: SpanStatusCode.ERROR});
            throw error;
        } finally {
            span.end();
        }
    };
};

export default InstrumentationMiddleware;
