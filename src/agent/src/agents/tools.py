import os

import requests

BASE_URL = os.getenv("APPLICATION_ENDPOINT", "localhost:8080")


def get_ads(category: str):
    """Fetch promotional ads for Astronomy Shop homepage."""
    url = f"http://{BASE_URL}/api/data"
    params = {"contextKeys": category}
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return f"Error fetching ads: {e}"


def add_to_cart(userId: str, productId: str, quantity: int = 1):
    """Add a product (productId) to the shopping cart for a user (userId)."""
    url = f"http://{BASE_URL}/api/cart"
    data = {
        "item": {
            "productId": productId,
            "quantity": quantity,
        },
        "userId": userId,
    }
    try:
        res = requests.post(url, json=data)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return f"Error while adding product to cart: {e}"


def get_cart():
    """Retrieve the current contents of a user's cart."""
    url = f"http://{BASE_URL}/api/cart"
    try:
        res = requests.get(url)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return f"Error while fetching cart: {e}"


def empty_cart(uuid: str):
    """Empty the shopping cart for a user."""
    url = f"http://{BASE_URL}/api/cart/empty/{uuid}"
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
    """Checkout the user's cart and create an order."""
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


def convert_currency(from_currency: str, to_currency: str, amount: float):
    """Convert between currencies."""
    url = f"http://{BASE_URL}/api/currency/convert?from={from_currency}&to={to_currency}&amount={amount}"
    try:
        res = requests.get(url)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return f"Error converting currency: {e}"


def get_recommendations(productId: str):
    """Get product recommendations for a user."""
    url = f"http://{BASE_URL}/api/recommendations"
    params = {"productIds": productId}
    try:
        res = requests.get(url, params=params)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return f"Error fetching recommendations: {e}"


def get_shipping_quote(address_id: str):
    """Get estimated shipping cost for a given address."""
    url = f"http://{BASE_URL}/api/shipping/quote/{address_id}"
    try:
        res = requests.get(url)
        res.raise_for_status()
        return res.json()
    except Exception as e:
        return f"Error fetching shipping quote: {e}"
