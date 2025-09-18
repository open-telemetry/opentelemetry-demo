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

// Payment cache for storing transaction data
const paymentCache = new Map();
const CACHE_MAX_SIZE = 1000;
let cacheStats = {
  hits: 0,
  misses: 0,
  evictions: 0,
  rejections: 0,
  currentSize: 0,
  maxSize: CACHE_MAX_SIZE
};

/** Return random element from given array */
function random(arr) {
  const index = Math.floor(Math.random() * arr.length);
  return arr[index];
}

/** Get comprehensive system metrics including CPU, memory, and performance data */
function getSystemMetrics() {
  const memoryUsage = process.memoryUsage();
  const cpuUsage = process.cpuUsage();
  const hrTime = process.hrtime();
  
  return {
    memory: {
      heapUsed: Math.round(memoryUsage.heapUsed / 1024 / 1024), // MB
      heapTotal: Math.round(memoryUsage.heapTotal / 1024 / 1024), // MB
      external: Math.round(memoryUsage.external / 1024 / 1024), // MB
      rss: Math.round(memoryUsage.rss / 1024 / 1024), // MB
      arrayBuffers: Math.round(memoryUsage.arrayBuffers / 1024 / 1024), // MB
      heapUtilization: Math.round((memoryUsage.heapUsed / memoryUsage.heapTotal) * 100) // %
    },
    cpu: {
      user: Math.round(cpuUsage.user / 1000), // Convert to milliseconds
      system: Math.round(cpuUsage.system / 1000), // Convert to milliseconds
      total: Math.round((cpuUsage.user + cpuUsage.system) / 1000) // Total CPU time in ms
    },
    process: {
      uptime: Math.round(process.uptime()), // seconds
      pid: process.pid,
      platform: process.platform,
      nodeVersion: process.version,
      hrTime: hrTime[0] * 1000000000 + hrTime[1] // nanoseconds since process start
    },
    performance: {
      eventLoopDelay: Math.round(Math.random() * 10), // Simulated event loop delay in ms
      activeHandles: process._getActiveHandles().length,
      activeRequests: process._getActiveRequests().length
    },
    timestamp: Date.now()
  };
}

/** Get trace context from current span */
function getTraceContext() {
  const activeSpan = trace.getActiveSpan();
  const spanContext = activeSpan?.spanContext();
  
  return {
    traceId: spanContext?.traceId || 'unknown',
    spanId: spanContext?.spanId || 'unknown',
    traceFlags: spanContext?.traceFlags || 0
  };
}

/** Log cache state with detailed metrics */
function logCacheState(operation, context = {}) {
  const systemMetrics = getSystemMetrics();
  const traceContext = getTraceContext();
  
  return {
    operation,
    cacheSize: paymentCache.size,
    maxCapacity: CACHE_MAX_SIZE,
    utilizationPercent: Math.round((paymentCache.size / CACHE_MAX_SIZE) * 100),
    hitRate: cacheStats.hits > 0 ? (cacheStats.hits / (cacheStats.hits + cacheStats.misses)) : 0,
    stats: { ...cacheStats },
    systemMetrics,
    traceContext,
    ...context
  };
}

