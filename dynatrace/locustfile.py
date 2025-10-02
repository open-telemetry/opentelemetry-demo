#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


import json
import os
import random
import sys
import traceback
import uuid
import logging

from locust import HttpUser, task, between
from locust_plugins.users.playwright import PlaywrightUser, pw, PageWithRetry, event

from opentelemetry import context, baggage, trace
from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.jinja2 import Jinja2Instrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
from opentelemetry._logs import set_logger_provider
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
    OTLPLogExporter,
)
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource

from openfeature import api
from openfeature.contrib.provider.ofrep import OFREPProvider
from openfeature.contrib.hook.opentelemetry import TracingHook

from playwright.async_api import Route, Request

logger_provider = LoggerProvider(resource=Resource.create(
        {
            "service.name": "load-generator",
        }
    ),)
set_logger_provider(logger_provider)

exporter = OTLPLogExporter(insecure=True)
logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
handler = LoggingHandler(level=logging.INFO, logger_provider=logger_provider)

# Attach OTLP handler to locust logger
logging.getLogger().addHandler(handler)
logging.getLogger().setLevel(logging.INFO)

exporter = OTLPMetricExporter(insecure=True)
set_meter_provider(MeterProvider([PeriodicExportingMetricReader(exporter)]))

tracer_provider = TracerProvider()
trace.set_tracer_provider(tracer_provider)
tracer_provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

# Instrumenting manually to avoid error with locust gevent monkey
Jinja2Instrumentor().instrument()
RequestsInstrumentor().instrument()
SystemMetricsInstrumentor().instrument()
URLLib3Instrumentor().instrument()
logging.info("Instrumentation complete")

# Initialize Flagd provider
base_url = f"http://{os.environ.get('FLAGD_HOST', 'localhost')}:{os.environ.get('FLAGD_OFREP_PORT', 8016)}"
api.set_provider(OFREPProvider(base_url=base_url))
api.add_hooks([TracingHook()])

def get_flagd_value(FlagName):
    # Initialize OpenFeature
    client = api.get_client()
    return client.get_integer_value(FlagName, 0)

categories = [
    "binoculars",
    "telescopes",
    "accessories",
    "assembly",
    "travel",
    "books",
    None,
]

products = [
    "0PUK6V6EV0",
    "1YMWWN1N4O",
    "2ZYFJ3GM2N",
    "66VCHSJNUP",
    "6E92ZMYYFZ",
    "9SIQT8TOJO",
    "L9ECAV7KIM",
    "LS4PSXUNUM",
    "OLJCESPC7Z",
    "HQTGWGPNH4",
]

people_file = open('people.json')
people = json.load(people_file)

