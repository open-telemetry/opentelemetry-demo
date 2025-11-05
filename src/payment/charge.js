// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
const { context, propagation, trace, metrics } = require('@opentelemetry/api');
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

/** Return random element from given array */
function random(arr) {
  const index = Math.floor(Math.random() * arr.length);
  return arr[index];
}

module.exports.charge = async request => {
  const span = tracer.startSpan('charge');

  await OpenFeature.setProviderAndWait(flagProvider);

  const numberVariant =  await OpenFeature.getClient().getNumberValue("paymentFailure", 0);

  if (numberVariant > 0) {
    // n% chance to fail with app.loyalty.level=gold
    if (Math.random() < numberVariant) {
      // Create child span for ButtercupPayment even on failure
      const externalPaymentSpan = tracer.startSpan('HTTP POST', {
        attributes: {
          'http.method': 'POST',
          'http.url': 'https://api.buttercuppayments.com/v1/charge',
          'http.target': '/v1/charge',
          'http.host': 'api.buttercuppayments.com',
          'http.scheme': 'https',
          'net.peer.name': 'api.buttercuppayments.com',
          'net.peer.port': 443,
          'span.kind': 'client'
        }
      }, context.active());

      // Simulate external payment processing time
      await new Promise(resolve => setTimeout(resolve, 50 + Math.random() * 100));

      externalPaymentSpan.setAttribute('http.status_code', 400);
      externalPaymentSpan.recordException(new Error('Payment request failed. Invalid token.'));
      externalPaymentSpan.end();

      span.setAttributes({'app.loyalty.level': 'gold' });
      span.end();

      throw new Error('Payment request failed. Invalid token. app.loyalty.level=gold');
    }
  }

  const {
    creditCardNumber: number,
    creditCardExpirationYear: year,
    creditCardExpirationMonth: month
  } = request.creditCard;
  const currentMonth = new Date().getMonth() + 1;
  const currentYear = new Date().getFullYear();
  const lastFourDigits = number.substr(-4);
  const transactionId = uuidv4();

  const card = cardValidator(number);
  const { card_type: cardType, valid } = card.getCardDetails();

  const loyalty_level = random(LOYALTY_LEVEL);

  span.setAttributes({
    'app.payment.card_type': cardType,
    'app.payment.card_valid': valid,
    'app.loyalty.level': loyalty_level
  });

  if (!valid) {
    throw new Error('Credit card info is invalid.');
  }

  if (!['visa', 'mastercard'].includes(cardType)) {
    throw new Error(`Sorry, we cannot process ${cardType} credit cards. Only VISA or MasterCard is accepted.`);
  }

  if ((currentYear * 12 + currentMonth) > (year * 12 + month)) {
    throw new Error(`The credit card (ending ${lastFourDigits}) expired on ${month}/${year}.`);
  }

  // Create child span to emulate HTTP call to external payment service
  const externalPaymentSpan = tracer.startSpan('HTTP POST', {
    attributes: {
      'http.method': 'POST',
      'http.url': 'https://api.buttercuppayments.com/v1/charge',
      'http.target': '/v1/charge',
      'http.host': 'api.buttercuppayments.com',
      'http.scheme': 'https',
      'net.peer.name': 'api.buttercuppayments.com',
      'net.peer.port': 443,
      'span.kind': 'client'
    }
  }, context.active());

  // Simulate external payment processing time
  await new Promise(resolve => setTimeout(resolve, 50 + Math.random() * 100));

  externalPaymentSpan.setAttribute('http.status_code', 200);
  externalPaymentSpan.end();

  // Check baggage for synthetic_request=true, and add charged attribute accordingly
  const baggage = propagation.getBaggage(context.active());
  if (baggage && baggage.getEntry('synthetic_request') && baggage.getEntry('synthetic_request').value === 'true') {
    span.setAttribute('app.payment.charged', false);
  } else {
    span.setAttribute('app.payment.charged', true);
  }

  const { units, nanos, currencyCode } = request.amount;
  logger.info({ transactionId, cardType, lastFourDigits, amount: { units, nanos, currencyCode }, loyalty_level }, 'Transaction complete.');
  transactionsCounter.add(1, { 'app.payment.currency': currencyCode });
  span.end();

  return { transactionId };
};
