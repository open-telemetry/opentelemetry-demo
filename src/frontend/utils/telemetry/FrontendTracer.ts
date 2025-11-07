// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

// This file previously initialized the OpenTelemetry SDK for the browser-side (client).
// It has been removed to allow external SDK attachment at runtime via environment variables.
//
// To enable OpenTelemetry instrumentation in the browser, you can:
// 1. Use OpenTelemetry auto-instrumentation loaded via a <script> tag
// 2. Inject instrumentation via a browser extension or proxy
// 3. Use Real User Monitoring (RUM) solutions that support OpenTelemetry
//
// The application code uses OpenTelemetry API calls which will emit signals
// only when an SDK is attached at runtime.

const FrontendTracer = async () => {
  // SDK initialization removed - signals will only be emitted if an external SDK is attached
  console.log('OpenTelemetry SDK initialization removed. Use external instrumentation to enable telemetry.');
};

export default FrontendTracer;
