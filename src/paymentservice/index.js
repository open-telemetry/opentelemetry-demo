// Copyright 2018 Google LLC
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//      http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

// Npm
const grpc = require('@grpc/grpc-js')
const protoLoader = require('@grpc/proto-loader')
const health = require('grpc-health-check')
const opentelemetry = require('@opentelemetry/api')
const pino = require('pino')
const cardValidator = require('simple-card-validator')
const { v4: uuidv4 } = require('uuid')

// Functions
function charge(req) {
  const span = tracer.startSpan('charge')

  const { creditCardNumber: number,
    creditCardExpirationYear: year,
    creditCardExpirationMonth: month
  } = req.creditCard
  const { units, nanos, currencyCode } = req.amount
  const currentMonth = new Date().getMonth() + 1
  const currentYear = new Date().getFullYear()
  const lastFourDigits = number.substr(-4)

  const card = cardValidator(number)
  const {card_type: cardType, valid } = card.getCardDetails()

  span.setAttributes({
    'app.payment.charge.cardType': cardType,
    'app.payment.charge.valid': valid
  })

  if (!valid)
    throw new Error('Credit card info is invalid.')

  if (!['visa', 'mastercard'].includes(cardType))
    throw new Error(`Sorry, we cannot process ${cardType} credit cards. Only VISA or MasterCard is accepted.`)

  if ((currentYear * 12 + currentMonth) > (year * 12 + month))
    throw new Error(`The credit card (ending ${lastFourDigits}) expired on ${month}/${year}.`)

  span.setAttribute('app.payment.charged', true)
  span.end()

  logger.info(`Transaction processed: ${cardType} ending ${lastFourDigits} | Amount: ${units}.${nanos} ${currencyCode}`)

  return { transactionId: uuidv4() }
}

function chargeHandler(call, callback) {
  const span = opentelemetry.trace.getSpan(opentelemetry.context.active())

  try {
    const amount = call.request.amount
    // TODO is it snake case here?
    console.log(amount)
    span.setAttributes({
      'app.payment.currency': amount.currency_code,
      'app.payment.cost': parseFloat(`${amount.units}.${amount.nanos}`)
    })
    logger.info(`PaymentService#Charge invoked by: ${JSON.stringify(call.request)}`)

    const res = charge(call.request)
    logger.info(`PaymentService#Charge transaction completed with id: ${res.transactionId}`)
    callback(null, res)

  } catch (err) {
    // TODO: these are not actually errors, just invalid credit cards
    logger.warn(err)

    span.recordException(err)
    span.setStatus({ code: opentelemetry.SpanStatusCode.ERROR })

    callback(err)
  }
}

async function closeGracefully(signal) {
  server.forceShutdown()
  process.kill(process.pid, signal)
}

// Main
const logger = pino()
const tracer = opentelemetry.trace.getTracer('paymentservice')
const hipsterShopPackage = grpc.loadPackageDefinition(protoLoader.loadSync('demo.proto'))
const server = new grpc.Server()

server.addService(health.service, new health.Implementation({
  '': proto.grpc.health.v1.HealthCheckResponse.ServingStatus.SERVING
}))

server.addService(hipsterShopPackage.hipstershop.PaymentService.service, { charge: chargeHandler })

server.bindAsync(`0.0.0.0:${process.env.PAYMENT_SERVICE_PORT}`, grpc.ServerCredentials.createInsecure(), (err, port) => {
    logger.info(`PaymentService gRPC server started on port ${port}`)
    server.start()
  }
)

process.once('SIGINT', closeGracefully)
process.once('SIGTERM', closeGracefully)
