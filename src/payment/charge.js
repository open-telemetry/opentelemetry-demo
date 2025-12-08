// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
const { context, propagation, trace, metrics, SpanKind, SpanStatusCode } = require('@opentelemetry/api');
const cardValidator = require('simple-card-validator');
const { v4: uuidv4 } = require('uuid');

const { OpenFeature } = require('@openfeature/server-sdk');
const { FlagdProvider } = require('@openfeature/flagd-provider');
const flagProvider = new FlagdProvider();

const logger = require('./logger');
const tracer = trace.getTracer('payment');
const meter = metrics.getMeter('payment');
const transactionsCounter = meter.createCounter('app.payment.transactions');

const LOYALTY_LEVEL = ['platinum', 'gold', 'silver', 'bronze'];

// External service simulation (aligned with original semantics)
const SUCCESS_VERSION = 'v350.9';
const FAILURE_VERSION = 'v350.10';
const API_TOKEN_SUCCESS_TOKEN = 'prod-a8cf28f9-1a1a-4994-bafa-cd4b143c3291';
const API_TOKEN_FAILURE_TOKEN = 'test-20e26e90-356b-432e-a2c6-956fc03f5609';
const SUCCESS_PAYMENT_SERVICE_DURATION_MILLIS = 200;  // fast success
const ERROR_PAYMENT_SERVICE_DURATION_MILLIS = 1000;   // slower error

function random(arr) {
  const index = Math.floor(Math.random() * arr.length);
  return arr[index];
}

function randomInt(from, to) {
  return Math.floor((to - from) * Math.random() + from);
}

// Error types compatible with original behavior
class InvalidRequestError extends Error {
  constructor() {
    super('Invalid request');
    this.code = 401; // Authorization error
  }
}

class CreditCardError extends Error {
  constructor(message) {
    super(message);
    this.code = 400; // Invalid argument error
  }
}

class InvalidCreditCard extends CreditCardError {
  constructor() {
    super('Credit card info is invalid.');
  }
}

class UnacceptedCreditCard extends CreditCardError {
  constructor(cardType) {
    super(`Sorry, we cannot process ${cardType} credit cards. Only VISA or MasterCard is accepted.`);
  }
}

class ExpiredCreditCard extends CreditCardError {
  constructor(number, month, year) {
    super(`The credit card (ending ${number.substr(-4)}) expired on ${month}/${year}.`);
  }
}

// Simulated external payment processor (accepts both new and original request shapes)
function buttercupPaymentsApiCharge(request, token) {
  return new Promise((resolve, reject) => {
    if (token === API_TOKEN_FAILURE_TOKEN) {
      const timeoutMillis = randomInt(0, ERROR_PAYMENT_SERVICE_DURATION_MILLIS);
      setTimeout(() => reject(new InvalidRequestError()), timeoutMillis);
      return;
    }

    // Normalize request shape
    const amount = request.amount || request.Amount || {};
    const creditCard = request.creditCard || request.credit_card || {};
    const cardNumber = creditCard.creditCardNumber || creditCard.number || creditCard.credit_card_number;
    const year = creditCard.creditCardExpirationYear || creditCard.year || creditCard.credit_card_expiration_year;
    const month = creditCard.creditCardExpirationMonth || creditCard.month || creditCard.credit_card_expiration_month;

    const cardInfo = cardValidator(cardNumber);
    const { card_type: cardType, valid } = cardInfo.getCardDetails();

    if (!valid) {
      reject(new InvalidCreditCard());
      return;
    }

    if (!(cardType === 'visa' || cardType === 'mastercard')) {
      reject(new UnacceptedCreditCard(cardType));
      return;
    }

    const currentMonth = new Date().getMonth() + 1;
    const currentYear = new Date().getFullYear();
    if (currentYear * 12 + currentMonth > year * 12 + month) {
      reject(new ExpiredCreditCard(String(cardNumber).replace('-', ''), month, year));
      return;
    }

    const timeoutMillis = randomInt(0, SUCCESS_PAYMENT_SERVICE_DURATION_MILLIS);
    setTimeout(() => {
      resolve({
        transaction_id: uuidv4(),
        cardType,
        cardNumber,
        amount: {
          currency_code: amount.currencyCode || amount.currency_code,
          units: amount.units,
          nanos: amount.nanos,
        },
      });
    }, timeoutMillis);
  });
}

