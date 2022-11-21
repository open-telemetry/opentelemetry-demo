# Manual Span Attributes

This document contains the list of manual Span Attributes used throughout the demo:

## AdService

| Name                        | Type   | Description                           |
|-----------------------------|--------|---------------------------------------|
| `app.ads.category`          | string | Category for returned ad              |
| `app.ads.contextKeys`       | string | Context keys used to find related ads |
| `app.ads.contextKeys.count` | number | Count of unique context keys used     |
| `app.ads.count`             | number | Count of ads returned to user         |

## CartService

| Name                   | Type   | Description                    |
|------------------------|--------|--------------------------------|
| `app.cart.items.count` | number | Number of unique items in cart |
| `app.product.id`       | string | Product Id for cart item       |
| `app.product.quantity` | string | Quantity for cart item         |
| `app.user.id`          | string | User Id                        |

## CheckoutService

| Name                         | Type   | Description                     |
|------------------------------|--------|---------------------------------|
| `app.cart.items.count`       | number | Total number of items in cart   |
| `app.order.amount`           | number | Order amount                    |
| `app.order.id`               | string | Order Id                        |
| `app.order.items.count`      | number | Number of unique items in order |
| `app.payment.transaction.id` | string | Payment transaction Id          |
| `app.shipping.amount`        | number | Shipping amount                 |
| `app.shipping.tracking.id`   | string | Shipping tracking Id            |
| `app.user.currency`          | string | User currency                   |
| `app.user.id`                | string | User Id                         |

## CurrencyService

| Name                           | Type   | Description                   |
|--------------------------------|--------|-------------------------------|
| `app.currency.conversion.from` | string | Currency code to convert from |
| `app.currency.conversion.to`   | string | Currency code to convert to   |

## EmailService

| Name                  | Type   | Description                       |
|-----------------------|--------|-----------------------------------|
| `app.email.recipient` | string | Email used for order confirmation |
| `app.order.id`        | string | Order Id                          |

## FeatureFlagService

| Name                          | Type   | Description              |
|-------------------------------|--------|--------------------------|
| `app.featureflag.name`        | string | Name of the feature flag |
| `app.featureflag.description` | string | Admin description        |
| `app.featureflag.enabled`     | boolean | The feature flag status |

## Frontend

| Name                     | Type   | Description                   |
|--------------------------|--------|-------------------------------|
| `app.cart.size`          | number | Total number of items in cart |
| `app.cart.items.count`   | number | Count of unique items in cart |
| `app.cart.shipping.cost` | number | Cart shipping cost            |
| `app.cart.total.price`   | number | Cart total price              |
| `app.currency`           | string | User currency                 |
| `app.currency.new`       | string | New currency to set           |
| `app.order.total`        | number | Order total cost              |
| `app.product.id`         | string | Product Id                    |
| `app.product.quantity`   | number | Product quantity              |
| `app.products.count`     | number | Total products displayed      |
| `app.request.id`         | string | Request Id                    |
| `app.session.id`         | string | Session Id                    |
| `app.user.id`            | string | User Id                       |

## LoadGenerator

| Name     | Type | Description |
|----------|------|-------------|
| None yet |      |             |

## PaymentService

| Name                     | Type    | Description                                          |
|--------------------------|---------|------------------------------------------------------|
| `app.payment.amount`     | number  | Total payment amount                                 |
| `app.payment.card_type`  | string  | Type of card used for payment                        |
| `app.payment.card_valid` | boolean | Was the card used valid                              |
| `app.payment.charged`    | boolean | Was the charge successful (false with loadgenerator) |

## ProductCatalogService

| Name                        | Type   | Description                           |
|-----------------------------|--------|---------------------------------------|
| `app.product.id`            | string | Product Id                            |
| `app.product.name`          | string | Product name                          |
| `app.products.count`        | number | Number of products in catalog         |
| `app.products_search.count` | number | Number of products returned in search |

## QuoteService

| Name                    | Type   | Description          |
|-------------------------|--------|----------------------|
| `app.quote.items.count` | number | Total items to ship  |
| `app.quote.cost.total`  | number | Total shipping quote |

## RecommendationService

| Name                             | Type    | Description                             |
|----------------------------------|---------|-----------------------------------------|
| `app.filtered_products.count`    | number  | Number of filtered products returned    |
| `app.products.count`             | number  | Number of products in catalog           |
| `app.products_recommended.count` | number  | Number of recommended products returned |
| `app.cache_hit`                  | boolean | If cache was accessed or not            |

## ShippingService

| Name                       | Type   | Description                   |
|----------------------------|--------|-------------------------------|
| `app.shipping.cost.total`  | number | Total shipping cost           |
| `app.shipping.items.count` | number | Total items to ship           |
| `app.shipping.tracking.id` | string | Shipping tracking Id          |
| `app.shipping.zip_code`    | string | Zip code used to ship item(s) |
