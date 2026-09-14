// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import { NextApiHandler } from 'next';
import {context, Exception, Span, SpanStatusCode, trace} from '@opentelemetry/api';
import {
  ATTR_HTTP_REQUEST_METHOD,
  ATTR_HTTP_RESPONSE_STATUS_CODE,
  ATTR_URL_PATH,
  SemanticAttributes,
} from '@opentelemetry/semantic-conventions';
import logger from './logger';

const InstrumentationMiddleware = (handler: NextApiHandler): NextApiHandler => {
  return async (request, response) => {
    const span = trace.getSpan(context.active()) as Span;
    const urlPath = request.url?.split('?', 1)[0];

    let httpStatus = 200;
    try {
      await runWithSpan(span, async () => handler(request, response));
      httpStatus = response.statusCode;
      logger.info(
        {
          [ATTR_HTTP_REQUEST_METHOD]: request.method,
          [ATTR_URL_PATH]: urlPath,
          [ATTR_HTTP_RESPONSE_STATUS_CODE]: httpStatus,
        },
        'API request completed'
      );
    } catch (error) {
      span.recordException(error as Exception);
      span.setStatus({ code: SpanStatusCode.ERROR });
      httpStatus = 500;
      logger.error(
        {
          err: error,
          [ATTR_HTTP_REQUEST_METHOD]: request.method,
          [ATTR_URL_PATH]: urlPath,
          [ATTR_HTTP_RESPONSE_STATUS_CODE]: httpStatus,
        },
        'API request failed'
      );
      throw error;
    } finally {
      span.setAttribute(SemanticAttributes.HTTP_STATUS_CODE, httpStatus);
    }
  };
};

async function runWithSpan(parentSpan: Span, fn: () => Promise<unknown>) {
  const ctx = trace.setSpan(context.active(), parentSpan);
  return await context.with(ctx, fn);
}

export default InstrumentationMiddleware;
