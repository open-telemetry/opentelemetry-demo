# Forking this Repository

This repository is designed to be forked and used as a tool to show off what you
are doing with OpenTelemetry.

Setting up a fork or a demo usually only requires overriding some environment
variables and possibly replacing some container images.

Live demos can be added to the [README](https://github.com/open-telemetry/opentelemetry-demo/blob/main/README.md?plain=1#L186)

## Building Custom Images

Docker Compose uses  `IMAGE_VERSION`  and `IMAGE_NAME` from `.env`  to tag all
images. Modify these values in order to push or pull custom images from your
container registry of choice.

## Configuring the Collector

The collector is configured to export traces to jaeger and metrics to prometheus
in
[otelcol-config.yml](https://github.com/open-telemetry/opentelemetry-demo/blob/main/src/otelcollector/otelcol-config.yml)

You may wish to make a copy of
[otelcol-config-extras.yml](https://github.com/open-telemetry/opentelemetry-demo/blob/main/src/otelcollector/otelcol-config-extras.yml)
for your fork and to modify the relevant volume mounts for the collector in
[docker-compose.yaml](https://github.com/open-telemetry/opentelemetry-demo/blob/main/docker-compose.yml)

## Configuring the Collector [Helm/Kubernetes]

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

## Image Overrides [Helm/Kubernetes]

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
