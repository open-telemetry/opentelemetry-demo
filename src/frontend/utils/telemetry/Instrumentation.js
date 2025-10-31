// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// This file previously initialized the OpenTelemetry SDK for the Node.js server-side (Next.js SSR).
// It has been removed to allow external SDK attachment at runtime via environment variables.
// 
// To enable OpenTelemetry instrumentation, attach an external SDK using one of these methods:
// 1. Use the OpenTelemetry Node.js auto-instrumentation:
//    node --require @opentelemetry/auto-instrumentations-node/register server.js
// 2. Set environment variables to configure OTLP exporters:
//    OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
//    OTEL_SERVICE_NAME=frontend
// 3. Use a vendor-specific SDK or agent
//
// The application code uses OpenTelemetry API calls which will emit signals
// only when an SDK is attached at runtime.

