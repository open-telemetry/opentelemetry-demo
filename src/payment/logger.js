// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const pino = require('pino');
const { context, trace } = require('@opentelemetry/api');

const logger = pino({
  // Match desired base fields
  base: { name: 'paymentservice' },        // shows up as "name"
  pid: process.pid,
  hostname: require('os').hostname(),
  messageKey: 'message',                   // your examples use "message"
  timestamp: pino.stdTimeFunctions.unixTime, // Unix seconds in "time"
  // Map level -> { severity: "<level>" }
  formatters: {
    level: (label) => ({ severity: label }),
  },
  // Inject OTEL fields when a span is active
  mixin() {
    const span = trace.getSpan(context.active());
    const svc = process.env.OTEL_SERVICE_NAME || 'paymentservice';
    const base = { 'service.name': svc };
    if (span && typeof span.spanContext === 'function') {
      const sc = span.spanContext();
      if (sc) {
        // slice low 64-bits of 128-bit trace id to match your example format
        base.trace_id = (sc.traceId || '').slice(-16);
        base.span_id = sc.spanId;
      }
    }
    return base;
  },
});

module.exports = logger;
