// Node
const { promisify } = require('util')

// Npm
const test = require('ava')
const dotenv = require('dotenv')
const grpc = require('@grpc/grpc-js')
const protoLoader = require('@grpc/proto-loader')

// Local
const data = require('./data.json')

// Functions
const deepCopy = obj => JSON.parse(JSON.stringify(obj))

const arrayIntersection = (a, b) => a.filter(x => b.indexOf(x) !== -1)

const isEmpty = obj => Object.keys(obj).length === 0

// Main
let cartAdd = null, cartGet = null, cartEmpty = null
let charge = null
let recommend = null

test.before(() => {
  dotenv.config({ path: '../.env' })

  const hipstershop = grpc.loadPackageDefinition(protoLoader.loadSync('../pb/demo.proto')).hipstershop

  const cartClient = new hipstershop.CartService(`0.0.0.0:${process.env.CART_SERVICE_PORT}`, grpc.credentials.createInsecure())
  cartAdd = promisify(cartClient.addItem).bind(cartClient)
  cartGet = promisify(cartClient.getCart).bind(cartClient)
  cartEmpty = promisify(cartClient.emptyCart).bind(cartClient)

  const paymentClient = new hipstershop.PaymentService(`0.0.0.0:${process.env.PAYMENT_SERVICE_PORT}`, grpc.credentials.createInsecure())
  charge = promisify(paymentClient.charge).bind(paymentClient)

  const recommendationClient = new hipstershop.RecommendationService(`0.0.0.0:${process.env.RECOMMENDATION_SERVICE_PORT}`, grpc.credentials.createInsecure())
  recommend = promisify(recommendationClient.listRecommendations).bind(recommendationClient)
})

// --------------- Cart Service ---------------

test('cart: all', async t => {
  const request = data.cart
  const userIdRequest = { userId: request.userId }

  // Empty Cart
  const emptyRes1 = await cartEmpty(userIdRequest)
  t.truthy(isEmpty(emptyRes1))

  // Add to Cart
  const addRes = await cartAdd(request)
  t.truthy(isEmpty(addRes))

  // Check Cart Content
  const getRes1 = await cartGet(userIdRequest)
  t.is(getRes1.items.length, 1)
  t.is(getRes1.items[0].productId, request.item.productId)
  t.is(getRes1.items[0].quantity, request.item.quantity)

  // Empty Cart
  const emptyRes2 = await cartEmpty(userIdRequest)
  t.truthy(isEmpty(emptyRes2))

  // Check Cart Content
  const getRes2 = await cartGet(userIdRequest)
  t.truthy(isEmpty(getRes2))
})

// --------------- Payment Service ---------------

test('payment: valid credit card', t => {
  const request = data.charge

  return charge(request).then(res => {
    t.truthy(res.transactionId)
  })
})

test('payment: invalid credit card', t => {
  const request = deepCopy(data.charge)
  request.creditCard.creditCardNumber = '0000-0000-0000-0000'

  return charge(request).catch(err => {
    t.is(err.details, 'Credit card info is invalid.')
  })
})

test('payment: amex credit card not allowed', t => {
  const request = deepCopy(data.charge)
  request.creditCard.creditCardNumber = '3714 496353 98431'

  return charge(request).catch(err => {
    t.is(err.details, 'Sorry, we cannot process amex credit cards. Only VISA or MasterCard is accepted.')
  })
})

test('payment: expired credit card', t => {
  const request = deepCopy(data.charge)
  request.creditCard.creditCardExpirationYear = 2021

  return charge(request).catch(err => {
    t.is(err.details, 'The credit card (ending 0454) expired on 1/2021.')
  })
})

// --------------- Recommendation Service ---------------

test('recommendation: list products', t => {
  const request = deepCopy(data.recommend)

  return recommend(request).then(res => {
    t.is(res.productIds.length, 4)
    t.is(arrayIntersection(res.productIds, request.productIds).length, 0)
  })
})
