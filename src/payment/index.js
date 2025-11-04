// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
const { GrpcInstrumentation } = require('@opentelemetry/instrumentation-grpc');
const { registerInstrumentations } = require('@opentelemetry/instrumentation');
const opentelemetry = require('@opentelemetry/api')

registerInstrumentations({
  instrumentations: [new GrpcInstrumentation()]
});

// Load ALL modules AFTER instrumentation is registered
// (charge.js uses FlagdProvider which uses gRPC internally)
const grpc = require('@grpc/grpc-js')
const protoLoader = require('@grpc/proto-loader')
const health = require('grpc-js-health-check')
const charge = require('./charge')
const logger = require('./logger')

async function chargeServiceHandler(call, callback) {
  const span = opentelemetry.trace.getActiveSpan();
  console.log('Span:', span);

  const newSpan = opentelemetry.trace.getTracer('payment').startSpan('blah123', undefined, opentelemetry.context.active());
  newSpan.end();
  
  const tracerProvider = opentelemetry.trace.getTracerProvider();
  console.log('TracerProvider:', tracerProvider);
  console.log('TracerProvider type:', tracerProvider.constructor.name);
  
  // Try to access the active span processor and exporter config
  if (tracerProvider._delegate) {
    console.log('Delegate TracerProvider:', tracerProvider._delegate.constructor.name);
    console.log('Active Span Processor:', tracerProvider._delegate.activeSpanProcessor);
    console.log('Span Processors:', tracerProvider._delegate._spanProcessors);
    
    // Log exporters from span processors
    if (tracerProvider._delegate._spanProcessors) {
      tracerProvider._delegate._spanProcessors.forEach((processor, index) => {
        console.log(`Processor ${index}:`, processor.constructor.name);
        if (processor._exporter) {
          console.log(`  Exporter:`, processor._exporter.constructor.name);
          console.log(`  Exporter URL:`, processor._exporter.url || processor._exporter._otlpExporter?.url);
        }
      });
    }
  }

  try {
    const amount = call.request.amount
    span?.setAttributes({
      'app.payment.amount': parseFloat(`${amount.units}.${amount.nanos}`).toFixed(2)
    })
    logger.info({ request: call.request }, "Charge request received.")

    const response = await charge.charge(call.request)
    callback(null, response)

    //span?.setStatus({ code: opentelemetry.SpanStatusCode.OK })
    //span?.end()

  } catch (err) {
    logger.warn({ err })

    span?.recordException(err)
    span?.setStatus({ code: opentelemetry.SpanStatusCode.ERROR })
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


let ip = "0.0.0.0";

const ipv6_enabled = process.env.IPV6_ENABLED;

if (ipv6_enabled == "true") {
  ip = "[::]";
  logger.info(`Overwriting Localhost IP: ${ip}`)
}

const address = ip + `:${process.env['PAYMENT_PORT']}`;

server.bindAsync(address, grpc.ServerCredentials.createInsecure(), (err, port) => {
  if (err) {
    return logger.error({ err })
  }

  logger.info(`payment gRPC server started on ${address}`)
})

process.once('SIGINT', closeGracefully)
process.once('SIGTERM', closeGracefully)
