// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
const grpc = require('@grpc/grpc-js')
const protoLoader = require('@grpc/proto-loader')
const health = require('grpc-js-health-check')
const opentelemetry = require('@opentelemetry/api')
const fs = require('fs')
const path = require('path')

const charge = require('./charge')
const logger = require('./logger')

// Enhanced debugging function
function debugLog(message, data = {}) {
  const timestamp = new Date().toISOString()
  const logEntry = `[${timestamp}] PAYMENT_DEBUG: ${message} ${JSON.stringify(data, null, 2)}`
  console.log(logEntry)
  logger.info({ debug: true, timestamp, message, data }, 'Payment Debug Log')
}

async function chargeServiceHandler(call, callback) {
  const span = opentelemetry.trace.getActiveSpan();
  debugLog('Charge service handler called', { hasCall: !!call, hasRequest: !!call?.request })

  try {
    const amount = call.request.amount
    span?.setAttributes({
      'app.payment.amount': parseFloat(`${amount.units}.${amount.nanos}`).toFixed(2)
    })
    debugLog('Processing charge request', { 
      amount: amount,
      creditCard: call.request.creditCard ? 'present' : 'missing'
    })
    logger.info({ request: call.request }, "Charge request received.")

    const response = await charge.charge(call.request)
    debugLog('Charge completed successfully', { transactionId: response.transactionId })
    callback(null, response)

  } catch (err) {
    debugLog('Charge failed with error', { 
      error: err.message, 
      stack: err.stack,
      requestData: call.request 
    })
    logger.warn({ err })

    span?.recordException(err)
    span?.setStatus({ code: opentelemetry.SpanStatusCode.ERROR })
    callback(err)
  }
}

async function closeGracefully(signal) {
  debugLog('Graceful shutdown initiated', { signal, pid: process.pid })
  try {
    server.forceShutdown()
    debugLog('Server shutdown completed')
  } catch (err) {
    debugLog('Error during server shutdown', { error: err.message })
  }
  process.kill(process.pid, signal)
}

// Debug environment and dependencies
debugLog('Starting payment service initialization', {
  nodeVersion: process.version,
  platform: process.platform,
  arch: process.arch,
  cwd: process.cwd(),
  env: {
    PAYMENT_PORT: process.env.PAYMENT_PORT,
    IPV6_ENABLED: process.env.IPV6_ENABLED,
    OTEL_SERVICE_NAME: process.env.OTEL_SERVICE_NAME,
    FLAGD_HOST: process.env.FLAGD_HOST,
    OTEL_EXPORTER_OTLP_ENDPOINT: process.env.OTEL_EXPORTER_OTLP_ENDPOINT
  }
})

// Check if proto file exists
const protoPath = path.resolve('demo.proto')
debugLog('Checking proto file', { 
  protoPath,
  exists: fs.existsSync(protoPath),
  cwd: process.cwd()
})

if (!fs.existsSync(protoPath)) {
  debugLog('Proto file not found, checking alternative locations')
  const altPaths = [
    path.resolve('../pb/demo.proto'),
    path.resolve('../../pb/demo.proto'),
    path.resolve('/app/demo.proto')
  ]
  
  for (const altPath of altPaths) {
    debugLog('Checking alternative proto path', { path: altPath, exists: fs.existsSync(altPath) })
    if (fs.existsSync(altPath)) {
      debugLog('Found proto file at alternative location', { path: altPath })
      break
    }
  }
}

try {
  debugLog('Loading proto definition')
  const otelDemoPackage = grpc.loadPackageDefinition(protoLoader.loadSync('demo.proto'))
  debugLog('Proto definition loaded successfully', { 
    hasOteldemo: !!otelDemoPackage.oteldemo,
    hasPaymentService: !!otelDemoPackage.oteldemo?.PaymentService
  })
  
  debugLog('Creating gRPC server')
  const server = new grpc.Server()
  debugLog('gRPC server created successfully')

  debugLog('Adding health check service')
  server.addService(health.service, new health.Implementation({
    '': health.servingStatus.SERVING
  }))
  debugLog('Health check service added')

  debugLog('Adding payment service')
  server.addService(otelDemoPackage.oteldemo.PaymentService.service, { charge: chargeServiceHandler })
  debugLog('Payment service added')

  // Configure IPv4 or IPv6 address based on environment variable
  const ipv6Enabled = process.env.IPV6_ENABLED === 'true' || process.env.IPV6_ENABLED === '1';
  const host = ipv6Enabled ? '[::]' : '0.0.0.0';
  const port = process.env['PAYMENT_PORT'] || '8080';
  const address = `${host}:${port}`;

  debugLog('Server binding configuration', {
    IPV6_ENABLED: process.env.IPV6_ENABLED,
    ipv6Enabled,
    host,
    port,
    address
  })

  console.log(`DEBUG: IPV6_ENABLED = ${process.env.IPV6_ENABLED || 'not set'}`);
  console.log(`DEBUG: Binding to ${address} (IPv6 ${ipv6Enabled ? 'ENABLED' : 'DISABLED'})`);

  debugLog('Starting server bind operation')
  server.bindAsync(address, grpc.ServerCredentials.createInsecure(), (err, boundPort) => {
    if (err) {
      debugLog('Server bind failed', { 
        error: err.message, 
        code: err.code, 
        details: err.details,
        stack: err.stack,
        address 
      })
      logger.error({ err, address }, 'Failed to bind server')
      process.exit(1)
    }

    debugLog('Server bind successful', { address, boundPort })
    logger.info(`payment gRPC server started on ${address} (bound to port ${boundPort})`)
    
    // Test server health
    setTimeout(() => {
      debugLog('Server health check', { 
        serverStarted: true,
        uptime: process.uptime(),
        memoryUsage: process.memoryUsage()
      })
    }, 1000)
  })

} catch (err) {
  debugLog('Fatal error during server initialization', {
    error: err.message,
    stack: err.stack
  })
  logger.error({ err }, 'Fatal error during server initialization')
  process.exit(1)
}

// Enhanced process event handling
process.once('SIGINT', closeGracefully)
process.once('SIGTERM', closeGracefully)

process.on('uncaughtException', (err) => {
  debugLog('Uncaught exception', { 
    error: err.message, 
    stack: err.stack 
  })
  logger.error({ err }, 'Uncaught exception')
  process.exit(1)
})

process.on('unhandledRejection', (reason, promise) => {
  debugLog('Unhandled promise rejection', { 
    reason: reason?.message || reason, 
    stack: reason?.stack 
  })
  logger.error({ reason, promise }, 'Unhandled promise rejection')
  process.exit(1)
})

debugLog('Payment service initialization completed', { pid: process.pid })
