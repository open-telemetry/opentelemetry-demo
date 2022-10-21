# Kubernetes

We provide a [OpenTelemetry Demo Helm
chart](https://github.com/open-telemetry/opentelemetry-helm-charts/tree/main/charts/opentelemetry-demo)
to help deploy the demo to an existing Kubernetes cluster.

[Helm](https://helm.sh) must be installed to use the charts.
Please refer to Helm's [documentation](https://helm.sh/docs/) to get started.

## Prerequisites

- Pre-existing Kubernetes Cluster
- Helm 3.0+

## Install the Chart

Add OpenTelemetry Helm repository:

```console
helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
```

To install the chart with the release name my-otel-demo, run the following command:

```console
helm install my-otel-demo open-telemetry/opentelemetry-demo
```

## Verify the Webstore & the Telemetry

In order to use the demo services deployed in a Kubernetes cluster, the services
must be exposed. You can do this using the `kubectl port-forward` command, or by
exposing the services using different service types (ie: LoadBalancer) with
optional ingress routes.

### Using kubectl port-forward to expose services

You will need to expose each service individually using the
- Frontend UI: http://localhost:8080
  by running these commands:
  kubectl port-forward svc/{{ include "otel-demo.name" . }}-frontend 8080:8080

{{- if $.Values.observability.jaeger.enabled }}

- Jaeger UI: http://localhost:16686
  by running these commands:
  kubectl port-forward svc/{{ include "otel-demo.name" . }}-jaeger 16686:16686
  {{- end }}

{{- if $.Values.observability.grafana.enabled }}

- Grafana UI: http://localhost:3000
  by running these commands:
  kubectl port-forward svc/{{ include "otel-demo.name" . }}-grafana 3000:3000
  {{- end }}

- Locust (load generator) UI: http://localhost:8089
  by running these commands:
  kubectl port-forward svc/{{ include "otel-demo.name" . }}-loadgenerator 8089:8089

- Feature Flag Service UI: http://localhost:8081
  by running these commands:
  kubectl port-forward svc/{{ include "otel-demo.name" . }}-featureflagservice 8081:8081

- OpenTelemetry Collector OTLP/HTTP receiver (required for browser spans to be emitted):
  by running these commands:
  kubectl port-forward svc/{{ include "otel-demo.name" . }}-otelcol 4318:4318
