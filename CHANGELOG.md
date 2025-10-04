# Changelog

Please update changelog as part of any significant pull request. Place short
description of your change into "Unreleased" section. As part of release
process content of "Unreleased" section content will generate release notes for
the release.

## Unreleased

* [grafana] Update grafana to 11.3.0
  ([#1764](https://github.com/open-telemetry/opentelemetry-demo/pull/1764))
* [chore] Move build args to .env file
  ([#1767](https://github.com/open-telemetry/opentelemetry-demo/pull/1767))
* [frontendproxy] add access logs
  ([#1768](https://github.com/open-telemetry/opentelemetry-demo/pull/1768))
* [grafana] Fix Dashboards
  ([#1779](https://github.com/open-telemetry/opentelemetry-demo/pull/1779))
* [accountingservice] bump OpenTelemetry .NET Automatic Instrumentation
  to 1.9.0 ([#1780](https://github.com/open-telemetry/opentelemetry-demo/pull/1780))
* [react-native-app] Add React Native example app
  ([#1781](https://github.com/open-telemetry/opentelemetry-demo/pull/1781))
* [chore] Add multi-platform build support
  ([#1785](https://github.com/open-telemetry/opentelemetry-demo/pull/1785))
* [chore] update memory limits for flagd, flagdui, and loadgenerator
  ([#1786](https://github.com/open-telemetry/opentelemetry-demo/pull/1786))
* [chore] Generate protobuf code for Go and Python services
  ([#1794](https://github.com/open-telemetry/opentelemetry-demo/pull/1784))
* [paymentservice] Add nodejs instrumentation for runtime metrics
  ([#1797](https://github.com/open-telemetry/opentelemetry-demo/pull/1797))
* [flagd and paymentservice] Update `paymentServiceFailure` to use a list of
  variants and add loyalty level attributes to spans. Added `service.name` to logs.
  ([#1815](https://github.com/open-telemetry/opentelemetry-demo/pull/1815))
* [accounting] rename accountingservice to accounting
  ([#1827](https://github.com/open-telemetry/opentelemetry-demo/pull/1827))
* [cartservice] - Add Exemplars to Cart Service
  ([#1830](https://github.com/open-telemetry/opentelemetry-demo/pull/1830))
* [ad] rename adservice to ad
  ([#1832](https://github.com/open-telemetry/opentelemetry-demo/pull/1832))
* [grafana] Add Exemplars Dashboard
  ([#1836](https://github.com/open-telemetry/opentelemetry-demo/pull/1836))
* [quote] rename quoteservice to quote
  ([#1838](https://github.com/open-telemetry/opentelemetry-demo/pull/1838))
* [cart] rename cartservice to cart
  ([#1839](https://github.com/open-telemetry/opentelemetry-demo/pull/1839))
* [flagd-ui] rename flagdui to flagd-ui
  ([#1840](https://github.com/open-telemetry/opentelemetry-demo/pull/1840))
* [otel-collector] rename otelcol to otel-collector
  ([#1841](https://github.com/open-telemetry/opentelemetry-demo/pull/1841))
* [shipping] rename shippingservice to shipping
  ([#1842](https://github.com/open-telemetry/opentelemetry-demo/pull/1842))
* [chore] Update demo Dependencies (Collector, Grafana, FlagD, Jaeger, Prometheus)
  ([#1855](https://github.com/open-telemetry/opentelemetry-demo/pull/1855))
* [load-generator] rename loadgenerator to load-generator
  ([#1856](https://github.com/open-telemetry/opentelemetry-demo/pull/1856))
* [image-provider] rename imageprovider to image-provider
  ([#1857](https://github.com/open-telemetry/opentelemetry-demo/pull/1857))
* [currency] rename currencyservice to currency
  ([#1858](https://github.com/open-telemetry/opentelemetry-demo/pull/1858))
* [email] rename emailservice to email
  ([#1861](https://github.com/open-telemetry/opentelemetry-demo/pull/1861))
* [fraud-detection] rename frauddetectionservice to fraud-detection
  ([#1862](https://github.com/open-telemetry/opentelemetry-demo/pull/1862))
* [payment] rename paymentservice to payment
  ([#1863](https://github.com/open-telemetry/opentelemetry-demo/pull/1863))
* [recommendation] rename recommendationservice to recommendation
  ([#1865](https://github.com/open-telemetry/opentelemetry-demo/pull/1865))
* [product-catalog] rename productcatalogservice to product-catalog
  ([#1864](https://github.com/open-telemetry/opentelemetry-demo/pull/1864))
* [checkout] rename checkoutservice to checkout
  ([#1867](https://github.com/open-telemetry/opentelemetry-demo/pull/1867))
* [chore] remove `SERVICE_` from environment variables
  ([#1897](https://github.com/open-telemetry/opentelemetry-demo/pull/1897))
* [frontend-proxy] rename frontendproxy to frontend-proxy
  ([#1910](https://github.com/open-telemetry/opentelemetry-demo/pull/1910))
* [flagd-ui] fixed eslint ignore comment with useCallback
  ([#1923](https://github.com/open-telemetry/opentelemetry-demo/pull/1923))
* [chore] Add memory for frontend-proxy, kafka, grafana, opensearch
  ([#1931](https://github.com/open-telemetry/opentelemetry-demo/pull/1931))

## 1.12.0

* [accountingservice] allow running the container with non root user
  ([#1692](https://github.com/open-telemetry/opentelemetry-demo/pull/1692))
* [chore] Add yamllint to `make all`
  ([#1707](https://github.com/open-telemetry/opentelemetry-demo/pull/1707))
* [chore] Fix gen-proto for accountingservice
  ([#1709](https://github.com/open-telemetry/opentelemetry-demo/pull/1709))
* [chore] Add depends on to otelcol to wait on healthy opensearch
  ([#1724](https://github.com/open-telemetry/opentelemetry-demo/pull/1724))
* [flagd-ui] Add UI for managing Flagd feature flags
  ([#1725](https://github.com/open-telemetry/opentelemetry-demo/pull/1725))
* [accountingservice] bump OpenTelemetry .NET Automatic Instrumentation
  to 1.8.0 together with other dependencies
  ([#1727](https://github.com/open-telemetry/opentelemetry-demo/pull/1727))
* [frontend] fix imageSlowLoad headers not applied
  to 1.8.0 together with other dependencies
  ([#1733](https://github.com/open-telemetry/opentelemetry-demo/pull/1733))
* [cartservice] Propagate cartservice exceptions
  ([#1744](https://github.com/open-telemetry/opentelemetry-demo/pull/1744))
* [cartservice] Update cart service to fail when cartServiceFailure is enabled
  ([#1748](https://github.com/open-telemetry/opentelemetry-demo/pull/1748))

## 1.11.1

* [otel-col] Add docker stats receiver
  ([#1650](https://github.com/open-telemetry/opentelemetry-demo/pull/1650))
* [otel-col] strip high-cardinality segments of span names
  ([#1668](https://github.com/open-telemetry/opentelemetry-demo/pull/1668))
* [tests] run trace based tests concurrently
  ([#1659](https://github.com/open-telemetry/opentelemetry-demo/pull/1659))
* [otel-col] Set OTLP receiver endpoint to avoid breaking changes
  ([#1662](https://github.com/open-telemetry/opentelemetry-demo/pull/1662))
* [accountingservice] increase memory to 120MB
  ([#1666](https://github.com/open-telemetry/opentelemetry-demo/pull/1666))
* [frontend] Update nodejs to latest LTS and bump dependencies
  ([#1670](https://github.com/open-telemetry/opentelemetry-demo/pull/1670))
* [otel-col] Add host metrics receiver
  ([#1675](https://github.com/open-telemetry/opentelemetry-demo/pull/1675))
* [adservice] bump dependencies & gradle version
  ([#1681](https://github.com/open-telemetry/opentelemetry-demo/pull/1681))

## 1.11.0

* [accountingservice] convert from Go service to .NET service, uses
  OpenTelemetry .NET Automatic Instrumentation.
  ([#1538](https://github.com/open-telemetry/opentelemetry-demo/pull/1538))
* [frontend] fixed default flagd port for HTTPS connections
  ([#1609](https://github.com/open-telemetry/opentelemetry-demo/pull/1609))
* [cartservice] bump .NET package to 1.9.0 release
  ([#1610](https://github.com/open-telemetry/opentelemetry-demo/pull/1610))
* [Valkey] Replace Redis with Valkey
  ([#1619](https://github.com/open-telemetry/opentelemetry-demo/pull/1619))
* [recommendation] updated flag name to match flagd configuration
  ([#1634](https://github.com/open-telemetry/opentelemetry-demo/pull/1634))

## 1.10.0

* [frauddetectionservice] use span links when consuming from Kafka
  ([#1501](https://github.com/open-telemetry/opentelemetry-demo/pull/1501))
* [frontend] reunite trace from loadgenerator
  ([#1506](https://github.com/open-telemetry/opentelemetry-demo/pull/1506))
* [repo] add traceBasedTests image to published images
  ([#1507](https://github.com/open-telemetry/opentelemetry-demo/pull/1507))
* [quoteservice] add manual metric, export logs periodically
  ([#1519](https://github.com/open-telemetry/opentelemetry-demo/pull/1519))
* [flagd] export flagd traces to otel collector
  ([#1522](https://github.com/open-telemetry/opentelemetry-demo/pull/1522))
* [frontend] Pass down image optimization requests to imageprovider
  ([#1522](https://github.com/open-telemetry/opentelemetry-demo/pull/1522))
* [kafka] add kafkaQueueProblems feature flag
  ([#1528](https://github.com/open-telemetry/opentelemetry-demo/pull/1528))
* [otelcollector] Add `redisreceiver`
  ([#1537](https://github.com/open-telemetry/opentelemetry-demo/pull/1537))
* [traceBasedTests] update to v1.0.0
  ([#1551](https://github.com/open-telemetry/opentelemetry-demo/pull/1551))
* [flagd] update to 0.10.1 and set 50M memory limit
  ([#1554](https://github.com/open-telemetry/opentelemetry-demo/pull/1554))
* [loadgenerator] Configure feature flag evaluation tracing
  ([#1553](https://github.com/open-telemetry/opentelemetry-demo/pull/1553))
* [recommendationservice] Configure feature flag evaluation tracing
  ([#1553](https://github.com/open-telemetry/opentelemetry-demo/pull/1553))
* [loadgenerator] Fix feature flag hooks setter method
  ([#1556](https://github.com/open-telemetry/opentelemetry-demo/pull/1556))
* [frontend] Slowloading of images based on imageSlowLoad flag
  ([#1515](https://github.com/open-telemetry/opentelemetry-demo/pull/1486))
* [frontend] Fix imageloading issues on optimized images. bump next.js version
  ([#1571](https://github.com/open-telemetry/opentelemetry-demo/pull/1571))
* [cartservice] bump .NET package to 1.8.1 release
  ([#1514](https://github.com/open-telemetry/opentelemetry-demo/pull/1514),
   [#1580](https://github.com/open-telemetry/opentelemetry-demo/pull/1580))
* [kafka] Fix permission issue with the telemetry agent when running in docker compose
  ([#1574](https://github.com/open-telemetry/opentelemetry-demo/pull/1574))
* [flagd] Add flagd service to minimal docker compose deployment
  ([#1585](https://github.com/open-telemetry/opentelemetry-demo/pull/1585))
* [kafka] Increase memory and Java heap limits
  ([#1592](https://github.com/open-telemetry/opentelemetry-demo/pull/1592))
* chore: Add service version to OTEL_RESOURCE_ATTRIBUTES
  ([#1594](https://github.com/open-telemetry/opentelemetry-demo/pull/1594))
* [checkout] increase Kafka resiliency and observability
  ([#1590](https://github.com/open-telemetry/opentelemetry-demo/pull/1590))

## 1.9.0

* [chore] docker compose: add container name as tag attribute to container logs
* [featureflag] deprecate in favor of flagd
  ([#1338](https://github.com/open-telemetry/opentelemetry-demo/pull/1388))
* [checkoutservice] add producer interceptor for tracing
  ([#1400](https://github.com/open-telemetry/opentelemetry-demo/pull/1400))
* [chore] increase memory for Collector and Jaeger
  ([#1396](https://github.com/open-telemetry/opentelemetry-demo/pull/1396))
* [chore] fix Make targets for restart and redeploy
  ([#1397](https://github.com/open-telemetry/opentelemetry-demo/pull/1397))
* [chore] add nightly releases
  ([#1398](https://github.com/open-telemetry/opentelemetry-demo/pull/1398))
* [checkoutservice] add producer interceptor for tracing
  ([#1400](https://github.com/open-telemetry/opentelemetry-demo/pull/1400))
* [productcatalogservice] fix graceful shutdown issues
  ([#1402](https://github.com/open-telemetry/opentelemetry-demo/pull/1402))
* [chore] remove unused integration test
  ([#1406](https://github.com/open-telemetry/opentelemetry-demo/pull/1406))
* [CartService] - Add Host Detector
  ([#1415](https://github.com/open-telemetry/opentelemetry-demo/pull/1415))
* [chore] - add tests and odd profiles to make stop
  ([#1427](https://github.com/open-telemetry/opentelemetry-demo/pull/1427))
* [shippingservice] fix context propagation
  ([#1433](https://github.com/open-telemetry/opentelemetry-demo/pull/1433))
* [chore] - Update Telemetry Components
  ([#1440](https://github.com/open-telemetry/opentelemetry-demo/pull/1440))
* [loadgenerator] emit logs via OTLP
  ([#1446](https://github.com/open-telemetry/opentelemetry-demo/pull/1446))
* [frontend] reset quantity when new product selected
  ([#1447](https://github.com/open-telemetry/opentelemetry-demo/pull/1447))
* [paymentservice] add paymentServiceFailure feature flag
  ([#1449](https://github.com/open-telemetry/opentelemetry-demo/pull/1449))
* [checkoutservice] add paymentServiceUnreachable feature flag
  ([#1449](https://github.com/open-telemetry/opentelemetry-demo/pull/1449))
* [Frontend-proxy] Add restart policy to compose file
  ([#1448](https://github.com/open-telemetry/opentelemetry-demo/pull/1448))
* [cartservice] update .NET to .NET 8.0.3
  ([#1460](https://github.com/open-telemetry/opentelemetry-demo/pull/1460))
* [adservice] add adServiceManualGC feature flag
  ([#1463](https://github.com/open-telemetry/opentelemetry-demo/pull/1463))
* [frontendproxy] remove deprecated start_child_span option
  ([#1469](https://github.com/open-telemetry/opentelemetry-demo/pull/1469))
* [currency] fix metric name
  ([#1470](https://github.com/open-telemetry/opentelemetry-demo/pull/1470))
* [frontend] disable instrumentation-fs library
  ([#1473](https://github.com/open-telemetry/opentelemetry-demo/pull/1473))
* [Imageprovider] Create Nginx service to host images, add instrumentation to it
  ([#1462](https://github.com/open-telemetry/opentelemetry-demo/pull/1462))
* [loadgenerator] added loadgeneratorFloodHomepage flagd
  ([#1486](https://github.com/open-telemetry/opentelemetry-demo/pull/1486))
* [adservice] add adServiceHighCpu feature flag
  ([#1510](https://github.com/open-telemetry/opentelemetry-demo/pull/1510))

## 1.8.0

* [grafana] update grafana to 10.2.3
  ([#1332](https://github.com/open-telemetry/opentelemetry-demo/pull/1332))
* [frontendproxy] Enable envoy environment resource detector
  ([#1291](https://github.com/open-telemetry/opentelemetry-demo/pull/1291))
* [currencyservice] - add package name prefix to `rpc.service` attribute
  ([#1333](https://github.com/open-telemetry/opentelemetry-demo/pull/1333))
* [currency] fix metric exporter options
  ([#1335](https://github.com/open-telemetry/opentelemetry-demo/pull/1335))
* [ffspostgres] define and use demo specific postgres image
  ([#1338](https://github.com/open-telemetry/opentelemetry-demo/pull/1338))
* [loadgenerator, frontend] enable browser traffic in loadgenerator using playwright
  ([#1345](https://github.com/open-telemetry/opentelemetry-demo/pull/1345))
* [accountingservice] update wiki link
  ([#1346](https://github.com/open-telemetry/opentelemetry-demo/pull/1346))
* [checkoutservice] update wiki link
  ([#1346](https://github.com/open-telemetry/opentelemetry-demo/pull/1346))
* [productcatalogservice] update wiki link
  ([#1346](https://github.com/open-telemetry/opentelemetry-demo/pull/1346))
* [adservice] added group and anonymous read permission to
  opentelemetry-javaagent.jar
  ([#1348](https://github.com/open-telemetry/opentelemetry-demo/pull/1348))
* [frauddetectionservice] added group and anonymous read permission to
  opentelemetry-javaagent.jar
  ([#1348](https://github.com/open-telemetry/opentelemetry-demo/pull/1348))
* [adservice] Major version update for Java instrumentation, version 2.0.0
  ([#1352](https://github.com/open-telemetry/opentelemetry-demo/pull/1352))
* [frauddetectionservice] Major version update for Java instrumentation,
  version 2.0.0
  ([#1352](https://github.com/open-telemetry/opentelemetry-demo/pull/1352))
* [kafka] Major version update for Java instrumentation, version 2.0.0
  ([#1352](https://github.com/open-telemetry/opentelemetry-demo/pull/1352))
* Align env variables for OTLP ports
  ([#1353](https://github.com/open-telemetry/opentelemetry-demo/pull/1353))
* Update dependent services - Collector, Grafana, Jaeger, Prometheus, etc.
  ([#1354](https://github.com/open-telemetry/opentelemetry-demo/pull/1354))
* [OpenSearch] Use native OpenSearch exporter from Collector
  ([#1356](https://github.com/open-telemetry/opentelemetry-demo/pull/1356))
* Update GO SDKs & fix metrics config
  ([#1357](https://github.com/open-telemetry/opentelemetry-demo/pull/1357))
* Update Python SDKs
  ([#1358](https://github.com/open-telemetry/opentelemetry-demo/pull/1358))
* [loadgenerator] fix browser traffic enabled flag
  ([#1359](https://github.com/open-telemetry/opentelemetry-demo/pull/1359))
* [productcatalog] allow products to be extended
  ([#1363](https://github.com/open-telemetry/opentelemetry-demo/pull/1363))
* [tests] update trace based tests for semantic conventions
  ([#1377](https://github.com/open-telemetry/opentelemetry-demo/pull/1377))
* [currencyservice] Add OTLP logs
  ([#1378](https://github.com/open-telemetry/opentelemetry-demo/pull/1378))
* [cartservice] update .NET to .NET 8.0.2
  ([#1380](https://github.com/open-telemetry/opentelemetry-demo/pull/1380))

## 1.7.2

* [cartservice] update .NET package to 1.7.0 release
  ([#1326](https://github.com/open-telemetry/opentelemetry-demo/pull/1326))
* [loadgenerator and recommendationservice] Update python base image
  ([#1329](https://github.com/open-telemetry/opentelemetry-demo/pull/1329))

## 1.7.1

* [grafana] revert to 10.2.0
* [cartservice] disable config reload
  ([#1312](https://github.com/open-telemetry/opentelemetry-demo/pull/1312))
* [cartservice] fixed cartServiceFailure feature flag
  ([#1313](https://github.com/open-telemetry/opentelemetry-demo/pull/1313))
* [accountingservice] Update dependencies and semconv
* ([#1316](https://github.com/open-telemetry/opentelemetry-demo/pull/1316))
* [featureflagservice] Allow setting initial feature flag values
  ([#1319](https://github.com/open-telemetry/opentelemetry-demo/pull/1319))

## 1.7.0

* update PHP quoteservice to use 1.0.0
  ([#1236](https://github.com/open-telemetry/opentelemetry-demo/pull/1236))
* Add ability to do probabilistic A/B testing with feature flags
  ([#1237](https://github.com/open-telemetry/opentelemetry-demo/pull/1237))
* add env var for pinning trace-based test tool version
  ([#1239](https://github.com/open-telemetry/opentelemetry-demo/pull/1239))
* [cartservice] Add .NET memory, CPU, and thread metrics
  ([#1265](https://github.com/open-telemetry/opentelemetry-demo/pull/1265))
* [cartservice] update .NET to .NET 8.0
  ([#1272](https://github.com/open-telemetry/opentelemetry-demo/pull/1272))
* update loadgenerator dependencies and the base image
  ([#1274](https://github.com/open-telemetry/opentelemetry-demo/pull/1274))
* [currencyservice]: update opentelemetry-cpp to 1.12.0
  ([#1275](https://github.com/open-telemetry/opentelemetry-demo/pull/1275))
* [currencyservice] bring back multistage build
  ([#1276](https://github.com/open-telemetry/opentelemetry-demo/pull/1276))
* fix env var for pinning trace-based test tool version
  ([#1283](https://github.com/open-telemetry/opentelemetry-demo/pull/1283))
* [accountingservice] Add additional attributes to Kafka spans
  ([#1286](https://github.com/open-telemetry/opentelemetry-demo/pull/1286))
* [shippingservice] update Rust OTel libraries to 0.21
  ([#1287](https://github.com/open-telemetry/opentelemetry-demo/pull/1287))

## 1.6.0

* update PHP quoteservice to use RC1
  ([#1114](https://github.com/open-telemetry/opentelemetry-demo/pull/1114))
* [cartservice] update .NET package to 1.6.0 release
  ([#1115](https://github.com/open-telemetry/opentelemetry-demo/pull/1115))
* Set metric description to blank for rpc.server.duration and queueSize
  ([#1120](https://github.com/open-telemetry/opentelemetry-demo/pull/1120))
* sluggify Grafana dashboard name
  ([#1121](https://github.com/open-telemetry/opentelemetry-demo/pull/1121))
* [kafka frauddetection adservice] update java agent versions
  ([#1132](https://github.com/open-telemetry/opentelemetry-demo/pull/1132))
* update dependent components to latest versions
  ([#1146](https://github.com/open-telemetry/opentelemetry-demo/pull/1146))
* [prometheus] Enabled support for the OTLP write receiver
  ([#1149](https://github.com/open-telemetry/opentelemetry-demo/pull/1149))
* [grafana] fix dashboard metric names and update settings
  ([#1150](https://github.com/open-telemetry/opentelemetry-demo/pull/1150))
* [otelcol] add httpcheck receiver for synthetic check of frontendproxy
  ([#1162](https://github.com/open-telemetry/opentelemetry-demo/pull/1162))
* pinning trace-based test tool version and adding files as volumes
  ([#1182](https://github.com/open-telemetry/opentelemetry-demo/pull/1182))
* [jaeger] fix Jager SPM / Monitor support
  ([#1174](https://github.com/open-telemetry/opentelemetry-demo/pull/1174))
* [otelcol] merge configuration files for base and observability configs
  ([#1173](https://github.com/open-telemetry/opentelemetry-demo/pull/1173))
* [frontendproxy] Fix service graph by enabling client spans in envoy proxy
  ([#1180](https://github.com/open-telemetry/opentelemetry-demo/pull/1180))
* [java-services] Update java, gradle and OTel agent versions
  ([#1183](https://github.com/open-telemetry/opentelemetry-demo/pull/1183))
* [opensearch] Add OpenSearch as an OTLP Logging backend
  ([#1151](https://github.com/open-telemetry/opentelemetry-demo/pull/1151))
* [opensearch] Add Grafana dashboard panels for OpenSearch log data
  ([#1193](https://github.com/open-telemetry/opentelemetry-demo/pull/1193))
* [go-sdk] Workaround: disable gRPC metrics in Go services
  ([#1205](https://github.com/open-telemetry/opentelemetry-demo/pull/1205))

## 1.5.0

* update trace-based tests to test stream events
  ([#1072](https://github.com/open-telemetry/opentelemetry-demo/pull/1072))
* Add cartServiceFailure feature flag triggering Cart Service errors
  ([#824](https://github.com/open-telemetry/opentelemetry-demo/pull/824))
* [paymentservice] update JS SDKs to 1.12.0/0.38.0
  ([#853](https://github.com/open-telemetry/opentelemetry-demo/pull/853))
* [frontend] update JS SDKs to 1.12.0/0.38.0
  ([#853](https://github.com/open-telemetry/opentelemetry-demo/pull/853))
* [chore] use `otel-demo` namespace for generated kubernetes manifests
  ([#848](https://github.com/open-telemetry/opentelemetry-demo/pull/848))
* [collector] update collector version to 0.76.1 and remove connectors feature gate.
  ([#857](https://github.com/open-telemetry/opentelemetry-demo/pull/857))
* [shippingservice] update rust version and dependencies
  ([#865](https://github.com/open-telemetry/opentelemetry-demo/pull/865))
* [load generator] Bump loagen dependencies
  ([#869](https://github.com/open-telemetry/opentelemetry-demo/pull/869))
* [grafana] fix demo dashboard to be compatible with spanmetrics connector
  ([#874](https://github.com/open-telemetry/opentelemetry-demo/pull/874))
* [quoteservice] enabling batch span processor metrics
  ([#878](https://github.com/open-telemetry/opentelemetry-demo/pull/878))
* [kafka] remove KRaft mode support workarounds
  ([#880](https://github.com/open-telemetry/opentelemetry-demo/pull/880))
* [currencyservice] Fix OTel C++ build and update OTel version to 1.9.0
  ([#886](https://github.com/open-telemetry/opentelemetry-demo/pull/886))
* [featureflagservice] Upgrade opentelemetry_ecto to 1.1.1
  ([#899](https://github.com/open-telemetry/opentelemetry-demo/pull/899))
* [currencyservice] Fix OTLP export to use default env vars
  ([#904](https://github.com/open-telemetry/opentelemetry-demo/pull/904))
* [featureflagservice] Bump OTP version to 26.0
  ([#903](https://github.com/open-telemetry/opentelemetry-demo/pull/903))
* Regenerate kubernetes manifest and add auto-generate comment
  ([#909](https://github.com/open-telemetry/opentelemetry-demo/pull/909))
* [loadgenerator] fix redirect on recommendations load
  ([#913](https://github.com/open-telemetry/opentelemetry-demo/pull/913))
* [loadgenerator] run load through frontend proxy (Envoy)
  ([#914](https://github.com/open-telemetry/opentelemetry-demo/pull/914))
* [cartservice] update .NET package to 1.5.0 release
  ([#935](https://github.com/open-telemetry/opentelemetry-demo/pull/935))
* [cartservice] update service to .NET 7
  ([#942](https://github.com/open-telemetry/opentelemetry-demo/pull/942))
* [tests] Add trace-based testing examples
  ([#877](https://github.com/open-telemetry/opentelemetry-demo/pull/877))
* Introduce minimal mode to run demo
  ([#872](https://github.com/open-telemetry/opentelemetry-demo/pull/872))
* [frontendproxy]Envoy expose a route for the collector to route frontend spans
  ([#938](https://github.com/open-telemetry/opentelemetry-demo/pull/938))
* [frontend] update JS SDKs to 1.15.0/0.41.0
  ([#853](https://github.com/open-telemetry/opentelemetry-demo/pull/853))
* [shippingservice] Update Rust dependencies and add TelemetryResourceDetector
  ([#972](https://github.com/open-telemetry/opentelemetry-demo/pull/972))
* Update frontendproxy's env for minimal
  ([#983](https://github.com/open-telemetry/opentelemetry-demo/pull/983))
* [FeatureFlagService] Update dependencies
  ([#992](https://github.com/open-telemetry/opentelemetry-demo/pull/992))
* [currencyService] Update OTel dependency
  ([#991](https://github.com/open-telemetry/opentelemetry-demo/pull/991))
* [LoadGenerator & RecommendatationService] update dependencies
  ([#988](https://github.com/open-telemetry/opentelemetry-demo/pull/988))
* [FraudDetectionService] Updated Kotlin version and OTel dependencies
  ([#987](https://github.com/open-telemetry/opentelemetry-demo/pull/987))
* [quoteservice] update php dependencies
  ([#1009](https://github.com/open-telemetry/opentelemetry-demo/pull/1009))
* [tests] Update trace-based tests run script
  ([#1018](https://github.com/open-telemetry/opentelemetry-demo/pull/1018))
* [PaymentService] Update node to LTS version and bump deps
  ([#1029](https://github.com/open-telemetry/opentelemetry-demo/pull/1029))
* [frontend] Update dependencies
  ([#1054](https://github.com/open-telemetry/opentelemetry-demo/pull/1054))
* [frontendproxy] Fix typo URL endpoint for FrontendProxy
  ([#1075](https://github.com/open-telemetry/opentelemetry-demo/pull/1075))
* [checkoutservice] Upgrade Shopify/sarama to IBM/sarama
  ([#1083](https://github.com/open-telemetry/opentelemetry-demo/pull/1083))
* [accountingservice] Upgrade Shopify/sarama to IBM/sarama
  ([#1083](https://github.com/open-telemetry/opentelemetry-demo/pull/1083))
* Update Telemetry Components
  ([#1085](https://github.com/open-telemetry/opentelemetry-demo/pull/1085))
* [cartservice] Support for logs
  ([#1086](https://github.com/open-telemetry/opentelemetry-demo/pull/1086))
* [TraceTests] Update span attributes to align with new IBM/sarama instrumentation
  ([#1096](https://github.com/open-telemetry/opentelemetry-demo/pull/1096))

## 1.4.0

* [cart] use 60m TTL for cart entries in redis
  ([#779](https://github.com/open-telemetry/opentelemetry-demo/pull/779))
* spanmetrics dashboard service&operation rates & latencies
  ([#787](https://github.com/open-telemetry/opentelemetry-demo/pull/787))
* Adds Kubernetes manifests for the demo
  ([#791](https://github.com/open-telemetry/opentelemetry-demo/pull/791))
* [bug] fixing quoteservice metrics exporting (PHP)
  ([#793](https://github.com/open-telemetry/opentelemetry-demo/pull/793))
* Added app.session.id attribute to frontend spans
  ([#795](https://github.com/open-telemetry/opentelemetry-demo/pull/795))
* Add logs for Ad service and Recommendation service
  ([#796](https://github.com/open-telemetry/opentelemetry-demo/pull/796))
* Opentelemetry Collector Data Flow Dashboard
  ([#797](https://github.com/open-telemetry/opentelemetry-demo/pull/797))
* Fixed shipping update in the frontend UI when number of products in cart
  changes
  ([#799](https://github.com/open-telemetry/opentelemetry-demo/pull/799))
* Update frontend JavaScript SDKs to: 1.10.1/0.36.x
  ([#805](https://github.com/open-telemetry/opentelemetry-demo/pull/805))
* Fix http.status_code on error in frontend
  ([#810](https://github.com/open-telemetry/opentelemetry-demo/pull/810))
* Fix bug in shipping calculation
  ([#814](https://github.com/open-telemetry/opentelemetry-demo/pull/814))
* Reduce Kafka mem allocation
  ([#798](https://github.com/open-telemetry/opentelemetry-demo/pull/798))
* Updated frontend web tracer to us batch processor
  ([#819](https://github.com/open-telemetry/opentelemetry-demo/pull/819))
* Moved env platform flag to the footer, changed it to free text
  ([#818](https://github.com/open-telemetry/opentelemetry-demo/pull/818))
* Update OTel Collector
  ([#822](https://github.com/open-telemetry/opentelemetry-demo/pull/822))
* Update OTel Collector to use spanmetrics connector instead of spanmetrics
  processors
  ([#829](https://github.com/open-telemetry/opentelemetry-demo/pull/829))

## 1.3.1

* [docs] Drop docs folder as step in migration to OTel website
  ([#729](https://github.com/open-telemetry/opentelemetry-demo/issues/729))
* rename proto package from hipstershop to oteldemo
  ([#740](https://github.com/open-telemetry/opentelemetry-demo/pull/740))
* Removed unnecessary code from Program.cs
  ([#754](https://github.com/open-telemetry/opentelemetry-demo/pull/754))
* feature flag service: update the dependency tls_certificate_check and bump to
  OTP-25 ([#756](https://github.com/open-telemetry/opentelemetry-demo/pull/756))
* Bump up OTEL Java Agent version to 1.23.0
  ([#757](https://github.com/open-telemetry/opentelemetry-demo/pull/757))
* Add counter metric to currency service (C++)
  ([#759](https://github.com/open-telemetry/opentelemetry-demo/issues/759))
* Use browserDetector to populate browser info to frontend-web telemetry
  ([#760](https://github.com/open-telemetry/opentelemetry-demo/pull/760))
* [chore] update for Mac M2 architecture
  ([#764](https://github.com/open-telemetry/opentelemetry-demo/pull/764))
* [chore] align memory limits with Helm chart
  ([#781](https://github.com/open-telemetry/opentelemetry-demo/pull/781))
* Use an async PHP runtime, bump versions to latest betas
  ([#823](https://github.com/open-telemetry/opentelemetry-demo/pull/823))

## 1.3.0

* Use `frontend-web` as service name for browser/web requests
([#628](https://github.com/open-telemetry/opentelemetry-demo/pull/628))
* Update `quoteservice` to use opentelemetry-php beta release
([#644](https://github.com/open-telemetry/opentelemetry-demo/pull/644))
* Add build for arm64 arch
([#644](https://github.com/open-telemetry/opentelemetry-demo/pull/657))
* Add synthetic attribute flag to front end instrumentation
([#631](https://github.com/open-telemetry/opentelemetry-demo/pull/631))
* Fix the total sum on the cart page
([#633](https://github.com/open-telemetry/opentelemetry-demo/pull/633))
* Add OTel java agent with JMX Metric Insights to kafka
([#654](https://github.com/open-telemetry/opentelemetry-demo/pull/654))
* Add resource detectors to payment service
([#651](https://github.com/open-telemetry/opentelemetry-demo/pull/651))
* Add resource detectors to frontend service
([#648](https://github.com/open-telemetry/opentelemetry-demo/pull/648))
* Add Jaeger-SPM-Config
([#655](https://github.com/open-telemetry/opentelemetry-demo/pull/655))
* Add healthcheck to featureflagservice
([#661](https://github.com/open-telemetry/opentelemetry-demo/pull/661)
* Add resource detectors to checkout service
([#662](https://github.com/open-telemetry/opentelemetry-demo/pull/662))
* Add resource detectors to cart service
([#663](https://github.com/open-telemetry/opentelemetry-demo/pull/663))
* Add `OTEL_RESOURCE_ATTRIBUTES` to docker compose setup
([#664](https://github.com/open-telemetry/opentelemetry-demo/pull/664))
* Update loadgenerator python base image and dependencies
([#669](https://github.com/open-telemetry/opentelemetry-demo/pull/669))
* Add basic metric support to productcatalog service
([#674](https://github.com/open-telemetry/opentelemetry-demo/pull/674))
* Add resource detectors to accounting service
([#676](https://github.com/open-telemetry/opentelemetry-demo/pull/676))
* Add resource detectors to product catalog service
([#677](https://github.com/open-telemetry/opentelemetry-demo/pull/677))
* Add custom metrics to ads service
([#678](https://github.com/open-telemetry/opentelemetry-demo/pull/678))
* Rebuild currency service Dockerfile with alpine
([#687](https://github.com/open-telemetry/opentelemetry-demo/pull/687))
* Remove grpc from loadgenerator
([#688](https://github.com/open-telemetry/opentelemetry-demo/pull/688))
* Update docker-compose services to restart unless stopped
([#690](https://github.com/open-telemetry/opentelemetry-demo/pull/690))
* Use different docker base images for frauddetection service
([#691](https://github.com/open-telemetry/opentelemetry-demo/pull/691))
* Fix payment service version to support temporality environment variable
([#693](https://github.com/open-telemetry/opentelemetry-demo/pull/693))
* Update recommendationservice python base image and dependencies
([#700](https://github.com/open-telemetry/opentelemetry-demo/pull/700))
* Add adServiceFailure feature flag triggering Ad Service errors
([#694](https://github.com/open-telemetry/opentelemetry-demo/pull/694))
* Reduce spans generated from quote service
([#702](https://github.com/open-telemetry/opentelemetry-demo/pull/702))
* Update emailservice Dockerfile to use alpine and multistage build
([#703](https://github.com/open-telemetry/opentelemetry-demo/pull/703))
* Update dockerfile for adservice to use different base images
([#705](https://github.com/open-telemetry/opentelemetry-demo/pull/705))
* Enable exemplar support in the metrics exporter, Prometheus, and Grafana
([#704](https://github.com/open-telemetry/opentelemetry-demo/pull/704))
* Add cross-compilation for shipping service
([#715](https://github.com/open-telemetry/opentelemetry-demo/issues/715))

## 1.2.0

* Change ZipCode data type from int to string
([#587](https://github.com/open-telemetry/opentelemetry-demo/pull/587))
* Pass product's `categories` as an input for the Ad service
([#600](https://github.com/open-telemetry/opentelemetry-demo/pull/600))
* Add HTTP client instrumentation to shippingservice
([#610](https://github.com/open-telemetry/opentelemetry-demo/pull/610))
* Added Kafka, accountingservice and frauddetectionservice for async workflows
([#512](https://github.com/open-telemetry/opentelemetry-demo/pull/457))
* Added support for non-root containers
([#615](https://github.com/open-telemetry/opentelemetry-demo/pull/615))
* Add tracing to Envoy (frontend-proxy)
([#613](https://github.com/open-telemetry/opentelemetry-demo/pull/613))
* Build Kafka image
([#617](https://github.com/open-telemetry/opentelemetry-demo/pull/617))

## v1.1.0

* Replaced PHP-CLI to PHP-Apache for a more realistic service
([#563](https://github.com/open-telemetry/opentelemetry-demo/pull/563))
* Optimize currencyservice build time with parallel build jobs
([#569](https://github.com/open-telemetry/opentelemetry-demo/pull/569))
* Optimize GitHub Builds and fix broken emulation of featureflag
([#536](https://github.com/open-telemetry/opentelemetry-demo/pull/536))
* Add basic metrics support for payment service
([#583](https://github.com/open-telemetry/opentelemetry-demo/pull/583))

## v1.0.0

* Add component owners for adservice Java app by @trask in
  ([519](https://github.com/open-telemetry/opentelemetry-demo/pull/519))
* Add gradle wrapper validation by @trask in
  ([518](https://github.com/open-telemetry/opentelemetry-demo/pull/518))
* fix currency bug by @cartersocha in
  ([522](https://github.com/open-telemetry/opentelemetry-demo/pull/522))
* Final Docs Review by @austinlparker in
  ([515](https://github.com/open-telemetry/opentelemetry-demo/pull/515))
* Front End -> Frontend by @austinlparker in
  ([537](https://github.com/open-telemetry/opentelemetry-demo/pull/537))
* [docs] kubernetes by @puckpuck in
  ([521](https://github.com/open-telemetry/opentelemetry-demo/pull/521))
* bump to v1.0 for release by @austinlparker in
  ([538](https://github.com/open-telemetry/opentelemetry-demo/pull/538))

## v0.7.0-beta

* Update shippingservice to add resource data to spans
([#504](https://github.com/open-telemetry/opentelemetry-demo/pull/504))
* Add Envoy as reverse proxy for all user-facing services
([#508](https://github.com/open-telemetry/opentelemetry-demo/pull/508))
* Envoy: Grafana, Load Generator, Jaeger exposed.
([#513](https://github.com/open-telemetry/opentelemetry-demo/pull/513))
* Added frontend instrumentation exporter custom url
([#512](https://github.com/open-telemetry/opentelemetry-demo/pull/512))

## v0.6.1-beta

* Set resource memory limits for all services
([#460](https://github.com/open-telemetry/opentelemetry-demo/pull/460))
* Added cache scenario to recommendation service
([#455](https://github.com/open-telemetry/opentelemetry-demo/pull/455))
* Update cartservice Dockerfile to support ARM64
([#439](https://github.com/open-telemetry/opentelemetry-demo/pull/439))

## v0.6.0-beta

* Added basic metrics support for recommendation service (Python)
([#416](https://github.com/open-telemetry/opentelemetry-demo/pull/416))
* Added metrics auto-instrumentation + minor metrics refactor for recommendation
 service (Python)
 [#432](https://github.com/open-telemetry/opentelemetry-demo/pull/432)
* Replaced the Jaeger exporter to the OTLP exporter in the OTel Collector
([#435](https://github.com/open-telemetry/opentelemetry-demo/pull/435))

## v0.5.0

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

## v0.4.0

* Add span events to shipping service
([#344](https://github.com/open-telemetry/opentelemetry-demo/pull/344))
* Add PHP quote service
([#345](https://github.com/open-telemetry/opentelemetry-demo/pull/345))
* Improve initial run time, without a build
([#362](https://github.com/open-telemetry/opentelemetry-demo/pull/362))

## v0.3.0

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

## v0.2.0

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

## v0.1.0

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
