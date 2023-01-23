// This file configures the initialization of Sentry on the server.
// The config you add here will be used whenever the server handles a request.
// https://docs.sentry.io/platforms/javascript/guides/nextjs/

import * as Sentry from '@sentry/nextjs';
import '@sentry/tracing';
import { ProfilingIntegration } from '@sentry/profiling-node';

Sentry.init({
  dsn: process.env.SENTRY_DSN_SERVER,
  instrumenter: 'otel',
  // Adjust this value in production, or use tracesSampler for greater control
  tracesSampleRate: 1.0,
  profilesSampleRate: 1.0,
  includeLocalVariables: true,
  environment: process.env.SENTRY_ENVIRONMENT,
  integrations: [new ProfilingIntegration()],
  // ...
  // Note: if you want to override the automatic release value, do not set a
  // `release` value here - use the environment variable `SENTRY_RELEASE`, so
  // that it will also get attached to your source maps
});
