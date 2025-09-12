// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
const { context, propagation, trace, metrics } = require('@opentelemetry/api');
const cardValidator = require('simple-card-validator');
const { v4: uuidv4 } = require('uuid');

const { OpenFeature } = require('@openfeature/server-sdk');
const { FlagdProvider } = require('@openfeature/flagd-provider');

const logger = require('./logger');

// Enhanced debugging function for charge module
function chargeDebugLog(message, data = {}) {
  const timestamp = new Date().toISOString()
  const logEntry = `[${timestamp}] CHARGE_DEBUG: ${message} ${JSON.stringify(data, null, 2)}`
  console.log(logEntry)
  logger.info({ debug: true, module: 'charge', timestamp, message, data }, 'Charge Debug Log')
}

chargeDebugLog('Initializing charge module', {
  hasOpenFeature: !!OpenFeature,
  hasFlagdProvider: !!FlagdProvider,
  env: {
    FLAGD_HOST: process.env.FLAGD_HOST,
    FLAGD_PORT: process.env.FLAGD_PORT
  }
})

let flagProvider
try {
  flagProvider = new FlagdProvider()
  chargeDebugLog('FlagdProvider created successfully')
} catch (err) {
  chargeDebugLog('Failed to create FlagdProvider', { error: err.message, stack: err.stack })
  // Create a fallback provider that always returns default values
  flagProvider = {
    getNumberValue: async () => 0
  }
}
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
  chargeDebugLog('Starting charge processing', {
    hasRequest: !!request,
    requestKeys: request ? Object.keys(request) : [],
    spanId: span?.spanContext()?.spanId
  })

  try {
    chargeDebugLog('Setting up OpenFeature provider')
    await OpenFeature.setProviderAndWait(flagProvider);
    chargeDebugLog('OpenFeature provider set successfully')

    chargeDebugLog('Getting payment failure flag value')
    const numberVariant = await OpenFeature.getClient().getNumberValue("paymentFailure", 0);
    chargeDebugLog('Payment failure flag retrieved', { numberVariant })

    if (numberVariant > 0) {
      const randomValue = Math.random()
      chargeDebugLog('Checking payment failure simulation', { 
        numberVariant, 
        randomValue, 
        willFail: randomValue < numberVariant 
      })
      
      // n% chance to fail with app.loyalty.level=gold
      if (randomValue < numberVariant) {
        span.setAttributes({'app.loyalty.level': 'gold' });
        span.end();
        chargeDebugLog('Simulating payment failure')
        throw new Error('Payment request failed. Invalid token. app.loyalty.level=gold');
      }
    }

    chargeDebugLog('Extracting credit card information')
    if (!request.creditCard) {
      chargeDebugLog('Missing credit card in request', { request })
      throw new Error('Credit card information is required')
    }

    const {
      creditCardNumber: number,
      creditCardExpirationYear: year,
      creditCardExpirationMonth: month
    } = request.creditCard;
    
    chargeDebugLog('Credit card data extracted', {
      hasNumber: !!number,
      numberLength: number ? number.length : 0,
      year,
      month
    })
    
    const currentMonth = new Date().getMonth() + 1;
    const currentYear = new Date().getFullYear();
    const lastFourDigits = number.substr(-4);
    const transactionId = uuidv4();
    
    chargeDebugLog('Transaction details', {
      transactionId,
      lastFourDigits,
      currentMonth,
      currentYear
    })

    chargeDebugLog('Validating credit card')
    const card = cardValidator(number);
    const { card_type: cardType, valid } = card.getCardDetails();
    
    chargeDebugLog('Card validation results', {
      cardType,
      valid,
      cardDetails: card.getCardDetails()
    })

    const loyalty_level = random(LOYALTY_LEVEL);
    
    chargeDebugLog('Setting span attributes', {
      cardType,
      valid,
      loyalty_level
    })

    span.setAttributes({
      'app.payment.card_type': cardType,
      'app.payment.card_valid': valid,
      'app.loyalty.level': loyalty_level
    });

    if (!valid) {
      chargeDebugLog('Card validation failed', { cardType, number: `****${lastFourDigits}` })
      throw new Error('Credit card info is invalid.');
    }

    if (!['visa', 'mastercard'].includes(cardType)) {
      chargeDebugLog('Unsupported card type', { cardType })
      throw new Error(`Sorry, we cannot process ${cardType} credit cards. Only VISA or MasterCard is accepted.`);
    }

    const currentMonthTotal = currentYear * 12 + currentMonth
    const cardMonthTotal = year * 12 + month
    chargeDebugLog('Checking card expiration', {
      currentMonthTotal,
      cardMonthTotal,
      isExpired: currentMonthTotal > cardMonthTotal
    })
    
    if (currentMonthTotal > cardMonthTotal) {
      chargeDebugLog('Card expired', { month, year, lastFourDigits })
      throw new Error(`The credit card (ending ${lastFourDigits}) expired on ${month}/${year}.`);
    }

    // Check baggage for synthetic_request=true, and add charged attribute accordingly
    chargeDebugLog('Checking baggage for synthetic request')
    const baggage = propagation.getBaggage(context.active());
    const syntheticEntry = baggage?.getEntry('synthetic_request')
    const isSynthetic = syntheticEntry?.value === 'true'
    
    chargeDebugLog('Baggage analysis', {
      hasBaggage: !!baggage,
      syntheticEntry: syntheticEntry?.value,
      isSynthetic
    })
    
    if (isSynthetic) {
      span.setAttribute('app.payment.charged', false);
    } else {
      span.setAttribute('app.payment.charged', true);
    }

    const { units, nanos, currencyCode } = request.amount;
    
    chargeDebugLog('Completing transaction', {
      transactionId,
      cardType,
      lastFourDigits,
      amount: { units, nanos, currencyCode },
      loyalty_level
    })
    
    logger.info({ transactionId, cardType, lastFourDigits, amount: { units, nanos, currencyCode }, loyalty_level }, 'Transaction complete.');
    transactionsCounter.add(1, { 'app.payment.currency': currencyCode });
    span.end();

    chargeDebugLog('Charge processing completed successfully', { transactionId })
    return { transactionId };
    
  } catch (err) {
    chargeDebugLog('Charge processing failed', {
      error: err.message,
      stack: err.stack,
      request: request ? {
        hasCreditCard: !!request.creditCard,
        hasAmount: !!request.amount
      } : null
    })
    span?.recordException(err)
    span?.setStatus({ code: 2 }) // ERROR
    span?.end()
    throw err
  }
};
