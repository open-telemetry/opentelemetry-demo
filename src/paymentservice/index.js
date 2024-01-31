'use strict'

// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
const { callbackify, promisify } = require('util')
const grpc = require('@grpc/grpc-js')
const protoLoader = require('@grpc/proto-loader')
const health = require('grpc-js-health-check')
const opentelemetry = require('@opentelemetry/api')

const charge = require('./charge')
const logger = require('./logger')

const otelDemoPackage = grpc.loadPackageDefinition(
  protoLoader.loadSync('demo.proto')
)

const featureFlagServiceClient = initFeatureFlagClient()
const getPaymentServiceSimulateSlowness = featureFlagServiceClient
  ? promisify(featureFlagServiceClient.getRangeFeatureFlag.bind(featureFlagServiceClient))
  : null

async function chargeServiceHandler(call) {
  const span = opentelemetry.trace.getActiveSpan()

  try {
    const amount = call.request.amount
    span.setAttributes({
      'app.payment.amount': parseFloat(`${amount.units}.${amount.nanos}`)
    })
    logger.info({ request: call.request }, 'Charge request received.')
    await simulateSlowness(span);

    return charge.charge(call.request)
  } catch (err) {
    logger.warn({ err })

    span.recordException(err)
    span.setStatus({ code: opentelemetry.SpanStatusCode.ERROR })

    throw err
  }
}

async function simulateSlowness(span) {
  if (getPaymentServiceSimulateSlowness) {
    try {
      const simulateSlownessResponse = await getPaymentServiceSimulateSlowness({
        name: 'paymentServiceSimulateSlowness',
        nameLowerBound: 'paymentServiceSimulateSlownessLowerBound',
        nameUpperBound: 'paymentServiceSimulateSlownessUpperBound'
      })
      if (simulateSlownessResponse.enabled) {
        const minimumDelayResponse = simulateSlownessResponse.lowerBound || 0
        const maximumDelayResponse = simulateSlownessResponse.upperBound || 500
        const delayMillis =
            minimumDelayResponse +
            Math.floor(Math.random() * (maximumDelayResponse - minimumDelayResponse))
        logger.info('Simulating payment service slowness, waiting %d.', delayMillis)
        span.setAttributes({ 'app.payment.simulatedSlowness': delayMillis })
        await new Promise((resolve) => setTimeout(resolve, delayMillis))
      }
    } catch (err) {
      logger.warn({err: err})
    }
  }
}

async function closeGracefully(signal) {
  featureFlagServiceClient.close()
  server.forceShutdown()
  process.kill(process.pid, signal)
}

const server = new grpc.Server()

server.addService(
  health.service,
  new health.Implementation({
    '': health.servingStatus.SERVING,
  })
)

server.addService(otelDemoPackage.oteldemo.PaymentService.service, {
  charge: callbackify(chargeServiceHandler),
})

server.bindAsync(
  `0.0.0.0:${process.env['PAYMENT_SERVICE_PORT']}`,
  grpc.ServerCredentials.createInsecure(),
  (err, port) => {
    if (err) {
      return logger.error({ err })
    }

    logger.info(`PaymentService gRPC server started on port ${port}`)
    server.start()
  }
)

function initFeatureFlagClient() {
  const featureFlagServiceAddress = process.env.FEATURE_FLAG_GRPC_SERVICE_ADDR
  if (!featureFlagServiceAddress) {
    logger.warn(
      'The feature flag service address is not set (FEATURE_FLAG_GRPC_SERVICE_ADDR). No artificial request duration variance will be introduced.'
    )
    return null
  }
  return new otelDemoPackage.oteldemo.FeatureFlagService(
    featureFlagServiceAddress,
    grpc.credentials.createInsecure()
  )
}

process.once('SIGINT', closeGracefully)
process.once('SIGTERM', closeGracefully)
