# Standard library imports
import nerdgraph
import os
import sys
import time
from typing import Callable


def get_api_key() -> str:
    """Get the New Relic API key from the environment variable
    NEW_RELIC_API_KEY.

    Exit if not set.

    :return: The New Relic API key.
    :rtype: str
    """

    api_key = os.getenv('NEW_RELIC_API_KEY')
    if not api_key:
        print("Error: NEW_RELIC_API_KEY environment variable not set.")
        sys.exit(1)

    return api_key


def get_account_id() -> int:
    """Get the New Relic Account ID from the environment variable
    NEW_RELIC_ACCOUNT_ID.

    Exit if not set or not an integer.

    :raises ValueError: If the Account ID is not an integer.
    :return: The New Relic Account ID.
    :rtype: int
    """

    account_id = os.getenv('NEW_RELIC_ACCOUNT_ID')
    if not account_id:
        print("Error: NEW_RELIC_ACCOUNT_ID environment variable not set.")
        sys.exit(1)

    # This will raise a ValueError and exit the script if not an integer
    account_id = int(account_id)

    return account_id


def poll(
    api_key: str,
    account_id: int,
    fn: Callable[[str, int], bool],
) -> bool:
    """Poll a function until it returns True or a maximum number of retries is
    reached.

    :param api_key: The New Relic API key
    :type api_key: str
    :param account_id: The New Relic Account ID
    :type account_id: int
    :param fn: The function to poll, which takes the API key and account ID as
           arguments and returns a boolean
    :type fn: Callable[[str, int], bool]
    :return: True if the function returns True within the retry limit, False
             otherwise.
    :rtype: bool
    """

    retries = 15
    success = False

    for attempt in range(retries):
        print(
            f"Attempt {attempt + 1} of {retries} for check {fn.__name__}...",
        )
        if fn(api_key, account_id):
            success = True
            break

        if attempt + 1 == retries:
            break

        print(
            f"Did not find expected value for {fn.__name__}. Waiting 5 seconds before retrying...",
        )

        time.sleep(5)

    return success


def check_count(
    api_key: str,
    account_id: int,
    query: str,
    attrName: str = 'count',
    expected_condition: Callable[[int], bool] = lambda x: x > 0,
) -> bool:
    """Check if the value of the named attribute returned by the given NRQL
    query is a number that meets the expected condition.

    :param api_key: The New Relic API key
    :type api_key: str
    :param account_id: The New Relic Account ID
    :type account_id: int
    :param query: The NRQL query to run
    :type query: str
    :param attrName: The name of the attribute to check in the query result,
                     defaults to 'count'
    :type attrName: str
    :param expected_condition: A callable that takes the numeric value of the
                               named attribute as an argument and returns True
                               if the condition is met, defaults to checking if
                               the attribute value is > 0
    :type expected_condition: Callable[[int], bool]
    :raises GraphQLApiError: If running the NRQL query fails.
    :return: True if the count returned by the query is greater than zero, False
             otherwise.
    :rtype: bool
    """

    results = nerdgraph.run_nrql(
        api_key,
        [account_id],
        query,
    )

    # For the given query, we expect a single numeric result with a field with
    # the given attribute name.
    if len(results) != 1:
        return False

    count = results[0].get(attrName)
    if count is None:
        return False

    if not isinstance(count, int):
        return False

    return expected_condition(count)


def check_frontend_get(api_key: str, account_id: int) -> bool:
    """Check that we see `GET` spans from the `frontend` service in New Relic
    in the last minute.

    :param api_key: The New Relic API key
    :type api_key: str
    :param account_id: The New Relic Account ID
    :type account_id: int
    :return: True if we see `GET` spans from the `frontend` service in New
             Relic in the last minute, False otherwise.
    :rtype: bool
    """

    return check_count(
        api_key,
        account_id,
        """
FROM Span
SELECT count(*)
WHERE instrumentation.provider = 'opentelemetry' AND service.namespace = 'opentelemetry-demo' AND entity.name = 'frontend' AND name = 'GET'
SINCE 1 minute ago
""",
    )


def check_cart_add_item(api_key: str, account_id: int) -> bool:
    """Check that we see `POST /oteldemo.CartService/AddItem` spans from the
    `cart` service in New Relic in the last minute.

    :param api_key: The New Relic API key
    :type api_key: str
    :param account_id: The New Relic Account ID
    :type account_id: int
    :return: True if we see `POST /oteldemo.CartService/AddItem` spans from the
             `cart` service in New Relic in the last minute, False otherwise.
    :rtype: bool
    """

    return check_count(
        api_key,
        account_id,
        """
FROM Span
SELECT count(*)
WHERE instrumentation.provider = 'opentelemetry' AND service.namespace = 'opentelemetry-demo' AND entity.name = 'cart' AND name='POST /oteldemo.CartService/AddItem'
SINCE 1 minute ago
""",
    )


