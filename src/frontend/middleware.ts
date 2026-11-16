// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// Server-Timing traceparent: exposes the server trace context to the browser so
// document-load spans (Faro/OTel web side) can correlate with the Next.js server
// span that produced the page. Ported from grafana/opentelemetry-demo (Faro 1.8
// commit). No-op when no server span is active.
import { NextRequest, NextResponse } from 'next/server';
import { trace } from '@opentelemetry/api';

export function middleware(request: NextRequest) {
  const response = NextResponse.next();
  const current = trace.getActiveSpan();
  if (current) {
    const { traceId, spanId, traceFlags } = current.spanContext();
    response.headers.set('server-timing', `traceparent;desc="00-${traceId}-${spanId}-${traceFlags.toString(16).padStart(2, '0')}"`);
  }
  return response;
}
