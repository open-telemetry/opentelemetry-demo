// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0

import http from 'k6/http'
import { sleep } from 'k6'
import { browser } from 'k6/browser'
import { Tracer } from 'k6/x/otel'

const BASE_URL = __ENV.K6_TARGET_URL || 'http://frontend-proxy:8080'
const FLAGD_HOST = __ENV.FLAGD_HOST || 'flagd'
const FLAGD_OFREP_PORT = __ENV.FLAGD_OFREP_PORT || '8016'

// The HTTP scenario's VU count is read from LOAD_GENERATOR_VUS rather than
// k6's own K6_VUS, since a K6_VUS env var makes k6 discard this script's
// scenarios config entirely in favor of an implicit single scenario (see
// README.md). The browser scenario runs a single headless browser session
// alongside the HTTP traffic; it stays opt-in via K6_BROWSER_ENABLED.
const browserEnabled = (__ENV.K6_BROWSER_ENABLED || '').toLowerCase() === 'true'

export const options = {
    scenarios: {
        load: {
            executor: 'constant-vus',
            exec: 'httpScenario',
            vus: parseInt(__ENV.LOAD_GENERATOR_VUS || '10'),
            duration: __ENV.K6_DURATION || '9999h',
        },
        ...(browserEnabled ? {
            browser: {
                executor: 'constant-vus',
                exec: 'browserScenario',
                vus: 1,
                duration: __ENV.K6_DURATION || '9999h',
                options: {
                    browser: {
                        type: 'chromium',
                        headless: true,
                        // executablePath/args come from env vars, not this field - see README.md.
                    },
                },
            },
        } : {}),
    },
}

const products = [
    '0PUK6V6EV0', '1YMWWN1N4O', '2ZYFJ3GM2N', '66VCHSJNUP', '6E92ZMYYFZ',
    '9SIQT8TOJO', 'L9ECAV7KIM', 'LS4PSXUNUM', 'OLJCESPC7Z', 'HQTGWGPNH4',
]

const categories = ['binoculars', 'telescopes', 'accessories', 'assembly', 'travel', 'books', null]

const people = JSON.parse(open('./people.json'))

const tracer = new Tracer()

// ---- helpers ----------------------------------------------------------------

// Uses a Uint8Array rather than Uint32Array(1): k6's crypto.getRandomValues
// only randomizes `buf.length` bytes, not `buf.byteLength`, so a Uint32Array(1)
// gets just 1 random byte with the upper 3 left as zero.
function cryptoRandom() {
    const buf = new Uint8Array(4)
    crypto.getRandomValues(buf)
    const val = ((buf[0] << 24) | (buf[1] << 16) | (buf[2] << 8) | buf[3]) >>> 0
    return val / 0x100000000
}

function randomChoice(arr) {
    return arr[Math.floor(cryptoRandom() * arr.length)]
}

function uuid4() {
    return crypto.randomUUID()
}

// getFlagdValue mirrors Locust's TracingHook: each flag evaluation gets its
// own OTel span so flag-driven behaviour is visible in traces.
function getFlagdValue(flagName) {
    const span = tracer.startSpan('feature_flag.evaluate', { 'feature_flag.key': flagName })
    const res = http.post(
        `http://${FLAGD_HOST}:${FLAGD_OFREP_PORT}/ofrep/v1/evaluate/flags/${flagName}`,
        JSON.stringify({}),
        { headers: otelHeaders(span.traceParent(), { 'Content-Type': 'application/json' }), tags: { flagd: 'true' } }
    )
    let value = 0
    if (res.status === 200) {
        value = JSON.parse(res.body).value || 0
    }
    span.log(`Feature flag ${flagName} evaluated to ${value}`)
    span.end()
    return value
}

// Merges OTel headers (baggage + traceparent) with any extra headers provided.
function otelHeaders(traceParent, extra) {
    return Object.assign(
        {
            baggage: `synthetic_request=true,session.id=${sessionId}`,
            traceparent: traceParent,
        },
        extra
    )
}

