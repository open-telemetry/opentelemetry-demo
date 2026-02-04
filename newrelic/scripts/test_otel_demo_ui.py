# Standard library imports
import json
import sys
import time


# Third party imports
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement


def wait_for_element(
    driver: WebDriver,
    by: str,
    value: str,
    timeout: int=5,
) -> WebElement:
    """Wait until the FIRST element specified by the given locator is visible on
    the page or the specified timeout is reached.

    :param driver: The WebDriver instance
    :type driver: WebDriver
    :param by: The type of locator to use (e.g., By.ID, By.CSS_SELECTOR)
    :type by: str
    :param value: The locator value
    :type value: str
    :param timeout: The maximum time to wait for the element to be visible,
           defaults to 5 seconds
    :type timeout: int
    :raises selenium.common.exceptions.TimeoutException: If the element
            specified by the given locator is not visible before the specified
            timeout is reached.
    :return: The visible WebElement that was found.
    :rtype: WebElement
    """

    wait = WebDriverWait(driver, timeout=timeout)
    return wait.until(EC.visibility_of_element_located((by, value)))


def wait_for_elements(
    driver: WebDriver,
    by: str,
    value: str,
    timeout: int=5,
) -> list[WebElement]:
    """Wait until ALL the elements specified by the given locator are visible on
    the page or the specified timeout is reached.

    :param driver: The WebDriver instance
    :type driver: WebDriver
    :param by: The type of locator to use (e.g., By.ID, By.CSS_SELECTOR)
    :type by: str
    :param value: The locator value
    :type value: str
    :param timeout: The maximum time to wait for the elements to be visible,
           defaults to 5 seconds
    :type timeout: int
    :raises selenium.common.exceptions.TimeoutException: If the elements
            specified by the given locator are not visible before the specified
            timeout is reached.
    :return: The list of visible WebElements that were found.
    :rtype: list[WebElement]
    """

    wait = WebDriverWait(driver, timeout=timeout)
    return wait.until(EC.visibility_of_all_elements_located((by, value)))


def navigate(e: WebElement) -> None:
    """Navigate to a new page by clicking on the given WebElement.

    This function assumes that clicking on the given WebElement navigates to a
    new page. This function clicks on the element and then waits for a short
    period to allow the new page to settle.

    :param e: The WebElement to click on
    :type e: WebElement
    """

    # Click on the element
    e.click()

    # Give the page some time to settle
    time.sleep(2)


def add_product_to_cart(
    driver: WebDriver,
    product_index: int,
    product_name: str,
) -> None:
    """Simulate the add to cart flow for a given product.

    :param driver: The WebDriver instance
    :type driver: WebDriver
    :param product_index: The index of the product on the homepage
    :type product_index: int
    :param product_name: The name of the product
    :type product_name: str
    """

    # Verify homepage loads
    heading = wait_for_element(
        driver,
        By.XPATH,
        "//h1[contains(@class, 'Banner-')]",
    )
    assert isinstance(heading, WebElement)
    assert "telescopes" in heading.text

    # Locate product link
    product_link = wait_for_element(
        driver,
        By.XPATH,
        f"//a[contains(@class, 'ProductCard')][{product_index}]//p[contains(@class, 'ProductName')]",
    )
    assert isinstance(product_link, WebElement)
    assert product_name == product_link.text.strip()

    # Navigate to product details page
    navigate(product_link)

    # Verify product details page loads
    product_heading = wait_for_element(driver, By.TAG_NAME, "h5")
    assert isinstance(product_heading, WebElement)
    assert product_name == product_heading.text.strip()

    # Add product to cart
    button = wait_for_element(
        driver,
        By.XPATH,
        "//button[contains(@class, 'AddToCart')]",
    )
    assert isinstance(button, WebElement)

    # Navigate to shopping cart page
    navigate(button)

    # Verify shopping cart page loads
    heading = wait_for_element(
        driver,
        By.XPATH,
        "//h1[contains(@class, 'Cart-')]",
    )
    assert isinstance(heading, WebElement)
    assert "Shopping Cart" == heading.text.strip()


