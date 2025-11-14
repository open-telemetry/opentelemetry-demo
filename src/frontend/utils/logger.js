// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const { trace, context } = require('@opentelemetry/api');

/**
 * Splunk-optimized JSON logger
 * Outputs single-line JSON logs with trace context
 */
class SplunkLogger {
  constructor(serviceName = 'frontend') {
    this.serviceName = serviceName;
  }

  _getTraceContext() {
    const span = trace.getSpan(context.active());
    if (span) {
      const spanContext = span.spanContext();
      return {
        'trace.id': spanContext.traceId,
        'span.id': spanContext.spanId,
        'trace.flags': spanContext.traceFlags,
      };
    }
    return {};
  }

  _formatLog(level, message, additionalFields = {}) {
    const timestamp = new Date().toISOString();
    const traceContext = this._getTraceContext();

    const logEntry = {
      timestamp,
      level: level.toUpperCase(),
      'service.name': this.serviceName,
      message,
      ...traceContext,
      ...additionalFields,
    };

    // Output as single-line JSON
    console.log(JSON.stringify(logEntry));
  }

  debug(message, fields = {}) {
    this._formatLog('debug', message, fields);
  }

  info(message, fields = {}) {
    this._formatLog('info', message, fields);
  }

  warn(message, fields = {}) {
    this._formatLog('warn', message, fields);
  }

  error(message, fields = {}) {
    // If fields contains an Error object, extract its properties
    if (fields.error instanceof Error) {
      fields.error = {
        name: fields.error.name,
        message: fields.error.message,
        stack: fields.error.stack,
      };
    }
    this._formatLog('error', message, fields);
  }
}

// Create singleton instance
const logger = new SplunkLogger(process.env.OTEL_SERVICE_NAME || 'frontend');

module.exports = { logger, SplunkLogger };
