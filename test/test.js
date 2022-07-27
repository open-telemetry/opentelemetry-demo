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
let productList = null, productGet = null, productSearch = null
let shippingQuote = null, shippingOrder = null

test.before(() => {
  dotenv.config({ path: '../.env' })

  const hipstershop = grpc.loadPackageDefinition(protoLoader.loadSync('../pb/demo.proto')).hipstershop

  const cartClient = new hipstershop.CartService(`0.0.0.0:${process.env.CART_SERVICE_PORT}`, grpc.credentials.createInsecure())
  cartAdd = promisify(cartClient.addItem).bind(cartClient)
  cartGet = promisify(cartClient.getCart).bind(cartClient)
  cartEmpty = promisify(cartClient.emptyCart).bind(cartClient)

  const paymentClient = new hipstershop.PaymentService(`0.0.0.0:${process.env.PAYMENT_SERVICE_PORT}`, grpc.credentials.createInsecure())
  charge = promisify(paymentClient.charge).bind(paymentClient)

  const productCatalogClient = new hipstershop.ProductCatalogService(`0.0.0.0:${process.env.PRODUCT_CATALOG_SERVICE_PORT}`, grpc.credentials.createInsecure())
  productList = promisify(productCatalogClient.listProducts).bind(productCatalogClient)
  productGet = promisify(productCatalogClient.getProduct).bind(productCatalogClient)
  productSearch = promisify(productCatalogClient.searchProducts).bind(productCatalogClient)

  const recommendationClient = new hipstershop.RecommendationService(`0.0.0.0:${process.env.RECOMMENDATION_SERVICE_PORT}`, grpc.credentials.createInsecure())
  recommend = promisify(recommendationClient.listRecommendations).bind(recommendationClient)

  const shippingClient = new hipstershop.ShippingService(`0.0.0.0:${process.env.SHIPPING_SERVICE_PORT}`, grpc.credentials.createInsecure())
  shippingQuote = promisify(shippingClient.getQuote).bind(shippingClient)
  shippingOrder = promisify(shippingClient.shipOrder).bind(shippingClient)
})

// --------------- Cart Service ---------------

test('cart: all', async t => {
  const request = data.cart
  const userIdRequest = { userId: request.userId }

  // Empty Cart
  let res = await cartEmpty(userIdRequest)
  t.truthy(isEmpty(res))

  // Add to Cart
  res = await cartAdd(request)
  t.truthy(isEmpty(res))

  // Check Cart Content
  res = await cartGet(userIdRequest)
  t.is(res.items.length, 1)
  t.is(res.items[0].productId, request.item.productId)
  t.is(res.items[0].quantity, request.item.quantity)

  // Empty Cart
  res = await cartEmpty(userIdRequest)
  t.truthy(isEmpty(res))

  // Check Cart Content
  res = await cartGet(userIdRequest)
  t.truthy(isEmpty(res))
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

// --------------- Product Catalog Service ---------------

test('product: list', async t => {
  const res = await productList({})
  t.is(res.products.length, 9)
})

test('product: get', async t => {
  const res = await productGet({ id: 'OLJCESPC7Z' })
  t.is(res.name, 'Sunglasses')
  t.truthy(res.description)
  t.truthy(res.picture)
  t.truthy(res.priceUsd)
  t.truthy(res.categories)
})

test('product: search', async t => {
  const res = await productSearch({ query: 'hold' })
  t.is(res.results.length, 2)
  t.is(res.results[0].name, 'Candle Holder')
  t.is(res.results[1].name, 'Bamboo Glass Jar')
})

// --------------- Recommendation Service ---------------

test('recommendation: list products', t => {
  const request = deepCopy(data.recommend)

  return recommend(request).then(res => {
    t.is(res.productIds.length, 4)
    t.is(arrayIntersection(res.productIds, request.productIds).length, 0)
  })
})

// --------------- Shipping Service ---------------

test('shipping: quote', async t => {
  const request = data.shipping

  const res = await shippingQuote(request)
  t.is(res.costUsd.units, 17)
  t.is(res.costUsd.nanos, 980000000)
})

test('shipping: empty quote', async t => {
  const request = deepCopy(data.shipping)
  request.items = []

  const res = await shippingQuote(request)
  t.falsy(res.costUsd.units)
  t.falsy(res.costUsd.nanos)
})

test('shipping: order', async t => {
  const request = data.shipping

  const res = await shippingOrder(request)
  t.truthy(res.trackingId)
})
