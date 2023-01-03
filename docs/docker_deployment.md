# Docker

## Prerequisites

- Docker
- [Docker Compose](https://docs.docker.com/compose/install/#install-compose) v2.0.0+
- 5 GB of RAM

## Clone Repo

- Clone the Webstore Demo repository:

```shell
git clone https://github.com/open-telemetry/opentelemetry-demo.git
```

## Open Folder

- Navigate to the cloned folder:

```shell
cd opentelemetry-demo/
```

## Run Docker Compose

- Start the demo:

```shell
docker compose up --no-build
```

> **Note:** If you're running on Apple Silicon, please run `docker compose
> build` in order to create local images vs. pulling them from the repository.

**Note:** The `--no-build` flag is used to fetch released docker images from
[ghcr](http://ghcr.io/open-telemetry/demo) instead of building from source.
Removing the `--no-build` command line option will rebuild all images from
source. It may take more than 20 minutes to build if the flag is omitted.

## Verify the Webstore & the Telemetry

Once the images are built and containers are started you can access:

- Webstore: <http://localhost:8080/>
- Grafana: <http://localhost:8080/grafana/>
- Feature Flags UI: <http://localhost:8080/feature/>
- Load Generator UI: <http://localhost:8080/loadgen/>
- Jaeger UI: <http://localhost:8080/jaeger/ui/>

## Bring your own backend

Likely you want to use the Webstore as a demo application for an observability
backend you already have (e.g. an existing instance of Jaeger, Zipkin, or one
of the [vendor of your choice](https://opentelemetry.io/vendors/).

OpenTelemetry Collector can be used to export telemetry data to multiple
backends. By default, the collector in the demo application will merge the
configuration from two files:

- otelcol-config.yml
- otelcol-config-extras.yml

To add your backend, open the file
[src/otelcollector/otelcol-config-extras.yml](../src/otelcollector/otelcol-config-extras.yml)
with an editor.

- Start by adding a new exporter. For example, if your backend supports
  OTLP over HTTP, add the following:

```yaml
exporters:
  otlphttp/example:
    endpoint: <your-endpoint-url>
```

- Then add a new pipeline with your new exporter:

```yaml
service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlphttp/example]
```

Vendor backends might require you to add additional parameters for
authentication, please check their documentation. Some backends require
different exporters, you may find them and their documentation available at
[opentelemetry-collector-contrib/exporter](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/exporter).

After updating the `otelcol-config-extras.yml`, start the demo by running
`docker compose up`. After a while, you should see the traces flowing into
your backend as well.
