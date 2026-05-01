// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
const protobuf = require('protobufjs');
const { trace, metrics, SpanStatusCode } = require('@opentelemetry/api');
const { v4: uuidv4 } = require('uuid');

const { OpenFeature } = require('@openfeature/server-sdk');
const { FlagdProvider } = require('@openfeature/flagd-provider');
const flagProvider = new FlagdProvider();

const logger = require('./logger');
const kafkaProducer = require('./kafkaProducer');

const tracer = trace.getTracer('payment');
const meter = metrics.getMeter('payment');
const refundsCounter = meter.createCounter('app.payment.refunds');

const REFUNDS_TOPIC = 'refunds';

const RefundResultType = protobuf.loadSync('demo.proto').lookupType('oteldemo.RefundResult');

module.exports.refund = async request => {
  const span = tracer.startSpan('refund');

  try {
    await OpenFeature.setProviderAndWait(flagProvider);

    const numberVariant = await OpenFeature.getClient().getNumberValue("paymentServiceRefundFailure", 0);

    if (numberVariant > 0) {
      if (Math.random() < numberVariant) {
        throw new Error('Refund request failed.');
      }

      // Deterministic failure for demo: emails containing "125@"
      const email = request.email || '';
      if (email.match(/125@/)) {
        throw new Error('Payment processor declined the refund request.');
      }
    }

    const { orderId, transactionId, amount, email } = request;
    const refundTransactionId = uuidv4();

    span.setAttributes({
      'app.payment.order_id': orderId || '',
      'app.payment.transaction_id': transactionId || '',
      'app.payment.refund_transaction_id': refundTransactionId,
    });

    logger.info({ orderId, transactionId, refundTransactionId }, 'Refund complete.');
    refundsCounter.add(1);

    // Publish to the refunds topic so accounting can mark the order refunded.
    // Failure to publish does not fail the refund — the card has already been credited.
    const message = RefundResultType.create({
      orderId: orderId || '',
      transactionId: transactionId || '',
      refundTransactionId,
      amount,
      email: email || '',
    });
    const payload = RefundResultType.encode(message).finish();
    await kafkaProducer.publish(REFUNDS_TOPIC, Buffer.from(payload));

    return { refundTransactionId, success: true };
  } catch (err) {
    span.recordException(err);
    span.setStatus({ code: SpanStatusCode.ERROR, message: err.message });
    throw err;
  } finally {
    span.end();
  }
};
