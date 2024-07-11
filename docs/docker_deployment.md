# Docker

## Prerequisites

- Docker
- [Docker Compose](https://docs.docker.com/compose/install/#install-compose) v2.0.0+
- 5 GB of RAM

## Clone Repo

- Clone the Webstore Demo repository (New Relic):

```shell
git clone https://github.com/newrelic/opentelemetry-demo.git
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
- Load Generator UI: <http://localhost:8080/loadgen/>
- Jaeger UI: <http://localhost:8080/jaeger/ui/>

## Bring your New Relic account

Likely you want to use the Webstore as a demo application for an observability
backend you already have (e.g. an existing instance of Jaeger, Zipkin or
New Relic).

OpenTelemetry Collector can be used to export telemetry data to multiple
backends. By default, the collector in the demo application will merge the
configuration from two files:

- otelcol-config.yml
- otelcol-config-extras.yml

To add your backend, open the file
[src/otelcollector/otelcol-config-extras.yml](../src/otelcollector/otelcol-config-extras.yml)
with an editor.

- A new OTLP exporter for New Relic is already added for you where the
New Relic endpoint and your license key are configured as environment
variables.

```yaml
exporters:
  otlp/newrelic:
    endpoint: ${NEW_RELIC_OTLP_ENDPOINT}
    headers:
      api-key: ${NEW_RELIC_LICENSE_KEY}
```

- Your New Relic exporter above is also already added into your pipeline:

```yaml
service:
  pipelines:
    traces:
      exporters: [otlp/newrelic]
    metrics:
      exporters: [otlp/newrelic]
```

To define your endpoint and your license key, open the file [.env.override](../.env.override).

- Down below the file you will see the New Relic specific variables. Configure
them according to the region which your account is in.

- You can directly copy/paste your license key to `NEW_RELIC_LICENSE_KEY` or
define it in your terminal.

```yaml
### New Relic
# Select corresponding OTLP endpoint depending where your account is.
NEW_RELIC_OTLP_ENDPOINT_US=https://otlp.nr-data.net:4317
NEW_RELIC_OTLP_ENDPOINT_EU=https://otlp.eu01.nr-data.net:4317
NEW_RELIC_OTLP_ENDPOINT=${NEW_RELIC_OTLP_ENDPOINT_US}

# Define license key as environment variable
NEW_RELIC_LICENSE_KEY=${NEW_RELIC_LICENSE_KEY}
```

After updating the `otelcol-config-extras.yml` and `env` files, start the demo
by running `docker compose up`. After a while, you should see the telemetry
data flowing into your New Relic account as well.
