# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import json
import os
import time
import urllib.error
import urllib.request
import uuid


FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://frontend:8080")
CHECKOUT_COUNT = int(os.environ.get("CHECKOUT_COUNT", "2"))

PRODUCTS = ["0PUK6V6EV0", "1YMWWN1N4O", "2ZYFJ3GM2N"]

PERSON = {
    "email": "telemetry-test@example.com",
    "address": {
        "streetAddress": "1600 Amphitheatre Parkway",
        "zipCode": "94043",
        "city": "Mountain View",
        "state": "CA",
        "country": "United States",
    },
    "userCurrency": "USD",
    "creditCard": {
        "creditCardNumber": "4432-8015-6152-0454",
        "creditCardExpirationMonth": 1,
        "creditCardExpirationYear": 2039,
        "creditCardCvv": 672,
    },
}


def post_json(path, payload, timeout=30):
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{FRONTEND_URL}{path}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, response.read().decode("utf-8")


def checkout(index):
    user_id = str(uuid.uuid4())
    product_id = PRODUCTS[index % len(PRODUCTS)]
    post_json(
        "/api/cart",
        {"item": {"productId": product_id, "quantity": 1}, "userId": user_id},
        timeout=20,
    )
    payload = dict(PERSON, userId=user_id)
    return post_json("/api/checkout", payload, timeout=30)


def main():
    deadline = time.time() + 120
    completed = 0
    last_error = None
    while completed < CHECKOUT_COUNT and time.time() < deadline:
        try:
            status, response_body = checkout(completed)
            completed += 1
            print(f"checkout {completed}/{CHECKOUT_COUNT}: HTTP {status} {response_body[:120]}")
        except (urllib.error.URLError, TimeoutError) as exc:
            last_error = exc
            print(f"checkout attempt failed: {exc}")
            time.sleep(5)
    if completed < CHECKOUT_COUNT:
        raise SystemExit(
            f"completed only {completed}/{CHECKOUT_COUNT} checkout(s); last error: {last_error}"
        )


if __name__ == "__main__":
    main()
