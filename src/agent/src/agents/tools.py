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
    url = f"http://{BASE_URL}/api/cart/empty/{user_id}"
    try:
        res = requests.get(url)
        res.raise_for_status()
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
        res.raise_for_status()
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
    Items is {string product_id, int32  quantity}
    CurrencyCode is currency identifier Eg: `USD`
    Address is {string streetAddress, string city, string state, string country, string zipCode}
    """
    url = f"http://{BASE_URL}/api/shipping"
    params = {"itemList": json.dumps(items), "currencyCode": currency_code, "address": json.dumps(address)}
    try:
        res = requests.get(url, params)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return f"Error fetching shipping quote: {e}"