# -----------------------------------------------------------------------------
# Main script logic
# -----------------------------------------------------------------------------

# Initialize the Chrome WebDriver / launch the browser
driver = webdriver.Chrome()

# Give the browser some time to settle
time.sleep(5)

# ----------------------------------------------------------------------------
# Test Script for OpenTelemetry Demo Application
# ----------------------------------------------------------------------------

# Load the homepage
driver.get("http://localhost:8080")

# Give the page some time to settle
time.sleep(2)

# Add first product to cart
add_product_to_cart(driver, 1, "Solar System Color Imager")

# Click on the continue shopping button
button = wait_for_element(
    driver,
    By.XPATH,
    "//button[contains(text(), 'Continue Shopping')]",
)
assert isinstance(button, WebElement)
navigate(button)

# Add seventh product to cart
add_product_to_cart(driver, 7, "The Comet Book")

# Verify products in shopping cart
products = wait_for_elements(
    driver,
    By.XPATH,
    "//div[contains(@class, 'CartItems')]/a/div/p",
)
assert isinstance(products, list)
assert len(products) == 2
assert isinstance(products[0], WebElement)
assert "Solar System Color Imager" == products[0].text.strip()
assert isinstance(products[1], WebElement)
assert "The Comet Book" == products[1].text.strip()

# Locate the submit button and click it
submit_button = wait_for_element(driver, By.XPATH, "//button[@type='submit']")
assert isinstance(submit_button, WebElement)
navigate(submit_button)

# Verify order complete page loads
heading = wait_for_element(
    driver,
    By.XPATH,
    "//h1[contains(@class, 'Checkout-')]",
)
assert isinstance(heading, WebElement)
assert "Your order is complete!" == heading.text.strip()

# Verify products in order complete page
products = wait_for_elements(driver, By.CSS_SELECTOR, "h5")
assert isinstance(products, list)
assert len(products) == 2
assert isinstance(products[0], WebElement)
assert "Solar System Color Imager" == products[0].text.strip()
assert isinstance(products[1], WebElement)
assert "The Comet Book" == products[1].text.strip()

# ----------------------------------------------------------------------------
# Test Script for OpenTelemetry Demo Features Application
# ----------------------------------------------------------------------------

# Load the feature page
driver.get("http://localhost:8080/feature")

# Give the page some time to settle
time.sleep(2)

# Verify feature page loads
heading = wait_for_element(driver, By.XPATH, "//nav//a[@href='/feature']")
assert isinstance(heading, WebElement)
assert "Flagd Configurator" == heading.text.strip()

# Locate the Advanced nav link and click it
advanced_link = wait_for_element(driver, By.LINK_TEXT, "Advanced")
assert isinstance(advanced_link, WebElement)
navigate(advanced_link)

# Verify Advanced page loads
textarea = wait_for_element(
    driver,
    By.XPATH,
    "//form/textarea[@name='content']",
)
assert isinstance(textarea, WebElement)
json_text = textarea.get_attribute("value") # type: ignore
assert json_text is not None and json_text != ""

# Load JSON content and verify a feature flag exists
try:
    data = json.loads(json_text)

    assert "flags" in data
    flags = data["flags"]

    assert "adFailure" in flags
    ad_failure_flag = flags["adFailure"]

    assert "state" in ad_failure_flag
    assert ad_failure_flag["state"] == "ENABLED"
except json.JSONDecodeError as e:
    print(f"JSON Format Error: {e.msg} at line {e.lineno}, column {e.colno}")
    sys.exit(1)
except Exception as e:
    print(
        f"An unexpected error occurred while verifying the feature flag JSON data: {e}",
    )
    sys.exit(1)

# Release the driver / close the browser
driver.quit()