/** Simulate cache overflow scenario */
function simulateCacheOverflow(transactionId, span) {
  const startTime = process.hrtime.bigint();
  const cacheKey = `txn_${transactionId}_${Date.now()}`;
  const transactionData = {
    id: transactionId,
    timestamp: new Date().toISOString(),
    data: Buffer.alloc(1024 * 10), // 10KB of data per transaction
    metadata: {
      processed: false,
      retryCount: 0,
      priority: Math.floor(Math.random() * 5)
    }
  };

  // Check if cache is at capacity
  if (paymentCache.size >= CACHE_MAX_SIZE) {
    cacheStats.rejections++;
    
    const errorContext = {
      cacheKey,
      transactionId,
      timestamp: new Date().toISOString(),
      traceId: span.spanContext().traceId,
      spanId: span.spanContext().spanId
    };

    const endTime = process.hrtime.bigint();
    const operationDuration = Number(endTime - startTime) / 1000000; // Convert to milliseconds
    const traceContext = getTraceContext();
    const systemMetrics = getSystemMetrics();
    
    // Log cache overflow error with detailed metrics
    logger.error({
      error: {
        type: 'CacheOverflowError',
        message: 'Payment cache capacity exceeded, unable to store transaction data',
        code: 'CACHE_CAPACITY_EXCEEDED',
        stack: new Error().stack
      },
      context: {
        transactionId: errorContext.transactionId,
        cacheKey: errorContext.cacheKey,
        rejectionReason: 'cache_capacity_exceeded',
        operationType: 'cache_write'
      },
      cache: logCacheState('overflow_rejection', {
        attemptedOperation: 'store_transaction',
        dataSize: '10KB',
        overflowBy: paymentCache.size - CACHE_MAX_SIZE + 1
      }),
      performance: {
        operationDuration: Math.round(operationDuration * 100) / 100, // Round to 2 decimal places
        memoryPressure: 'high',
        cacheEfficiency: cacheStats.hits / Math.max(cacheStats.hits + cacheStats.misses, 1),
        throughput: 'degraded',
        latency: 'elevated'
      },
      systemMetrics,
      traceContext,
      service: 'payment-service',
      operation: 'cache_store'
    }, 'Payment cache overflow: Transaction data rejected due to capacity limits');

    span.setAttributes({
      'app.payment.cache.overflow': true,
      'app.payment.cache.size': paymentCache.size,
      'app.payment.cache.capacity': CACHE_MAX_SIZE,
      'app.payment.cache.rejection_reason': 'capacity_exceeded'
    });

    throw new Error(`Payment cache overflow: Unable to process transaction ${transactionId}. Cache at maximum capacity (${CACHE_MAX_SIZE} items).`);
  }

  // Store in cache and log successful operation
  paymentCache.set(cacheKey, transactionData);
  cacheStats.currentSize = paymentCache.size;

  const endTime = process.hrtime.bigint();
  const operationDuration = Number(endTime - startTime) / 1000000; // Convert to milliseconds
  const traceContext = getTraceContext();
  const systemMetrics = getSystemMetrics();
  
  logger.info({
    cache: logCacheState('successful_store', {
      cacheKey,
      dataSize: '10KB',
      operationType: 'store_transaction'
    }),
    context: {
      transactionId,
      cacheKey,
      operationType: 'cache_write'
    },
    performance: {
      operationDuration: Math.round(operationDuration * 100) / 100, // Round to 2 decimal places
      throughput: 'normal',
      latency: 'normal'
    },
    systemMetrics,
    traceContext,
    service: 'payment-service',
    operation: 'cache_store'
  }, 'Transaction data successfully stored in payment cache');

  return cacheKey;
}

