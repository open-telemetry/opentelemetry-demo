# Service Roles

View [Service Graph](../README.md#architecture) to visualize request flows.

| Service                                                         | Language        | Description                                                                                                                                  |
|-----------------------------------------------------------------|-----------------|----------------------------------------------------------------------------------------------------------------------------------------------|
| [adservice](../src/adservice/README.md)                         | Java            | Provides text ads based on given context words.                                                                                              |
| [cartservice](../src/cartservice/README.md)                     | DotNet          | Stores the items in the user's shopping cart in Redis and retrieves it.                                                                      |
| [checkoutservice](../src/checkoutservice/README.md)             | Go              | Retrieves user cart, prepares order and orchestrates the payment, shipping and the email notification.                                       |
| [currencyservice](../src/currencyservice/README.md)             | C++             | Converts one money amount to another currency. Uses real values fetched from European Central Bank. It's the highest QPS service.            |
| [emailservice](../src/emailservice/README.md)                   | Ruby            | Sends users an order confirmation email (mock).                                                                                              |
| [featureflagservice](../src/featureflagservice/README.md)       | Erlang/Elixir   | CRUD feature flag service to demonstrate various scenarios like fault injection & how to emit telemetry from a feature flag reliant service. |
| [frontend](../src/frontend/README.md)                           | JavaScript      | Exposes an HTTP server to serve the website. Does not require signup/login and generates session IDs for all users automatically.            |
| [loadgenerator](../src/loadgenerator/README.md)                 | Python/Locust   | Continuously sends requests imitating realistic user shopping flows to the frontend.                                                         |
| [paymentservice](../src/paymentservice/README.md)               | JavaScript      | Charges the given credit card info (mock) with the given amount and returns a transaction ID.                                                |
| [productcatalogservice](../src/productcatalogservice/README.md) | Go              | Provides the list of products from a JSON file and ability to search products and get individual products.                                   |
| [recommendationservice](../src/recommendationservice/README.md) | Python          | Recommends other products based on what's given in the cart.                                                                                 |
| [shippingservice](../src/shippingservice/README.md)             | Rust            | Gives shipping cost estimates based on the shopping cart. Ships items to the given address (mock).                                           |
