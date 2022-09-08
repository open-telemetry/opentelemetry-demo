# Docker

## Pre-requisites

- Docker
- [Docker Compose](https://docs.docker.com/compose/install/#install-compose) v2.0.0+

### Windows Pre-requisites

Run the following shell command to correctly configure file endings:

```shell
git config --global core.autocrlf input
```

If you already cloned the repo and are experiencing build issues then delete and
re-clone the repo after running the command.

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

- Start the demo (it can take ~20min the first time the command is executed as
all the container images will be built):

```shell
docker compose up
```

## Verify the Webstore & the Telemetry

Once the images are built and containers are started you can access:

- Webstore: <http://localhost:8080/>
- Jaeger: <http://localhost:16686/>
- Prometheus: <http://localhost:9090/>
- Grafana: <http://localhost:3000/>
- Feature Flags UI: <http://localhost:8081/>
- Load Generator UI: <http://localhost:8089/>

## Bring your own backend

Likely you want to use the Webstore as a demo application for an observability
backend you already have (e.g. an existing instance of Jaeger, Zipkin or one of
the [vendor of your choice](https://opentelemetry.io/vendors/).

To add your backend open the file
[src/otelcollector/otelcol-config.yml](../src/otelcollector/otelcol-config.yml)
with an editor:

- add a trace exporter for your backend. For example, if your backend supports
  otlp, extend the `exporters` section like the following:

```yaml
exporters:
  jaeger:
    endpoint: "jaeger:14250"
    insecure: true
  logging:
  otlp:
    endpoint: <your-endpoint-url>
```

- add the `otlp` exporter to the `pipelines` section as well:

```yaml
service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [logging, jaeger, otlp]
```

Vendor backends might require you to add additional parameters for
authentication, please check their documentation. Some backends require
different exporters, you may find them and their documentation available at
[opentelemetry-collector-contrib/exporter](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/exporter).

After updating the `otelcol-config.yml` start the demo by running
`docker compose up`. After a while you should see the traces flowing into
your backend as well.