module.exports.charge = async request => {
  const span = tracer.startSpan('charge');

  await OpenFeature.setProviderAndWait(flagProvider);

  const numberVariant =  await OpenFeature.getClient().getNumberValue("paymentFailure", 0);
  const cacheLeakEnabled = await OpenFeature.getClient().getBooleanValue("paymentCacheLeak", false);

  if (numberVariant > 0) {
    // n% chance to fail with app.loyalty.level=gold
    if (Math.random() < numberVariant) {
      const loyaltyLevel = 'gold';
      const errorContext = {
        userId: request.userId || `user_${Math.floor(Math.random() * 10000)}`,
        loyaltyLevel: loyaltyLevel,
        transactionId: uuidv4(),
        paymentMethod: 'token_validation',
        amount: request.amount,
        timestamp: new Date().toISOString(),
        traceId: span.spanContext().traceId,
        spanId: span.spanContext().spanId
      };

      const traceContext = getTraceContext();
      const systemMetrics = getSystemMetrics();
      
      // Log detailed payment failure with context
      logger.error({
        error: {
          type: 'TokenValidationError',
          message: `Invalid loyalty token for ${loyaltyLevel} tier user`,
          code: 'INVALID_LOYALTY_TOKEN',
          stack: new Error().stack
        },
        context: {
          userId: errorContext.userId,
          loyaltyLevel: errorContext.loyaltyLevel,
          transactionId: errorContext.transactionId,
          paymentMethod: errorContext.paymentMethod,
          amount: errorContext.amount,
          validationStep: 'loyalty_token_verification',
          tokenType: 'loyalty_access_token'
        },
        performance: {
          duration: Math.floor(Math.random() * 500) + 100, // Simulate processing time
          processingLatency: 'elevated'
        },
        systemMetrics,
        traceContext,
        service: 'payment-service',
        operation: 'charge_payment'
      }, 'Payment processing failed during loyalty token validation');

      span.setAttributes({
        'app.loyalty.level': loyaltyLevel,
        'app.payment.error.type': 'TokenValidationError',
        'app.payment.error.code': 'INVALID_LOYALTY_TOKEN',
        'app.payment.user_id': errorContext.userId,
        'app.payment.transaction_id': errorContext.transactionId
      });
      span.recordException(new Error(`Token validation failed for ${loyaltyLevel} tier user`));
      span.setStatus({ code: 2, message: 'Payment processing failed' }); // ERROR status
      span.end();

      throw new Error(`Payment processing failed: Invalid loyalty token for ${loyaltyLevel} tier user. Transaction ID: ${errorContext.transactionId}`);
    }
  }

  // Simulate cache leak scenario
  if (cacheLeakEnabled) {
    const tempTransactionId = uuidv4();
    
    try {
      // Simulate aggressive cache usage that leads to overflow
      for (let i = 0; i < 5; i++) {
        simulateCacheOverflow(`${tempTransactionId}_batch_${i}`, span);
      }
      
      const traceContext = getTraceContext();
      const systemMetrics = getSystemMetrics();
      
      logger.warn({
        cache: logCacheState('leak_simulation', {
          batchOperations: 5,
          leakType: 'aggressive_caching'
        }),
        context: {
          simulationType: 'cache_leak',
          batchSize: 5,
          baseTransactionId: tempTransactionId
        },
        performance: {
          memoryGrowth: 'rapid',
          cacheGrowthRate: '5x_normal',
          resourcePressure: 'increasing'
        },
        systemMetrics,
        traceContext,
        service: 'payment-service',
        operation: 'cache_leak_simulation'
      }, 'Payment cache experiencing rapid growth due to aggressive caching behavior');
      
    } catch (cacheError) {
      // Cache overflow occurred during leak simulation
      span.setAttributes({
        'app.payment.cache.leak_detected': true,
        'app.payment.cache.overflow_during_leak': true
      });
      
      // Re-throw the cache error to propagate the failure
      throw cacheError;
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

  // Check baggage for synthetic_request=true, and add charged attribute accordingly
  const baggage = propagation.getBaggage(context.active());
  if (baggage && baggage.getEntry('synthetic_request') && baggage.getEntry('synthetic_request').value === 'true') {
    span.setAttribute('app.payment.charged', false);
  } else {
    span.setAttribute('app.payment.charged', true);
  }

  const { units, nanos, currencyCode } = request.amount;
  const traceContext = getTraceContext();
  const systemMetrics = getSystemMetrics();
  
  logger.info({ 
    transactionId, 
    cardType, 
    lastFourDigits, 
    amount: { units, nanos, currencyCode }, 
    loyalty_level,
    systemMetrics,
    traceContext,
    service: 'payment-service',
    operation: 'charge_payment'
  }, 'Transaction complete.');
  transactionsCounter.add(1, { 'app.payment.currency': currencyCode });
  span.end();

  return { transactionId };
};
