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

// Error Classes
class CreditCardError extends Error {
  constructor (message) {
    super(message)
    this.code = 400
  }
}

class InvalidCreditCard extends CreditCardError {
  constructor () {
    super(`Credit card info is invalid.`)
  }
}

class UnacceptedCreditCard extends CreditCardError {
  constructor (cardType) {
    super(`Sorry, we cannot process ${cardType} credit cards. Only VISA or MasterCard is accepted.`)
  }
}

class ExpiredCreditCard extends CreditCardError {
  constructor (lastFourDigits, month, year) {
    super(`The credit card (ending ${lastFourDigits}) expired on ${month}/${year}.`)
  }
}

// Functions
module.exports.charge = request => {
  const span = tracer.startSpan('charge')

  const { amount, credit_card: creditCard } = request
  const cardNumber = creditCard.credit_card_number
  const card = cardValidator(cardNumber)
  const {card_type: cardType, valid } = card.getCardDetails()
  span.setAttributes({
    'app.payment.charge.cardType': cardType,
    'app.payment.charge.valid': valid
  })

  if (!valid)
    throw new InvalidCreditCard()

  if (!['visa', 'mastercard'].includes(cardType))
    throw new UnacceptedCreditCard(cardType)

  const currentMonth = new Date().getMonth() + 1
  const currentYear = new Date().getFullYear()
  const { credit_card_expiration_year: year, credit_card_expiration_month: month } = creditCard
  const lastFourDigits = cardNumber.substr(-4)
  if ((currentYear * 12 + currentMonth) > (year * 12 + month))
    throw new ExpiredCreditCard(lastFourDigits, month, year)

  span.setAttribute('app.payment.charged', true)
  span.end()

  logger.info(`Transaction processed: ${cardType} ending ${lastFourDigits} | Amount: ${amount.currency_code}${amount.units}.${amount.nanos}`)

  return { transaction_id: uuidv4() }
}
