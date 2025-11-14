// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const { start } = require('@splunk/otel');
const { diag, DiagConsoleLogger, DiagLogLevel } = require('@opentelemetry/api');

// Log relevant environment variables at startup
console.log('OpenTelemetry Configuration:', {
  'OTEL_SERVICE_NAME': process.env.OTEL_SERVICE_NAME || 'frontend',
  'OTEL_EXPORTER_OTLP_ENDPOINT': process.env.OTEL_EXPORTER_OTLP_ENDPOINT,
  'OTEL_EXPORTER_OTLP_PROTOCOL': process.env.OTEL_EXPORTER_OTLP_PROTOCOL,
  'OTEL_RESOURCE_ATTRIBUTES': process.env.OTEL_RESOURCE_ATTRIBUTES,
  'OTEL_LOG_LEVEL': process.env.OTEL_LOG_LEVEL || 'NONE',
  'NODE_OPTIONS': process.env.NODE_OPTIONS,
});

// Enable diagnostic logging based on environment variable
// OTEL_LOG_LEVEL can be: NONE, ERROR, WARN, INFO, DEBUG, VERBOSE, ALL
const logLevel = process.env.OTEL_LOG_LEVEL || 'NONE';
if (logLevel !== 'NONE') {
  const level = DiagLogLevel[logLevel] || DiagLogLevel.INFO;
  diag.setLogger(new DiagConsoleLogger(), level);
}

start({
  serviceName: process.env.OTEL_SERVICE_NAME || 'frontend',
});

// Initialize Splunk-optimized JSON logger
const { logger } = require('./utils/logger');
logger.info('OpenTelemetry instrumentation initialized', {
  'service.name': process.env.OTEL_SERVICE_NAME || 'frontend',
  'otel.exporter.endpoint': process.env.OTEL_EXPORTER_OTLP_ENDPOINT,
  'otel.exporter.protocol': process.env.OTEL_EXPORTER_OTLP_PROTOCOL,
  'otel.resource.attributes': process.env.OTEL_RESOURCE_ATTRIBUTES,
});