// ---- per-VU session state ---------------------------------------------------

let sessionId = null

function onStart() {
    sessionId = uuid4()
    const span = tracer.startSpan('user_session_start')
    span.log(`Starting user session: ${sessionId}`)
    http.get(`${BASE_URL}/`, { headers: otelHeaders(span.traceParent()) })
    span.end()
}

// ---- tasks ------------------------------------------------------------------

function index() {
    const span = tracer.startSpan('user_index')
    span.log('User accessing index page')
    http.get(`${BASE_URL}/`, { headers: otelHeaders(span.traceParent()) })
    span.end()
}

function browseProduct() {
    const product = randomChoice(products)
    const span = tracer.startSpan('user_browse_product', { 'product.id': product })
    span.log(`User browsing product: ${product}`)
    http.get(`${BASE_URL}/api/products/${product}`, { headers: otelHeaders(span.traceParent()) })
    span.end()
}

function getRecommendations() {
    const product = randomChoice(products)
    const span = tracer.startSpan('user_get_recommendations', { 'product.id': product })
    span.log(`User getting recommendations for product: ${product}`)
    http.get(
        `${BASE_URL}/api/recommendations?productIds=${product}`,
        { headers: otelHeaders(span.traceParent()) }
    )
    span.end()
}

function getAds() {
    const category = randomChoice(categories)
    const span = tracer.startSpan('user_get_ads', { category: String(category) })
    span.log(`User getting ads for category: ${category}`)
    // When category is null, Locust sends contextKeys=None (Python str(None)).
    const url = category !== null
        ? `${BASE_URL}/api/data/?contextKeys=${category}`
        : `${BASE_URL}/api/data/?contextKeys=None`
    http.get(url, { headers: otelHeaders(span.traceParent()) })
    span.end()
}

function viewCart() {
    const span = tracer.startSpan('user_view_cart')
    span.log('User viewing cart')
    http.get(`${BASE_URL}/api/cart`, { headers: otelHeaders(span.traceParent()) })
    span.end()
}

function addToCart(user) {
    if (!user) user = uuid4()
    const product = randomChoice(products)
    const quantity = randomChoice([1, 2, 3, 4, 5, 10])
    const span = tracer.startSpan(
        'user_add_to_cart',
        { 'user.id': user, 'product.id': product, quantity }
    )
    span.log(`User ${user} adding ${quantity} of product ${product} to cart`)
    const h = otelHeaders(span.traceParent())
    http.get(`${BASE_URL}/api/products/${product}`, { headers: h })
    http.post(
        `${BASE_URL}/api/cart`,
        JSON.stringify({ item: { productId: product, quantity }, userId: user }),
        { headers: otelHeaders(span.traceParent(), { 'Content-Type': 'application/json' }) }
    )
    span.end()
}

function checkout() {
    const user = uuid4()
    const span = tracer.startSpan('user_checkout_single', { 'user.id': user })
    span.log(`Starting checkout for user ${user}`)

    addToCart(user)

    http.post(
        `${BASE_URL}/api/checkout`,
        JSON.stringify(Object.assign({}, randomChoice(people), { userId: user })),
        { headers: otelHeaders(span.traceParent(), { 'Content-Type': 'application/json' }) }
    )
    span.log(`Checkout completed for user ${user}`)
    span.end()
}

function checkoutMulti() {
    const user = uuid4()
    const itemCount = randomChoice([2, 3, 4])
    const span = tracer.startSpan('user_checkout_multi', { 'user.id': user, 'item.count': itemCount })
    span.log(`Starting multi-item checkout for user ${user}, ${itemCount} items`)

    for (let i = 0; i < itemCount; i++) {
        addToCart(user)
    }

    http.post(
        `${BASE_URL}/api/checkout`,
        JSON.stringify(Object.assign({}, randomChoice(people), { userId: user })),
        { headers: otelHeaders(span.traceParent(), { 'Content-Type': 'application/json' }) }
    )
    span.log(`Multi-item checkout completed for user ${user}`)
    span.end()
}

