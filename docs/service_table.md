# Service Roles

View [Service Graph](./current_architecture.md) to visualize request flows.

| Service                                                      | Language      | Description                                                                                                                                  |
|--------------------------------------------------------------|---------------|----------------------------------------------------------------------------------------------------------------------------------------------|
| [accountingservice](./services/accountingservice.md)         | Go            | Processes incoming orders and count the sum of all orders (mock).                                                                            |
| [adservice](./services/adservice.md)                         | Java          | Provides text ads based on given context words.                                                                                              |
| [cartservice](./services/cartservice.md)                     | DotNet        | Stores the items in the user's shopping cart in Redis and retrieves it.                                                                      |
| [checkoutservice](./services/checkoutservice.md)             | Go            | Retrieves user cart, prepares order and orchestrates the payment, shipping and the email notification.                                       |
| [currencyservice](./services/currencyservice.md)             | C++           | Converts one money amount to another currency. Uses real values fetched from European Central Bank. It's the highest QPS service.            |
| [emailservice](./services/emailservice.md)                   | Ruby          | Sends users an order confirmation email (mock).                                                                                              |
| [frauddetectionservice](./services/frauddetectionservice.md) | Kotlin        | Analyzes incoming orders and detects fraud attempts (mock).                                                                                  |
| [featureflagservice](./services/featureflagservice.md)       | Erlang/Elixir | CRUD feature flag service to demonstrate various scenarios like fault injection & how to emit telemetry from a feature flag reliant service. |
| [frontend](./services/frontend.md)                           | JavaScript    | Exposes an HTTP server to serve the website. Does not require signup/login and generates session IDs for all users automatically.            |
| [loadgenerator](./services/loadgenerator.md)                 | Python/Locust | Continuously sends requests imitating realistic user shopping flows to the frontend.                                                         |
| [paymentservice](./services/paymentservice.md)               | JavaScript    | Charges the given credit card info (mock) with the given amount and returns a transaction ID.                                                |
| [productcatalogservice](./services/productcatalogservice.md) | Go            | Provides the list of products from a JSON file and ability to search products and get individual products.                                   |
| [quoteservice](./services/quoteservice.md)                   | PHP           | Calculates the shipping costs, based on the number of items to be shipped.                                                                   |
| [recommendationservice](./services/recommendationservice.md) | Python        | Recommends other products based on what's given in the cart.                                                                                 |
| [shippingservice](./services/shippingservice.md)             | Rust          | Gives shipping cost estimates based on the shopping cart. Ships items to the given address (mock).                                           |
