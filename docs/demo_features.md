# Features

- **[Kubernetes](https://kubernetes.io)**: the app is designed to run on
  Kubernetes (both locally, as well as on the cloud) using a Helm chart.
- **[Docker](https://docs.docker.com)**: this forked sample can also be executed
  only with Docker.
- **[gRPC](https://grpc.io)**: microservices use a high volume of gRPC calls to
  communicate to each other.
- **[HTTP](https://www.rfc-editor.org/rfc/rfc9110.html)**: microservices use HTTP
  where gRPC is unavailable or not well supported.
- **[OpenTelemetry Traces](https://opentelemetry.io)**: all services are
  instrumented using OpenTelemetry available instrumentation libraries.
- **[OpenTelemetry Metrics](https://opentelemetry.io)**: Select services are
instrumented using OpenTelemetry available instrumentation libraries. More will
be added as the relevant SDKs are released.
- **[OpenTelemetry
  Collector](https://opentelemetry.io/docs/collector/getting-started)**: all
  services are instrumented and sending the generated traces and metrics to the
  OpenTelemetry Collector via gRPC. The received traces are then exported to the
  logs and to Jaeger.
- **[Jaeger](https://www.jaegertracing.io)**: all generated traces are being
  sent to Jaeger.
- **Synthetic Load Generation**: the application demo comes with a background
  job that creates realistic usage patterns on the website using
  [Locust](https://locust.io/) load generator.
- **[Prometheus](https://prometheus.io/)**: all generated metrics are scraped by
  Prometheus.
- **[Grafana](https://grafana.com/)**: all metric dashboards are stored in
  Grafana.
- **[Envoy](https://www.envoyproxy.io/)**: Envoy is used as a reverse proxy for
  user-facing web interfaces such as the frontend, load generator, and feature
  flag service.