function floodHome() {
    const floodCount = getFlagdValue('loadGeneratorFloodHomepage')
    if (floodCount <= 0) return

    const span = tracer.startSpan('user_flood_home', { 'flood.count': floodCount })
    span.log(`User flooding homepage ${floodCount} times`)
    const h = otelHeaders(span.traceParent())
    for (let i = 0; i < floodCount; i++) {
        http.get(`${BASE_URL}/`, { headers: h })
    }
    span.end()
}

// ---- weighted task selection ------------------------------------------------
// Task weights: index(1) browse(10) recs(3) ads(3) cart(3) add(2)
// checkout(1) checkout_multi(1) flood(5) = 29

const weightedTasks = [
    { cumWeight:  1, task: index },
    { cumWeight: 11, task: browseProduct },
    { cumWeight: 14, task: getRecommendations },
    { cumWeight: 17, task: getAds },
    { cumWeight: 20, task: viewCart },
    { cumWeight: 22, task: addToCart },
    { cumWeight: 23, task: checkout },
    { cumWeight: 24, task: checkoutMulti },
    { cumWeight: 29, task: floodHome },
]

function selectTask() {
    const r = cryptoRandom() * 29
    for (const { cumWeight, task } of weightedTasks) {
        if (r < cumWeight) return task
    }
    return weightedTasks[weightedTasks.length - 1].task
}

// ---- HTTP entrypoint --------------------------------------------------------

export function httpScenario() {
    if (getFlagdValue('loadGeneratorTraffic') <= 0) {
        sleep(cryptoRandom() * 9 + 1)
        return
    }

    if (sessionId === null) {
        onStart()
    }

    selectTask()()

    sleep(cryptoRandom() * 9 + 1)  // mirrors Locust between(1, 10)
}

// ---- browser tasks ----------------------------------------------------------

async function changeCurrency(page) {
    await page.goto(`${BASE_URL}/cart`, { waitUntil: 'domcontentloaded' })
    await page.selectOption('[name="currency_code"]', 'CHF')
    await page.waitForTimeout(2000)
}

async function addProductToCartBrowser(page) {
    // Roof Binoculars (2ZYFJ3GM2N). Selects by href / data-cy rather than
    // :has-text(), which k6 browser's native CSS engine does not support
    // (it forwards selectors straight to document.querySelectorAll, unlike
    // Playwright's own selector engine).
    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' })
    await page.waitForSelector('a[href="/product/2ZYFJ3GM2N"]', { timeout: 15000 })
    await page.click('a[href="/product/2ZYFJ3GM2N"]')
    await page.waitForLoadState('domcontentloaded')
    await page.click('[data-cy="product-add-to-cart"]')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(2000)
}

// ---- browser entrypoint -----------------------------------------------------

export async function browserScenario() {
    if (getFlagdValue('loadGeneratorTraffic') <= 0) {
        sleep(cryptoRandom() * 9 + 1)
        return
    }

    const page = await browser.newPage()
    const isCurrencyChange = cryptoRandom() < 0.5
    const span = tracer.startSpan(isCurrencyChange ? 'browser_change_currency' : 'browser_add_to_cart')
    try {
        await page.setExtraHTTPHeaders({ baggage: 'synthetic_request=true' })
        if (isCurrencyChange) {
            span.log('Currency changed to CHF')
            await changeCurrency(page)
        } else {
            span.log('Product added to cart successfully')
            await addProductToCartBrowser(page)
        }
    } catch (e) {
        console.error(`browser task error: ${e}`)
    } finally {
        span.end()
        await page.close()
    }

    sleep(cryptoRandom() * 9 + 1)
}
