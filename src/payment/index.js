// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
const grpc = require('@grpc/grpc-js')
const protoLoader = require('@grpc/proto-loader')
const health = require('grpc-js-health-check')
const opentelemetry = require('@opentelemetry/api')
const tracer = opentelemetry.trace.getTracer(process.env.OTEL_SERVICE_NAME);

const charge = require('./charge')
const logger = require('./logger')

async function chargeServiceHandler(call, callback) {
  // Check if we have an active span if not start a new one
  let span = opentelemetry.trace.getActiveSpan();
  let startedSpan = false;
  if (!span)
  {
    span = tracer.startSpan('chargeServiceHandler');
    // Mark this new span as active
    tracer.setSpan(tracer.context.active(), span)
    startedSpan = true;
  }

  try {
    const amount = call.request.amount
    span.setAttributes({
      'app.payment.amount': parseFloat(`${amount.units}.${amount.nanos}`).toFixed(2)
    })
    logger.info({ request: call.request }, "Charge request received.")

    const response = await charge.charge(call.request)
    callback(null, response)

  } catch (err) {
    logger.warn({ err })

    span.recordException(err)
    span.setStatus({ code: opentelemetry.SpanStatusCode.ERROR })
    // Make sure we cleanup by closing the span if we started it.
    if (startedSpan) {
      span.end();
    }
    callback(err)
  }
}

async function closeGracefully(signal) {
  server.forceShutdown()
  process.kill(process.pid, signal)
}

const otelDemoPackage = grpc.loadPackageDefinition(protoLoader.loadSync('demo.proto'))
const server = new grpc.Server()

server.addService(health.service, new health.Implementation({
  '': health.servingStatus.SERVING
}))

server.addService(otelDemoPackage.oteldemo.PaymentService.service, { charge: chargeServiceHandler })

server.bindAsync(`0.0.0.0:${process.env['PAYMENT_PORT']}`, grpc.ServerCredentials.createInsecure(), (err, port) => {
  if (err) {
    return logger.error({ err })
  }

  logger.info(`payment gRPC server started on port ${port}`)
})

process.once('SIGINT', closeGracefully)
process.once('SIGTERM', closeGracefully)
