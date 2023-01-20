// This file configures the initialization of Sentry on the browser.
// The config you add here will be used whenever a page is visited.
// https://docs.sentry.io/platforms/javascript/guides/nextjs/

import * as Sentry from '@sentry/nextjs';

Sentry.init({
  dsn: process.env.NEXT_PUBLIC_SENTRY_DSN_CLIENT,
  environment: process.env.NEXT_PUBLIC_SENTRY_ENVIRONMENT,
  // Adjust this value in production, or use tracesSampler for greater control
  tracesSampleRate: 1.0,

  // This sets the sample rate to be 10%. You may want this to be 100% while
  // in development and sample at a lower rate in production
  replaysSessionSampleRate: 1.0,

  // If the entire session is not sampled, use the below sample rate to sample
  // sessions when an error occurs.
  replaysOnErrorSampleRate: 1.0,

  integrations: [
    new Sentry.Replay({
      // Additional SDK configuration goes in here, for example:
      maskAllText: true,
      blockAllMedia: true,
    }),
    new Sentry.BrowserTracing({
      _experiments: {
        enableInteractions: true,
      },
    }),
  ],
  // ...
  // Note: if you want to override the automatic release value, do not set a
  // `release` value here - use the environment variable `SENTRY_RELEASE`, so
  // that it will also get attached to your source maps
});

// We want to keep a consistent user id across page loads for a user, especially for replay
const userId = getLocalUserId();
if (userId) {
  Sentry.setUser({ id: userId });
}

function getLocalUserId() {
  try {
    const storedUserId = localStorage.getItem('SENTRY-userId');
    if (storedUserId) {
      return storedUserId;
    }

    const newUserId = crypto.randomUUID();
    localStorage.setItem('SENTRY-userId', newUserId);
    return newUserId;
  } catch (error) {
    // If either localStorage or crypto is not available, we simply fall back to no user handling
    return undefined;
  }
}
