# Demo Architecture

**Online Boutique** is composed of microservices written in different programming
languages that talk to each other over gRPC and HTTP; and a load generator which
uses [Locust](https://locust.io/) to fake user traffic.

```mermaid
graph TD

subgraph Service Diagram
adservice(Ad Service):::java
cache[(Cache<br/>&#40redis&#41)]
cartservice(Cart Service):::dotnet
checkoutservice(Checkout Service):::golang
currencyservice(Currency Service):::cpp
emailservice(Email Service):::ruby
frontend(Frontend):::javascript
loadgenerator([Load Generator]):::python
paymentservice(Payment Service):::javascript
productcatalogservice(Product Catalog Service):::golang
quoteservice(Quote Service):::php
recommendationservice(Recommendation Service):::python
shippingservice(Shipping Service):::rust
featureflagservice(Feature Flag Service):::erlang
featureflagstore[(Feature Flag Store<br/>&#40PostgreSQL DB&#41)]

Internet -->|HTTP| frontend
loadgenerator -->|HTTP| frontend

checkoutservice --->|gRPC| cartservice --> cache
checkoutservice --->|gRPC| productcatalogservice
checkoutservice --->|gRPC| currencyservice
checkoutservice --->|HTTP| emailservice
checkoutservice --->|gRPC| paymentservice
checkoutservice -->|gRPC| shippingservice

frontend -->|gRPC| adservice
frontend -->|gRPC| cartservice
frontend -->|gRPC| productcatalogservice
frontend -->|gRPC| checkoutservice
frontend -->|gRPC| currencyservice
frontend -->|gRPC| recommendationservice -->|gRPC| productcatalogservice
frontend -->|gRPC| shippingservice -->|HTTP| quoteservice

productcatalogservice -->|gRPC| featureflagservice

shippingservice -->|gRPC| featureflagservice

featureflagservice --> featureflagstore

end
classDef java fill:#b07219,color:white;
classDef dotnet fill:#178600,color:white;
classDef golang fill:#00add8,color:black;
classDef cpp fill:#f34b7d,color:white;
classDef ruby fill:#701516,color:white;
classDef python fill:#3572A5,color:white;
classDef javascript fill:#f1e05a,color:black;
classDef rust fill:#dea584,color:black;
classDef erlang fill:#b83998,color:white;
classDef php fill:#4f5d95,color:white;
```

```mermaid
graph TD
subgraph Service Legend
  javasvc(Java):::java
  dotnetsvc(.NET):::dotnet
  golangsvc(Go):::golang
  cppsvc(C++):::cpp
  rubysvc(Ruby):::ruby
  pythonsvc(Python):::python
  javascriptsvc(JavaScript):::javascript
  rustsvc(Rust):::rust
  erlangsvc(Erlang/Elixir):::erlang
  phpsvc(PHP):::php
end

classDef java fill:#b07219,color:white;
classDef dotnet fill:#178600,color:white;
classDef golang fill:#00add8,color:black;
classDef cpp fill:#f34b7d,color:white;
classDef ruby fill:#701516,color:white;
classDef python fill:#3572A5,color:white;
classDef javascript fill:#f1e05a,color:black;
classDef rust fill:#dea584,color:black;
classDef erlang fill:#b83998,color:white;
classDef php fill:#4f5d95,color:white;
```

Find the **Protocol Buffer Definitions** in the `/pb/` directory.