def check_product_catalog_get_product(api_key: str, account_id: int) -> bool:
    """Check that we see `oteldemo.ProductCatalogService/GetProduct` spans from
    the `product-catalog` service in New Relic in the last minute.

    :param api_key: The New Relic API key
    :type api_key: str
    :param account_id: The New Relic Account ID
    :type account_id: int
    :return: True if we see `oteldemo.ProductCatalogService/GetProduct` spans
             from the `product-catalog` service in New Relic in the last
             minute, False otherwise.
    :rtype: bool
    """

    return check_count(
        api_key,
        account_id,
        """
FROM Span
SELECT count(*)
WHERE instrumentation.provider = 'opentelemetry' AND service.namespace = 'opentelemetry-demo' AND entity.name = 'product-catalog' AND name='oteldemo.ProductCatalogService/GetProduct'
SINCE 1 minute ago
""",
    )


def check_user_checkout_multi(api_key: str, account_id: int) -> bool:
    """Check that we see 12 unique entity GUIDs for the latest
    `user_checkout_multi` trace in New Relic in the last minute.

    :param api_key: The New Relic API key
    :type api_key: str
    :param account_id: The New Relic Account ID
    :type account_id: int
    :return: True if we see 12 unique entity GUIDs for the latest
             `user_checkout_multi` trace in New Relic in the last minute, False
             otherwise.
    :rtype: bool
    """

    return check_count(
        api_key,
        account_id,
        """
FROM Span
SELECT uniqueCount(entity.guid)
WHERE trace.id = (
  SELECT latest(trace.id)
  FROM Span
  WHERE instrumentation.provider = 'opentelemetry' AND service.namespace = 'opentelemetry-demo' AND entity.name = 'load-generator' AND name = 'user_checkout_multi'
  SINCE 1 minute ago
)
""",
        'uniqueCount.entity.guid',
        lambda x: x == 12,
    )


def check_spans_from_multiple_services(api_key: str, account_id: int) -> bool:
    """Check that we see spans from at least 10 different opentelemetry-demo
    services in New Relic in the last minute.

    :param api_key: The New Relic API key
    :type api_key: str
    :param account_id: The New Relic Account ID
    :type account_id: int
    :return: True if we see spans from at least 10 different opentelemetry-demo
             services in New Relic in the last minute, False otherwise.
    :rtype: bool
    """

    results = nerdgraph.run_nrql(
        api_key,
        [account_id],
        """
FROM Span
SELECT count(*)
WHERE instrumentation.provider = 'opentelemetry' AND service.namespace = 'opentelemetry-demo'
FACET service.name
SINCE 1 minute ago
LIMIT MAX
""",
    )

    # For this query, we expect > 10 results, one per unique service name, each
    # with a count of at least 1.

    if len(results) < 10:
        return False

    for result in results:
        count = result.get('count')
        if count is None:
            return False

        if not isinstance(count, int):
            return False

        if count < 1:
            return False

    return True

# -----------------------------------------------------------------------------
# Main script logic
# -----------------------------------------------------------------------------

# Get API key and Account ID
api_key = get_api_key()
account_id = get_account_id()

# Look for frontend GET spans
success = poll(
    api_key,
    account_id,
    check_frontend_get,
)
assert success, "Did not find expected 'GET' spans from the frontend service in New Relic after multiple attempts."

# Look for cart add item spans
success = poll(
    api_key,
    account_id,
    check_cart_add_item,
)
assert success, "Did not find expected 'POST /oteldemo.CartService/AddItem ' spans from the cart service in New Relic after multiple attempts."

# Look for product catalog get product spans
success = poll(
    api_key,
    account_id,
    check_product_catalog_get_product,
)
assert success, "Did not find expected `oteldemo.ProductCatalogService/GetProduct` spans from the product-catalog service in New Relic after multiple attempts."

# Look for 12 unique entity GUIDs for the latest user_checkout_multi trace
success = poll(
    api_key,
    account_id,
    check_user_checkout_multi,
)
assert success, "Did not find expected GUIDs for 'user_checkout_multi' traces in New Relic after multiple attempts."

# Look for spans from at least 10 opentelemetry-demo services
success = poll(
    api_key,
    account_id,
    check_spans_from_multiple_services,
)
assert success, "Did not find expected spans for at least 10 opentelemetry-demo services in New Relic after multiple attempts."
