/**
 * Payment Service Version A Configuration
 * Stable/Production version - Normal operation
 */

module.exports = {
  name: 'payment',
  version: 'vA',
  displayVersion: '1.7.0-a',

  // API Configuration
  defaultTokenPrefix: 'prod',
  defaultToken: 'prod-a8cf28f9-1a1a-4994-bafa-cd4b143c3291',
  versionString: 'v350.9',  // Buttercup Payments API version (success)

  // Version behavior
  alwaysFail: false,  // Version A: Normal operation (succeeds)

  // Retry Configuration (not used in normal success case)
  retryMaxDefault: 4,
  retryBaseDelayMs: 100,
  retryStrategy: 'exponential',

  // Timing Configuration
  successDelayRange: [0, 200],    // 0-200ms for successful payments
  failureDelayRange: [0, 1000],   // Not used (version A succeeds)
  totalFailureTargetMs: 5000,     // Not used (version A succeeds)

  // Timeouts
  requestTimeoutMs: 5000,

  // Feature Flags
  useRetryMaxFlag: false,  // Version A doesn't use retry flag
  usePaymentFailureFlag: false,  // Routing handled by checkout

  // Logging
  logLevel: process.env.LOG_LEVEL || 'info',

  // OTEL Resource Attributes
  resourceAttributes: {
    // Buttercup demo version — APM Troubleshooting groups errors by this.
    // Must not be a shop tag like 2.0.9 (stitch would also clobber digits).
    'service.version': 'v350.9',
    'payment.variant': 'A',
    'payment.api.version': 'v1',
    'deployment.stability': 'stable',
  },

  // Version-specific features
  features: {
    enhancedLogging: false,
    metricsV2: false,
    circuitBreaker: false,
  },
};
