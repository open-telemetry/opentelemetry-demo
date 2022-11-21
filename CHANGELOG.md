# Changelog

Please update changelog as part of any significant pull request. Place short
description of your change into "Unreleased" section. As part of release process
content of "Unreleased" section content will generate release notes for the
release.

## Unreleased

* The initial code base is donated from a
[fork](https://github.com/julianocosta89/opentelemetry-microservices-demo) of
the [Google microservices
demo](https://github.com/GoogleCloudPlatform/microservices-demo) with express
knowledge of the owners. The pre-existing copyrights will remain. Any future
significant modifications will be credited to OpenTelemetry Authors.
* Added feature flag service protos
([#26](https://github.com/open-telemetry/opentelemetry-demo/pull/26))
* Added span attributes to frontend service
([#82](https://github.com/open-telemetry/opentelemetry-demo/pull/82))
* Rewrote shipping service in Rust
([#35](https://github.com/open-telemetry/opentelemetry-demo/issues/35))
* Added feature flag service implementation
([#141](https://github.com/open-telemetry/opentelemetry-demo/pull/141))
* Added additional attributes to productcatalog service
([#143](https://github.com/open-telemetry/opentelemetry-demo/pull/143))
* Added manual instrumentation to ad service
([#150](https://github.com/open-telemetry/opentelemetry-demo/pull/150))
* Added manual instrumentation to email service
([#158](https://github.com/open-telemetry/opentelemetry-demo/pull/158))
* Added basic metric support and Prometheus storage
([#160](https://github.com/open-telemetry/opentelemetry-demo/pull/160))
* Added manual instrumentation to recommendation service
([#163](https://github.com/open-telemetry/opentelemetry-demo/pull/163))
* Added manual instrumentation to checkout service
([#164](https://github.com/open-telemetry/opentelemetry-demo/pull/164))
* Added Grafana service and enhanced metric experience
([#175](https://github.com/open-telemetry/opentelemetry-demo/pull/175))
* Enhanced cart service attributes
([#183](https://github.com/open-telemetry/opentelemetry-demo/pull/183))
* Re-implemented currency service using C++
([#189](https://github.com/open-telemetry/opentelemetry-demo/pull/189))
* Simplified repo name and dropped the '-webstore' suffix in every place
([#225](https://github.com/open-telemetry/opentelemetry-demo/pull/225))
* Added end-to-end tests to each individual service
([#242](https://github.com/open-telemetry/opentelemetry-demo/pull/242))
* Added ability for repo forks to specify additional collector settings
([#246](https://github.com/open-telemetry/opentelemetry-demo/pull/246))
* Add metrics endpoint in adservice to send metrics from java agent
([#237](https://github.com/open-telemetry/opentelemetry-demo/pull/237))
* Support override java agent jar
([#244](https://github.com/open-telemetry/opentelemetry-demo/pull/244))
* Pulling java agent from the Java instrumentation releases instead.
([#253](https://github.com/open-telemetry/opentelemetry-demo/pull/253))
* Added explicit support for Kubernetes.
([#255](https://github.com/open-telemetry/opentelemetry-demo/pull/255))
* Added spanmetrics processor to otelcol
([#212](https://github.com/open-telemetry/opentelemetry-demo/pull/212))
* Added span attributes to shipping service
([#260](https://github.com/open-telemetry/opentelemetry-demo/pull/260))
* Added span attributes to currency service
([#265](https://github.com/open-telemetry/opentelemetry-demo/pull/265))
* Restricted network and port bindings
([#272](https://github.com/open-telemetry/opentelemetry-demo/pull/272))
* Feature Flag Service UI exposed on port 8081
([#273](https://github.com/open-telemetry/opentelemetry-demo/pull/273))
* Reimplemented Frontend app using [Next.js](https://nextjs.org/) Browser client
([#236](https://github.com/open-telemetry/opentelemetry-demo/pull/236))
* Remove set_currency from load generator
([#290](https://github.com/open-telemetry/opentelemetry-demo/pull/290))
* Added Frontend [Cypress](https://www.cypress.io/) E2E tests
([#298](https://github.com/open-telemetry/opentelemetry-demo/pull/298))
* Added baggage support in CurrencyService
([#281](https://github.com/open-telemetry/opentelemetry-demo/pull/281))
* Added error for a specific product based on a feature flag
([#245](https://github.com/open-telemetry/opentelemetry-demo/pull/245))
* Added Frontend Instrumentation
([#293](https://github.com/open-telemetry/opentelemetry-demo/pull/293))
* Add Feature Flags definitions
([#314](https://github.com/open-telemetry/opentelemetry-demo/pull/314))
* Enable Locust loadgen environment variable config options
([#316](https://github.com/open-telemetry/opentelemetry-demo/pull/316))
* Simplified and cleaned up ProductCatalogService
([#317](https://github.com/open-telemetry/opentelemetry-demo/pull/317))
* Updated Product Catalog to Match Astronomy Webstore
([#285](https://github.com/open-telemetry/opentelemetry-demo/pull/285))
* Add Span link for synthetic requests (from load generator)
([#332](https://github.com/open-telemetry/opentelemetry-demo/pull/332))
* Add `synthetic_request=true` baggage to load generator requests
([#331](https://github.com/open-telemetry/opentelemetry-demo/pull/331))
* Add span events to shipping service
([#344](https://github.com/open-telemetry/opentelemetry-demo/pull/344))
* Add PHP quote service
([#345](https://github.com/open-telemetry/opentelemetry-demo/pull/345))
* Improve initial run time, without a build
([#362](https://github.com/open-telemetry/opentelemetry-demo/pull/362))
* Add custom span and custom span attributes for Feature Flag Service
([#371](https://github.com/open-telemetry/opentelemetry-demo/pull/371))
* Change Cart Service to be async
([#372](https://github.com/open-telemetry/opentelemetry-demo/pull/372))
* Removed Postgres error on startup
([#378](https://github.com/open-telemetry/opentelemetry-demo/pull/378))
* Fixed traffic to Ad and Recommendation Service
([#379](https://github.com/open-telemetry/opentelemetry-demo/pull/379))
* Add dotnet runtime metrics to the Cart Service
([#393](https://github.com/open-telemetry/opentelemetry-demo/pull/393))
* Add dotnet instrumentation libraries to the Cart Service
([#394](https://github.com/open-telemetry/opentelemetry-demo/pull/394))
* Fixed Feature Flag Service error on start up
([#402](https://github.com/open-telemetry/opentelemetry-demo/pull/402))
* Update Checkout Service Go version to 1.19 once OTel Go Metrics require 1.18+
([#409](https://github.com/open-telemetry/opentelemetry-demo/pull/409))
* Added hero scenario metric to Checkout Service on cache leak
([#339](https://github.com/open-telemetry/opentelemetry-demo/pull/339))
* Added basic metrics support for recommendation service (Python)
([#416](https://github.com/open-telemetry/opentelemetry-demo/pull/416))
* Added metrics auto-instrumentation + minor metrics refactor for recommendation
 service (Python)
 [#432](https://github.com/open-telemetry/opentelemetry-demo/pull/432)
* Replaced the Jaeger exporter to the OTLP exporter in the OTel Collector
([#435](https://github.com/open-telemetry/opentelemetry-demo/pull/435))
* Set resource memory limits for all services
([#460](https://github.com/open-telemetry/opentelemetry-demo/pull/460))
* Added cache scenario to recommendation service
([#455](https://github.com/open-telemetry/opentelemetry-demo/pull/455))
* Update cartservice Dockerfile to support ARM64
([#439](https://github.com/open-telemetry/opentelemetry-demo/pull/439))
* Update shippingservice to add resource data to spans
([#504](https://github.com/open-telemetry/opentelemetry-demo/pull/504))
* Add Envoy as reverse proxy for all user-facing services
([#508](https://github.com/open-telemetry/opentelemetry-demo/pull/508))
* Envoy: Grafana, Load Generator, Jaeger exposed.
([#513](https://github.com/open-telemetry/opentelemetry-demo/pull/513))
* Added frontend instrumentation exporter custom url
([#512](https://github.com/open-telemetry/opentelemetry-demo/pull/512))
* Replaced PHP-CLI to PHP-Apache for a more realistic service
([#563](https://github.com/open-telemetry/opentelemetry-demo/pull/563))
* Optimize currencyservice build time with parallel build jobs
([#569](https://github.com/open-telemetry/opentelemetry-demo/pull/569))
* Optimize GitHub Builds and fix broken emulation of featureflag
([#536](https://github.com/open-telemetry/opentelemetry-demo/pull/536))
* Add basic metrics support for payment service
([#583](https://github.com/open-telemetry/opentelemetry-demo/pull/583))
* Change ZipCode data type from int to string
([#587](https://github.com/open-telemetry/opentelemetry-demo/pull/587))
