// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const pino = require('pino')
const { trace, context } = require('@opentelemetry/api')

const transport = pino.transport({
  target: 'pino-opentelemetry-transport',
  options: {
    logRecordProcessorOptions: [
      {
        recordProcessorType: 'batch',
        exporterOptions: {
          protocol: 'grpc',
        }
      },
      {
        recordProcessorType: 'simple',
        exporterOptions: { protocol: 'console' }
      }
    ],
    loggerName: 'payment-logger',
    serviceVersion: '1.0.0'
  }
})

const logger = pino(transport, {
  mixin() {
    const activeSpan = trace.getActiveSpan();
    const spanContext = activeSpan?.spanContext();
    
    return {
      'service.name': process.env['OTEL_SERVICE_NAME'],
      'traceId': spanContext?.traceId || 'unknown',
      'spanId': spanContext?.spanId || 'unknown',
      'timestamp': new Date().toISOString()
    }
  },
  formatters: {
    level: (label) => {
      return { 'level': label };
    },
  },
});

module.exports = logger;
