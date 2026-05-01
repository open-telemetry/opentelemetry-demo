// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

const { Kafka, logLevel } = require('kafkajs');

const logger = require('./logger');

const brokers = process.env.KAFKA_ADDR ? [process.env.KAFKA_ADDR] : [];
let producer = null;
let connecting = null;

if (brokers.length > 0) {
  const kafka = new Kafka({
    clientId: 'payment',
    brokers,
    logLevel: logLevel.WARN,
  });
  producer = kafka.producer();
  connecting = producer.connect()
    .then(() => logger.info({ brokers }, 'kafka producer connected'))
    .catch(err => {
      logger.error({ err }, 'kafka producer connect failed');
      producer = null;
    });
} else {
  logger.warn('KAFKA_ADDR not set; refund events will not be published');
}

module.exports.publish = async (topic, value) => {
  if (!producer) return;
  try {
    if (connecting) await connecting;
    if (!producer) return;
    await producer.send({ topic, messages: [{ value }] });
  } catch (err) {
    // Refund itself succeeded; failing to publish is logged but not surfaced.
    logger.error({ err, topic }, 'failed to publish kafka message');
  }
};
