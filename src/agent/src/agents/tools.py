#!/usr/bin/python

# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import json
import os

import requests

BASE_URL = os.getenv("APPLICATION_ENDPOINT", "localhost:8080")


def get_ads(category: str):
    """Fetch promotional ads for Astronomy Shop homepage.
    Eg : category: `telescopes` or `travel`"""
    url = f"http://{BASE_URL}/api/data"
    params = {"contextKeys": category}
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return f"Error fetching ads: {e}"


def add_to_cart(user_id: str, product_id: str, quantity: int = 1):
    """Add a product (product_id) to the shopping cart for a user (user_id)."""
    url = f"http://{BASE_URL}/api/cart"
    data = {
        "item": {
            "productId": product_id,
            "quantity": quantity,
        },
        "userId": user_id,
    }
    try:
        res = requests.post(url, json=data)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return f"Error while adding product to cart: {e}"


def get_cart(user_id: str):
    """Retrieve the current contents of a user's cart."""
    url = f"http://{BASE_URL}/api/cart"
    try:
        res = requests.get(url, params={"user_id": user_id})
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return f"Error while fetching cart: {e}"


def empty_cart(user_id: str):
    """Empty the shopping cart for a user."""
    url = f"http://{BASE_URL}/api/cart"
    payload = {"userId": user_id}
    try:
        res = requests.delete(url, json=payload)
        res.raise_for_status()
        if res.status_code == 204 or not res.content:
            return {"status": "success", "message": f"Cart emptied for user {user_id}"}
        return res.json()
    except Exception as e:
        return f"Error while emptying cart: {e}"


def list_products():
    """List all products available in the Astronomy Shop."""
    url = f"http://{BASE_URL}/api/products"
    try:
        res = requests.get(url)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return f"Error while fetching product list: {e}"


def get_product(product_id: str):
    """Get detailed information about a product using its ID."""
    url = f"http://{BASE_URL}/api/products/{product_id}"
    try:
        res = requests.get(url)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return f"Error while fetching product {product_id}: {e}"


def checkout(checkout_person):
    """Checkout the user's cart and create an order.
    Takes request in the format {string user_id, string userCurrency, Address address, string email, CreditCardInfo creditCard}
    Where Address is {string streetAddress, string city, string state, string country, string zipCode} and
    CreditCardInfo is {string creditCardNumber, int32 creditCardCvv, int32 creditCardExpirationYear, int32 creditCardExpirationMonth}
    """
    url = f"http://{BASE_URL}/api/checkout"
    try:
        res = requests.post(url, json=checkout_person)
        # On failure, the frontend returns a plain-text body; surface it so the
        # caller sees the real reason (e.g. "cart is empty", downstream errors).
        if not res.ok:
            body = res.text.strip() or "<empty body>"
            user_id = checkout_person.get("userId", "<unknown>")
            return (
                f"Checkout failed with HTTP {res.status_code} for user "
                f"{user_id}: {body}. "
                "Note: the user's cart must contain at least one item before "
                "calling checkout; call add_to_cart first."
            )
        return res.json()
    except Exception as e:
        return f"Error while performing checkout: {e}"


def get_supported_currencies():
    """List supported currencies in Astronomy Shop."""
    url = f"http://{BASE_URL}/api/currency"
    try:
        res = requests.get(url)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return f"Error while fetching currency list: {e}"


def get_recommendations(product_id: str):
    """Get product recommendations for a user."""
    url = f"http://{BASE_URL}/api/recommendations"
    params = {"productIds": product_id}
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return f"Error fetching recommendations: {e}"


def get_shipping_quote(items, currency_code, address):
    """Get estimated shipping cost for a given address.
    `items`: list of {productId, quantity} (a single dict is also accepted).
    `currency_code`: ISO 4217 code, e.g. "USD".
    `address`: {streetAddress, city, state, country, zipCode}.
    """
    url = f"http://{BASE_URL}/api/shipping"

    if isinstance(items, dict):
        items = [items]

    normalised_items = []
    for it in items:
        if not isinstance(it, dict):
            return f"Error fetching shipping quote: invalid item {it!r}"
        product_id = it.get("productId") or it.get("product_id")
        quantity = it.get("quantity", 1)
        if not product_id:
            return "Error fetching shipping quote: each item must include productId"
        normalised_items.append({"productId": product_id, "quantity": quantity})

    params = {
        "itemList": json.dumps(normalised_items),
        "currencyCode": currency_code,
        "address": json.dumps(address),
    }
    try:
        res = requests.get(url, params=params)
        if not res.ok:
            body = res.text.strip() or "<empty body>"
            return (
                f"Shipping quote failed with HTTP {res.status_code}: {body}. "
            )
        return res.json()
    except Exception as e:
        return f"Error fetching shipping quote: {e}"
