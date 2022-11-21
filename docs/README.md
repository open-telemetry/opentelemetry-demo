# OpenTelemetry Demo Documentation

Welcome to the OpenTelemetry Demo! This folder contains overall documentation
for the project, how to install and run it, and some scenarios you can use to
view OpenTelemetry in action.

## Table of Contents

- [Guided Scenarios](#scenarios)
- [Language Instrumentation Examples](#language-feature-reference)
- [Quick Start](#running-the-demo)
- [References](#reference)
- [Service Documentation](#service-documentation)

### Running the Demo

Want to deploy the demo and see it in action? Start here.

- [Docker](./docker_deployment.md)
- [Kubernetes](./kubernetes_deployment.md)

### Language Feature Reference

Want to understand how a particular language's instrumentation works? Start
here.

| Language      | Auto Instrumentation                                                                                                                                                       | Manual Instrumentation                                                                                              |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------|
| .NET          | [Cart Service](./services/cartservice.md)                                                                                                                                  | [Cart Service](./services/cartservice.md)                                                                           |
| C++           |                                                                                                                                                                            | [Currency Service](./services/currencyservice.md)                                                                   |
| Erlang/Elixir | [Feature Flag Service](./services/featureflagservice.md)                                                                                                                   | [Feature Flag Service](./services/featureflagservice.md)                                                            |
| Go            | [Accounting Service](./services/accountingservice.md), [Checkout Service](./services/checkoutservice.md), [Product Catalog Service]( ./services/productcatalogservice.md ) | [Checkout Service](./services/checkoutservice.md), [Product Catalog Service]( ./services/productcatalogservice.md ) |
| Java          | [Ad Service](./services/adservice.md)                                                                                                                                      | [Ad Service](./services/adservice.md)                                                                               |
| JavaScript    | [Frontend]( ./services/frontend.md )                                                                                                                                       | [Frontend](./services/frontend.md), [Payment Service](./services/paymentservice.md)                                 |
| Kotlin        | [Fraud Detection Service]( ./services/frauddetectionservice.md )                                                                                                           |                                                                                                                     |
| PHP           | [Quote Service](./services/quoteservice.md)                                                                                                                                | [Quote Service](./services/quoteservice.md)                                                                         |
| Python        | [Recommendation Service](./services/recommendationservice.md)                                                                                                              | [Recommendation Service](./services/recommendationservice.md)                                                       |
| Ruby          | [Email Service](./services/emailservice.md)                                                                                                                                | [Email Service](./services/emailservice.md)                                                                         |
| Rust          | [Shipping Service](./services/shippingservice.md)                                                                                                                          | [Shipping Service](./services/shippingservice.md)                                                                   |

### Service Documentation

Specific information about how OpenTelemetry is deployed in each service can be
found here:

- [Ad Service](./services/adservice.md)
- [Cart Service](./services/cartservice.md)
- [Checkout Service](./services/checkoutservice.md)
- [Email Service](./services/emailservice.md)
- [Feature Flag Service](./services/featureflagservice.md)
- [Frontend](./services/frontend.md)
- [Load Generator](./services/loadgenerator.md)
- [Payment Service](./services/paymentservice.md)
- [Product Catalog Service](./services/productcatalogservice.md)
- [Quote Service](./services/quoteservice.md)
- [Recommendation Service](./services/recommendationservice.md)
- [Shipping Service](./services/shippingservice.md)

### Scenarios

How can you solve problems with OpenTelemetry? These scenarios walk you through
some pre-configured problems and show you how to interpret OpenTelemetry data to
solve them.

We'll be adding more scenarios over time.

- Generate a [Product Catalog error](feature_flags.md) for `GetProduct` requests
  with product id: `OLJCESPC7Z` using the Feature Flag service
- Discover a memory leak and diagnose it using metrics and traces. [Read more](./scenarios/recommendation_cache.md)

### Reference

Project reference documentation, like requirements and feature matrices.

- [Architecture](./current_architecture.md)
- [Development](./development.md)
- [Feature Flags Reference](./feature_flags.md)
- [Metric Feature Matrix](./metric_service_features.md)
- [Requirements](./requirements/)
- [Screenshots](./demo_screenshots.md)
- [Service Roles Table](./service_table.md)
- [Span Attributes Reference](./manual_span_attributes.md)
- [Tests](./tests.md)
- [Trace Feature Matrix](./trace_service_features.md)
