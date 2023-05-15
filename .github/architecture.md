# Opensearch OTEL Demo Architecture
This document will review the OpenSearch architecture for the [OTEL demo](https://opentelemetry.io/docs/demo/) and will review how to use the new Observability capabilities
implemented into OpenSearch.

[OTEL DEMO](https://opentelemetry.io/docs/demo/architecture/) Describes the list of services that are composing the Astronomy Shop.

They are combined of:
 - [Accounting](https://opentelemetry.io/docs/demo/services/accounting/)
 - [Ad](https://opentelemetry.io/docs/demo/services/ad/)
 - [Cart](https://opentelemetry.io/docs/demo/services/cart/)
 - [Checkout](https://opentelemetry.io/docs/demo/services/checkout/)
 - [Currency](https://opentelemetry.io/docs/demo/services/currency/)
 - [Email](https://opentelemetry.io/docs/demo/services/email/)
 - [Feature Flag](https://opentelemetry.io/docs/demo/services/feature-flag/)
 - [Fraud Detection](https://opentelemetry.io/docs/demo/services/fraud-detection/)
 - [Frontend](https://opentelemetry.io/docs/demo/services/frontend/)
 - [Frontend Nginx Proxy](../src/nginx-otel/README.md) *(replacement for _Frontend-Proxy_)* 
 - [Kafka](https://opentelemetry.io/docs/demo/services/kafka/)
 - [Load Generator](https://opentelemetry.io/docs/demo/services/load-generator/)
 - [Payment](https://opentelemetry.io/docs/demo/services/payment/)
 - [Product Catalog](https://opentelemetry.io/docs/demo/services/product-catalog/)
 - [Quote](https://opentelemetry.io/docs/demo/services/quote/)
 - [Recommendation](https://opentelemetry.io/docs/demo/services/recommendation/)
 - [Shipping](https://opentelemetry.io/docs/demo/services/shipping/)
 - [Fluent-Bit](../src/fluent-bit/README.md) *(nginx's otel log exported)* 
 - [Integrations](../src/integrations/README.md) *(pre-canned OpenSearch assets)* 


---

## Purpose
The purpose of this demo is to demonstrate the different capabilities of OpenSearch Observability to investigate and reflect your system.

 - Integrations - the integration service is a list of pre-canned assets that are loaded in a combined manner to allow users the ability
for simple and automatic way to discover and review their services topology.

These integrations contain the following assets:
 - components & index template mapping
 - datasources 
 - data-stream & indices
 - queries
 - dashboards
   
Once they are loaded, the user can imminently review his OTEL demo services and dashboards that reflect the system state.
 - [Nginx Dashboard](../src/integrations/display/nginx-logs-dashboard-new.ndjson) - reflects the Nginx Proxy server that routes all the network communication to/from the frontend
 - [Prometheus datasource](../src/integrations/datasource/prometheus.json) - reflects the connectivity to the prometheus metric storage that allows us to federate metrics analytics queries
 - [Logs Datastream](../src/integrations/indices/data-stream.json) - reflects the data-stream used by nginx logs ingestion and dashboards representing a well-structured [log schema](../src/integrations/mapping-templates/logs.mapping)

Once these assets are loaded - the user can start reviewing its Observability dashboards and traces

![Nginx Dashboard](img/nginx_dashboard.png)

![Prometheus Metrics](img/prometheus_federated_metrics.png)

![Trace Analytics](img/trace_analytics.png)

![Service Maps](img/services.png)

![Traces](img/traces.png)


---

### **Scenarios**

How can you solve problems with OpenTelemetry? These scenarios walk you through some pre-configured problems and show you how to interpret OpenTelemetry data to solve them.

- Generate a Product Catalog error for GetProduct requests with product id: OLJCESPC7Z using the Feature Flag service
- Discover a memory leak and diagnose it using metrics and traces. Read more

### **Reference**
Project reference documentation, like requirements and feature matrices [here](https://opentelemetry.io/docs/demo/#reference)

