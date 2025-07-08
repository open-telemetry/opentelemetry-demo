#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


import json
import os
import random
import uuid
from locust import HttpUser, task, between
from locust_plugins.users.playwright import PlaywrightUser, pw, PageWithRetry, event

from opentelemetry import context, baggage, trace
from opentelemetry.metrics import set_meter_provider
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricExporter, PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.jinja2 import Jinja2Instrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.system_metrics import SystemMetricsInstrumentor
from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor
from playwright.async_api import Route, Request

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


class WebsiteUser(HttpUser):
    wait_time = between(1, 10)

    @task(1)
    def index(self):
        self.client.get("/")

    @task(10)
    def browse_product(self):
        self.client.get("/api/products/" + random.choice(products))

    @task(3)
    def get_recommendations(self):
        params = {
            "productIds": [random.choice(products)],
        }
        self.client.get("/api/recommendations", params=params)

    @task(3)
    def get_ads(self):
        params = {
            "contextKeys": [random.choice(categories)],
        }
        self.client.get("/api/data/", params=params)

    @task(3)
    def view_cart(self):
        self.client.get("/api/cart")

    @task(2)
    def add_to_cart(self, user=""):
        if user == "":
            user = str(uuid.uuid1())
        product = random.choice(products)
        self.client.get("/api/products/" + product)
        cart_item = {
            "item": {
                "productId": product,
                "quantity": random.choice([1, 2, 3, 4, 5, 10]),
            },
            "userId": user,
        }
        self.client.post("/api/cart", json=cart_item)

    @task(1)
    def checkout(self):
        # checkout call with an item added to cart
        user = str(uuid.uuid1())
        self.add_to_cart(user=user)
        checkout_person = random.choice(people)
        checkout_person["userId"] = user
        self.client.post("/api/checkout", json=checkout_person)

    @task(1)
    def checkout_multi(self):
        # checkout call which adds 2-4 different items to cart before checkout
        user = str(uuid.uuid1())
        for i in range(random.choice([2, 3, 4])):
            self.add_to_cart(user=user)
        checkout_person = random.choice(people)
        checkout_person["userId"] = user
        self.client.post("/api/checkout", json=checkout_person)

    def on_start(self):
        ctx = baggage.set_baggage("synthetic_request", "true")
        context.attach(ctx)
        self.index()


browser_traffic_enabled = os.environ.get("LOCUST_BROWSER_TRAFFIC_ENABLED", "").lower() in ("true", "yes", "on")

if browser_traffic_enabled:
    class WebsiteBrowserUser(PlaywrightUser):
        headless = True  # to use a headless browser, without a GUI

        @task
        @pw
        async def open_cart_page_and_change_currency(self, page: PageWithRetry):
            try:
                page.on("console", lambda msg: print(msg.text))
                await page.route('**/*', add_baggage_header)
                await page.goto("/cart", wait_until="domcontentloaded")
                await page.select_option('[name="currency_code"]', 'CHF')
                await page.wait_for_timeout(2000)  # giving the browser time to export the traces
            except:
                pass

        @task
        @pw
        async def add_product_to_cart(self, page: PageWithRetry):
            try:
                page.on("console", lambda msg: print(msg.text))
                await page.route('**/*', add_baggage_header)
                await page.goto("/", wait_until="domcontentloaded")
                await page.click('p:has-text("Roof Binoculars")')
                await page.click('button:has-text("Add To Cart")')
                await page.wait_for_timeout(2000)  # giving the browser time to export the traces
            except:
                pass

        @task
        @pw
        async def browse_shop(self, page: PageWithRetry):
            try:
                page.on("console", lambda msg: print(msg.text))
                await page.route('**/*', add_baggage_header)

                async with event(self, 'View shop'):
                    await page.goto("/", wait_until="domcontentloaded")
                    await page.wait_for_timeout(random.randint(2000, 15000))  # emulating user
                async with event(self, 'Browse products'):
                    await page.click(":nth-match([data-cy=product-card], " + str(random.randint(1, 4)) + ")")
                    await page.wait_for_timeout(random.randint(2000, 15000))
                    await page.click(":nth-match([data-cy=product-card], " + str(random.randint(1, 4)) + ")")
                    await page.wait_for_timeout(random.randint(2000, 15000))
                    await page.click(":nth-match([data-cy=product-card], " + str(random.randint(1, 4)) + ")")
                    await page.wait_for_timeout(random.randint(2000, 15000))

                if (random.randint(0, 12) == 0): # Change currency with a chance of 1:12
                    await page.select_option('[name="currency_code"]', 'CHF')

                async with event(self, 'Choose product'):
                    await page.goto("/", wait_until="domcontentloaded")
                    await page.wait_for_timeout(random.randint(2000, 15000))
                    await page.click('p:has-text("Roof Binoculars")')
                    await page.wait_for_timeout(random.randint(2000, 15000))
                    await page.click('button:has-text("Add To Cart")')
                    await page.wait_for_timeout(random.randint(2000, 15000))
                async with event(self, 'View cart'):
                    await page.goto("/cart", wait_until="domcontentloaded")
                    await page.wait_for_timeout(random.randint(2000, 15000))  # giving the browser time to export the traces

                if (random.randint(0, 8) == 0): # directly open unknown product page with a chance of 1:8
                    await page.goto("/product/ZFYYMZ29E6", wait_until="domcontentloaded")

                if (random.randint(0, 5) == 0): # checkout with a chance of 1:5
                    await page.click('a[data-cy="cart-icon"]')
                    await page.click('button:has-text("Go to Shopping Cart")')
                    await page.wait_for_timeout(random.randint(2000, 15000))
                    await page.click('button:has-text("Place Order")')
            except:
                raise


async def add_baggage_header(route: Route, request: Request):
    headers = {
        **request.headers,
        'baggage': 'synthetic_request=true'
    }
    await route.continue_(headers=headers)
