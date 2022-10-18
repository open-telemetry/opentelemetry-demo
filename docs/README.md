# OpenTelemetry Demo Documentation

Welcome to the OpenTelemetry Demo! This folder contains overall documentation
for the project, how to install and run it, and some scenarios you can use to
view OpenTelemetry in action.

## Table of Contents

### Running the Demo

Want to deploy the demo and see it in action? Start here.

- [Docker](./docker_deployment.md)
- [Kubernetes](./kubernetes_deployment.md)

### Language Feature Reference

Want to understand how a particular language's instrumentation works? Start
here.

| Language      | Auto Instrumentation                                                                                                | Manual Instrumentation                                                                                              |
|---------------|---------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------|
| .NET          | [Cart Service](./services/cartservice.md)                                                                           | [Cart Service](./services/cartservice.md)                                                                           |
| C++           |                                                                                                                     |                                                                                                                     |
| Erlang/Elixir | [Feature Flag Service](./services/featureflagservice.md)                                                            | [Feature Flag Service](./services/featureflagservice.md)                                                            |
| Go            | [Checkout Service](./services/checkoutservice.md), [Product Catalog Service]( ./services/productcatalogservice.md ) | [Checkout Service](./services/checkoutservice.md), [Product Catalog Service]( ./services/productcatalogservice.md ) |
| Java          | [Ad Service](./services/adservice.md)                                                                               | [Ad Service](./services/adservice.md)                                                                               |
| JavaScript    | [Frontend]( ./services/frontend.md )                                                                                | [Frontend](./services/frontend.md), [Payment Service](./services/paymentservice.md)                                 |
| PHP           | [Quote Service](./services/quoteservice.md)                                                                         | [Quote Service](./services/quoteservice.md)                                                                         |
| Python        | [Recommendation Service](./services/recommendationservice.md)                                                       | [Recommendation Service](./services/recommendationservice.md)                                                       |
| Ruby          | [Email Service](./services/emailservice.md)                                                                         | [Email Service](./services/emailservice.md)                                                                         |
| Rust          | [Shipping Service](./services/shippingservice.md)                                                                   | [Shipping Service](./services/shippingservice.md)                                                                   |

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

- [NYI](./README.md)

### Reference

Project reference documentation, like requirements and feature matrices.

- [Requirements](./requirements/)
- [Span Attributes Reference](./manual_span_attributes.md)
- [Feature Flags Reference](./feature_flags.md)
- [Trace Feature Matrix](./trace_service_features.md)
- [Metric Feature Matrix](./metric_service_features.md)
- [Service Roles Table](./service_table.md)