// TODO: Revisit retry logic for buttercupPaymentsApiCharge
//       - Decide if per-attempt probability failures should bypass validation errors
//       - Consider whether to create a new client span per attempt instead of a single span
//       - Confirm max retry behavior from OpenFeature flag or default
module.exports.charge = async request => {
  // Create a SERVER span so attributes are promoted in Splunk O11y
  const span = tracer.startSpan('charge', {
    kind: SpanKind.SERVER,
    attributes: {
      'rpc.system': 'grpc',
      'rpc.service': 'PaymentService',
      'rpc.method': 'Charge',
    }
  });
  await OpenFeature.setProviderAndWait(flagProvider);
  // Fetch retry max from OpenFeature; default to 4 if not present
  //const retryMaxRaw = await OpenFeature.getClient().getNumberValue('paymentRetryMax', 4);
  const retryMaxRaw =  4;
  const RETRY_MAX = Math.max(0, Math.floor(retryMaxRaw));
  const RETRY_BASE_DELAY_MS = 150;
  const numberVariant = await OpenFeature.getClient().getNumberValue('paymentFailure', 0);
  // token will now be chosen per-attempt inside the retry loop

  const creditCard = request.creditCard || request.credit_card || {};
  const card = cardValidator(creditCard.creditCardNumber || creditCard.number || creditCard.credit_card_number);
  const { card_type: cardType, valid } = card.getCardDetails();
  const loyalty_level = random(LOYALTY_LEVEL);
  // Default to success version; on ultimate failure we overwrite to FAILURE_VERSION below
  const version = SUCCESS_VERSION;

  span.setAttributes({
    version,
    'app.payment.card_type': cardType,
    'app.payment.card_valid': valid,
    'app.loyalty.level': loyalty_level,
  });

  let attempt = 0;
  let lastErr = null;

  function sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
  }

  try {
    let result = null;
    for (attempt = 1; attempt <= RETRY_MAX; attempt++) {
      // Create a new client span per attempt
      const clientSpan = tracer.startSpan(
        'buttercup.payments.api',
        {
          kind: SpanKind.CLIENT,
          attributes: {
            'peer.service': 'ButtercupPayments',
            'http.url': 'https://api.buttercup-payments.com/charge',
            'http.method': 'POST',
            'net.peer.name': 'api.buttercup-payments.com',
            'net.peer.port': 443,
            'retry.attempt': attempt,
          },
        },
        trace.setSpan(context.active(), span)
      );

      // Recalculate success/failure for this attempt
      const shouldFailAttempt = numberVariant > 0 && Math.random() < numberVariant;
      const token = shouldFailAttempt ? API_TOKEN_FAILURE_TOKEN : API_TOKEN_SUCCESS_TOKEN;
      clientSpan.addEvent('attempt.start', { attempt, shouldFailAttempt });
      try {
        const resp = await buttercupPaymentsApiCharge(request, token);
        // Success
        clientSpan.addEvent('attempt.success', { attempt });
        clientSpan.setAttributes({ 'http.status_code': '200' });
        span.setStatus({ code: SpanStatusCode.OK });
        // Log within the OTel context of the client span before ending it
        context.with(trace.setSpan(context.active(), clientSpan), () => {
          logger.info(
            {
              severity: 'info',
              time: Math.floor(Date.now() / 1000),
              pid: process.pid,
              hostname: require('os').hostname(),
              name: 'paymentservice',
              trace_id: trace.getSpan(context.active()).spanContext().traceId,
              span_id: trace.getSpan(context.active()).spanContext().spanId,
              'service.name': 'payment',
              token: token,
              version: SUCCESS_VERSION,
              message: 'Charging through ButtercupPayments',
            }
          );
        });
        clientSpan.end();

        const baggage = propagation.getBaggage(context.active());
        const synthetic = baggage && baggage.getEntry('synthetic_request') && baggage.getEntry('synthetic_request').value === 'true';

        if (synthetic) {
          logger.info(
            {
              severity: 'info',
              time: Math.floor(Date.now() / 1000),
              pid: process.pid,
              hostname: require('os').hostname(),
              name: 'payment',
              trace_id: trace.getSpan(context.active()).spanContext().traceId,
              span_id: trace.getSpan(context.active()).spanContext().spanId,
              'service.name': 'payment',
              message: 'Processing synthetic request - setting app.payment.charged=false',
              synthetic_request: true,
            }
          );
        }

        span.setAttribute('app.payment.charged', !synthetic);

        const { transaction_id, cardType: resolvedCardType, cardNumber, amount } = resp;

        logger.info(
          {
            transactionId: transaction_id,
            cardType: resolvedCardType,
            lastFourDigits: String(cardNumber).substr(-4),
            amount: {
              units: amount.units,
              nanos: amount.nanos,
              currencyCode: amount.currency_code,
            },
            loyalty_level,
            retry_count: attempt - 1,
          },
          'Transaction complete.'
        );
        transactionsCounter.add(1, { 'app.payment.currency': amount.currency_code });
        span.setAttributes({ 'retry.count': attempt - 1, 'retry.success': true });
        result = { transactionId: transaction_id, success: true, retries: attempt - 1 };
        break;

      } catch (err) {
        lastErr = err;
        clientSpan.addEvent('attempt.failure', { attempt, code: String(err.code || 401) });
        clientSpan.setAttributes({ 'http.status_code': String(err.code || 401) });
        // Mark this attempt span as an error
        clientSpan.setStatus({ code: SpanStatusCode.ERROR, message: String(err.code || 401) });


        // Flag the root span for every 401 attempt (not just the final failure)
        if (err.code === 401) {
          span.setAttributes({
            version: FAILURE_VERSION,
            // TODO: populate actual kubernetes_pod_uid via Downward API (e.g., env var K8S_POD_UID)
            //kubernetes_pod_uid: process.env.K8S_POD_UID || 'UNKNOWN',
            error: true,
          });
        }

        // TODO: Revisit this log message to adjust for non-401 errors (currently always logs "Invalid API Token")
        // Per-attempt failure log in original raw JSON shape (keep version; lowercase severity)
        // Log within the OTel context of the client span before ending it
        context.with(trace.setSpan(context.active(), clientSpan), () => {
          logger.error(
            {
              severity: 'error',
              time: Math.floor(Date.now() / 1000),
              pid: process.pid,
              hostname: require('os').hostname(),
              name: 'payment',
              trace_id: trace.getSpan(context.active()).spanContext().traceId,
              span_id: trace.getSpan(context.active()).spanContext().spanId,
              'service.name': 'payment',
              token: API_TOKEN_FAILURE_TOKEN,
              version: FAILURE_VERSION,
              message: `Failed payment processing through ButtercupPayments: Invalid API Token (${API_TOKEN_FAILURE_TOKEN})`,
            }
          );
        });
        clientSpan.end();

        // If more attempts remain, backoff and retry
        if (attempt < RETRY_MAX) {
          const delay = RETRY_BASE_DELAY_MS * Math.pow(2, attempt - 1);
          await sleep(delay);
          continue;
        }
      }
    }

    if (result) {
      return result;
    }

// All attempts failed: mark spans and return a 500/401-style failure (no throw)
    const finalCode = (lastErr && lastErr.code === 401) ? 401 : 500;

    span.setAttributes({
      version: FAILURE_VERSION,
      error: true,
      'app.loyalty.level': 'gold',
      'retry.count': attempt - 1,
      'retry.success': false,
      'http.status_code': finalCode,
    });

    // set explicit error status on the root span so it doesn't show as "unknown"
    span.setStatus({ code: SpanStatusCode.ERROR, message: String(finalCode) });

    // keep baggage handling as you have it
    const baggage = propagation.getBaggage(context.active());
    const synthetic = baggage && baggage.getEntry('synthetic_request') && baggage.getEntry('synthetic_request').value === 'true';

    if (synthetic) {
      logger.info(
        {
          severity: 'info',
          time: Math.floor(Date.now() / 1000),
          pid: process.pid,
          hostname: require('os').hostname(),
          name: 'payment',
          trace_id: trace.getSpan(context.active()).spanContext().traceId,
          span_id: trace.getSpan(context.active()).spanContext().spanId,
          'service.name': 'payment',
          message: 'Processing synthetic request (all retries failed) - setting app.payment.charged=false',
          synthetic_request: true,
        }
      );
    }

    span.setAttribute('app.payment.charged', false);

    // final log INSIDE the root span context (so trace/span ids are injected)
    context.with(trace.setSpan(context.active(), span), () => {
      if (finalCode === 401) {
        logger.error(
          {
            severity: 'error',
            time: Math.floor(Date.now() / 1000),
            pid: process.pid,
            hostname: require('os').hostname(),
            name: 'paymentservice',
            trace_id: trace.getSpan(context.active()).spanContext().traceId,
            span_id: trace.getSpan(context.active()).spanContext().spanId,
            'service.name': 'paymentservice',
            token: API_TOKEN_FAILURE_TOKEN,
            version: FAILURE_VERSION,
            message: `Failed payment processing through ButtercupPayments after ${RETRY_MAX} retries: Invalid API Token (${API_TOKEN_FAILURE_TOKEN})`,

          }
        );
      } else {
        logger.error(
          {
            severity: 'error',
            time: Math.floor(Date.now() / 1000),
            pid: process.pid,
            hostname: require('os').hostname(),
            name: 'paymentservice',
            trace_id: trace.getSpan(context.active()).spanContext().traceId,
            span_id: trace.getSpan(context.active()).spanContext().spanId,
            'service.name': 'paymentservice',
            version: FAILURE_VERSION,
            message: 'Failed payment processing through ButtercupPayments after retries',

          }
        );
      }
    });
    // Throw after all retries so upstream services see the failure
    const errToThrow = new Error(
      finalCode === 401
        ? `Payment failed after retries: Invalid API Token (${API_TOKEN_FAILURE_TOKEN})`
        : 'Payment failed after retries'
    );
    // attach code for structured error handling
    errToThrow.code = finalCode;
throw errToThrow;
  } finally {
    span.end();
  }
};
