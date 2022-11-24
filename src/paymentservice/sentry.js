const Sentry = require("@sentry/node");

function initSentry() {
  // Make sure to call `Sentry.init` BEFORE initializing the OpenTelemetry SDK
  Sentry.init({
    dsn: process.env.SENTRY_DSN,
    tracesSampleRate: 1.0,
    // set the instrumenter to use OpenTelemetry instead of Sentry
    instrumenter: "otel",
    // ...
  });
}

module.exports = {
  initSentry,
};