class WebsiteBrowserUser(PlaywrightUser):
    weight = 2
    headless = True  # to use a headless browser, without a GUI

    @task(1)
    @pw
    async def open_cart_page_and_change_currency(self, page: PageWithRetry):
        try:
            page.on("console", lambda msg: print(msg.text))
            await page.route('**/*', add_baggage_header)
            await page.goto("/", wait_until="domcontentloaded")

            # Open the Shopping cart flyout
            await page.click('a[data-cy="cart-icon"]')
            # Click the go to shopping cart button
            await page.click('button:has-text("Go to Shopping Cart")')

            # select a random user from the people.json file and checkout
            checkout_details = random.choice(people)
            await page.select_option('[name="currency_code"]', value=str(checkout_details['userCurrency']))

            await page.wait_for_timeout(2000)  # giving the browser time to export the traces
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            raise RescheduleTask(e)

    @task(1)
    @pw
    async def add_product_to_cart(self, page: PageWithRetry):
        try:
            page.on("console", lambda msg: print(msg.text))
            await page.route('**/*', add_baggage_header)
            await page.goto("/", wait_until="domcontentloaded")

            # Add 1-4 products to the cart
            for i in range(random.choice([1, 2, 3, 4])):
                # Get a random product link and click on it
                product_id = random.choice(products)
                await page.click(f"a[href='/product/{product_id}']")

                # Add a random number of products to the cart
                product_count = random.choice([1, 2, 3, 4, 5, 10])
                await page.select_option('select[data-cy="product-quantity"]', value=str(product_count))

                # add the product to our cart
                await page.click('button:has-text("Add To Cart")')

                # Continue Shopping
                await page.click('button:has-text("Continue Shopping")')

            # Open the Shopping cart flyout
            await page.click('a[data-cy="cart-icon"]')
            # Click the go to shopping cart button
            await page.click('button:has-text("Go to Shopping Cart")')

            await page.wait_for_timeout(8000)  # giving the browser time to export the traces
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            raise RescheduleTask(e)

    @task(3)
    @pw
    async def add_product_to_cart_and_checkout(self, page: PageWithRetry):
        try:
            page.on("console", lambda msg: print(msg.text))
            await page.route('**/*', add_baggage_header)
            await page.goto("/", wait_until="domcontentloaded")

            # Add 1-4 products to the cart
            for i in range(random.choice([1, 2, 3, 4])):
                # Get a random product link and click on it
                product_id = random.choice(products)
                await page.click(f"a[href='/product/{product_id}']")

                # Add a random number of products to the cart
                product_count = random.choice([1, 2, 3, 4, 5, 10])
                await page.select_option('select[data-cy="product-quantity"]', value=str(product_count))

                # add the product to our cart
                await page.click('button:has-text("Add To Cart")')

                # Continue Shopping
                await page.click('button:has-text("Continue Shopping")')

            # Open the Shopping cart flyout
            await page.click('a[data-cy="cart-icon"]')
            # Click the go to shopping cart button
            await page.click('button:has-text("Go to Shopping Cart")')

            # select a random user from the people.json file and checkout
            checkout_details = random.choice(people)
            await page.select_option('select[name="currency_code"]', value=str(checkout_details['userCurrency']))

            await page.locator('input#email').fill(checkout_details['email'])
            await page.locator('input#street_address').fill(checkout_details['address']['streetAddress'])
            await page.locator('input#zip_code').fill(str(checkout_details['address']['zipCode']))
            await page.locator('input#city').fill(checkout_details['address']['city'])
            await page.locator('input#state').fill(checkout_details['address']['state'])
            await page.locator('input#country').fill(checkout_details['address']['country'])
            await page.locator('input#credit_card_number').fill(str(checkout_details['creditCard']['creditCardNumber']))
            await page.select_option('select#credit_card_expiration_month', value=str(checkout_details['creditCard']['creditCardExpirationMonth']))
            await page.select_option('select#credit_card_expiration_year', value=str(checkout_details['creditCard']['creditCardExpirationYear']))
            await page.locator('input#credit_card_cvv').fill(str(checkout_details['creditCard']['creditCardCvv']))

            # Complete the order
            await page.click('button:has-text("Place Order")')
            await page.wait_for_timeout(8000)  # giving the browser time to export the traces
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            raise RescheduleTask(e)
        
    @task(1)
    @pw
    async def add_product_to_cart(self, page: PageWithRetry):
        try:
            page.on("console", lambda msg: print(msg.text))
            await page.route('**/*', add_baggage_header)
            await page.goto("/", wait_until="domcontentloaded")

            # Add 1-4 products to the cart
            for i in range(random.choice([1, 2, 3, 4])):
                # Get a random product link and click on it
                product_id = random.choice(products)
                await page.click(f"a[href='/product/{product_id}']")

                # Add a random number of products to the cart
                product_count = random.choice([1, 2, 3, 4, 5, 10])
                await page.select_option('select[data-cy="product-quantity"]', value=str(product_count))

                # add the product to our cart
                await page.click('button:has-text("Add To Cart")')

                # Continue Shopping
                await page.click('button:has-text("Continue Shopping")')

            # Open the Shopping cart flyout
            await page.click('a[data-cy="cart-icon"]')
            # Click the go to shopping cart button
            await page.click('button:has-text("Go to Shopping Cart")')

            await page.wait_for_timeout(8000)  # giving the browser time to export the traces
        except Exception as e:
            traceback.print_exc(file=sys.stdout)
            raise RescheduleTask(e)

        @task(3)
        @pw
        async def view_product_page_and_add_to_cart(self, page: PageWithRetry):
            """
            Navigates directly to the product UI page (/product/<id>) so Dynatrace can compute LCP/INP.
            Falls back to clicking from "/" if deep-linking fails. Keeps waits so RUM beacons flush.
            """
            try:
                page.on("console", lambda msg: print(msg.text))
                await page.route('**/*', add_baggage_header)

                # Pick a product you already use in API load
                product_id = random.choice(products)

                # --- Attempt 1: Deep-link directly to the UI route (Next.js dynamic route)
                # Upstream route file: src/frontend/pages/product/[productId]/index.tsx
                # URL shape confirmed as /product/<productId>
                resp = await page.goto(f"/product/{product_id}", wait_until="domcontentloaded")
                on_product = bool(resp and 200 <= resp.status <= 299)

                # --- Attempt 2: Click-through from "/" if deep-link didn't render the page
                if not on_product:
                    await page.goto("/", wait_until="domcontentloaded")
                    # Try a few selector patterns likely present in the catalog grid
                    for sel in [
                        f"a[href='/product/{product_id}']",
                        f"a[href^='/product/']",
                        f"[data-product-id='{product_id}']",
                        "[data-cy='product-card'], .product-card, a[href^='/product/']",
                    ]:
                        try:
                            loc = page.locator(sel).first
                            if await loc.count() > 0:
                                await loc.click()
                                break
                        except Exception:
                            pass

                    # Works for SPA route changes and full navigations
                    try:
                        await page.wait_for_url("**/product/**", timeout=8000)
                        on_product = True
                    except Exception:
                        on_product = False  # e.g., modal on "/"

                # --- Interact: set quantity (if available), Add to Cart (INP), then continue
                # Quantity selector used in many astroshop forks; tweak if your DOM differs
                try:
                    await page.select_option('select[data-cy="product-quantity"]',
                                            value=str(random.choice([1,2,3,4,5,10])))
                except Exception:
                    pass  # selector may not exist

                await page.click('button:has-text("Add To Cart")', timeout=4000)

                # Some UIs show a "Continue Shopping" button; handle both cases
                try:
                    await page.click('button:has-text("Continue Shopping")', timeout=8000)
                except Exception:
                    pass

                # Open cart and navigate to full cart page (optional but useful)
                try:
                    await page.click('a[data-cy="cart-icon"]', timeout=8000)
                    try:
                        with page.expect_navigation(timeout=8000):
                            await page.click('button:has-text("Go to Shopping Cart")', timeout=8000)
                    except Exception:
                        # SPA route change fallback
                        try:
                            await page.wait_for_url("**/cart**", timeout=8000)
                        except Exception:
                            pass
                except Exception:
                    pass

                # Allow time for RUM beacons (LCP/INP) to flush
                await page.wait_for_timeout(8000)

                # Optional: log final URL for debugging
                print("Final URL:", page.url, "on_product:", on_product)

            except Exception as e:
                traceback.print_exc(file=sys.stdout)
                # Reschedule to keep the user alive even if a selector fails intermittently
                raise RescheduleTask(e)        

        @task(2)
        @pw
        async def view_product_page(self, page: PageWithRetry):
            await page.route('**/*', add_baggage_header)
            product = random.choice([
                "0PUK6V6EV0","1YMWWN1N4O","2ZYFJ3GM2N","66VCHSJNUP"
            ])
            await page.goto(f"/product/{product}", wait_until="domcontentloaded")
            await page.wait_for_timeout(8000)            


async def add_baggage_header(route: Route, request: Request):
    existing_baggage = request.headers.get('baggage', '')
    headers = {
        **request.headers,
        'baggage': ', '.join(filter(None, (existing_baggage, 'synthetic_request=true')))
    }
    await route.continue_(headers=headers)
