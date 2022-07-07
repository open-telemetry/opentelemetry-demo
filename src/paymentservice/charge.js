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
const opentelemetry = require('@opentelemetry/api')
const cardValidator = require('simple-card-validator')
const pino = require('pino')
const { v4: uuidv4 } = require('uuid')

// Setup
const logger = pino()
const tracer = opentelemetry.trace.getTracer('paymentservice')

// Functions
module.exports.charge = request => {
  const span = tracer.startSpan('charge')

  const { amount, creditCard } = request
  const cardNumber = creditCard.creditCardNumber
  const card = cardValidator(cardNumber)
  const {card_type: cardType, valid } = card.getCardDetails()
  span.setAttributes({
    'app.payment.charge.cardType': cardType,
    'app.payment.charge.valid': valid
  })

  if (!valid)
    throw new Error('Credit card info is invalid.')

  if (!['visa', 'mastercard'].includes(cardType))
    throw new Error(`Sorry, we cannot process ${cardType} credit cards. Only VISA or MasterCard is accepted.`)

  const currentMonth = new Date().getMonth() + 1
  const currentYear = new Date().getFullYear()
  const { credit_card_expiration_year: year, credit_card_expiration_month: month } = creditCard
  const lastFourDigits = cardNumber.substr(-4)
  if ((currentYear * 12 + currentMonth) > (year * 12 + month))
    throw new Error(`The credit card (ending ${lastFourDigits}) expired on ${month}/${year}.`)

  span.setAttribute('app.payment.charged', true)
  span.end()

  logger.info(`Transaction processed: ${cardType} ending ${lastFourDigits} | Amount: ${amount.units}.${amount.nanos} ${amount.currencyCode}`)

  return { transaction_id: uuidv4() }
}
