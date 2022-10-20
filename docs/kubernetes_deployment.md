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

## Vendor Forking

Setting up a fork or a demo usually only requires overriding some environment
variables and possibly replacing some container images.

Live demos can be added to the [README](https://github.com/open-telemetry/opentelemetry-demo/blob/main/README.md?plain=1#L186)

### Configuring the Collector [Helm/Kubernetes]

The [helm
charts](https://github.com/open-telemetry/opentelemetry-helm-charts/tree/main/charts/opentelemetry-demo)
allow for easy customization of collector configuration using a custom values
file:

```yaml
opentelemetry-collector:
  config:
    exporters:
      otlp:
        endpoint: "your-otlp-endpoint.com:4317"
        headers:
          "x-vendor-api-key": "YOUR_API_KEY"
    service:
      pipelines:
        metrics:
          exporters:
            - otlp
        traces:
          exporters:
            - otlp
            - jaeger
```

Save this file and pass it into helm:

```shell
helm install opentelemetry-demo
open-telemetry/opentelemetry-demo --values opentelemetry-demo-values.yaml
```

Values provided in this way will be merged with the default values.

### Image Overrides [Helm/Kubernetes]

Each service has a key `imageOverride` which accepts a map of image override
options, for example:

```yaml
components:
  adService:
    imageOverride:
      repository: "my-repo"
      tag: "my-tag"
      pullSecrets: {}
      pullPolicy: Always
```
