## Developer Guide

So you want to contribute code to this project? Excellent! We're glad you're here. Here's what you need to do.

## Development Environment

You can contribute to this project from a Windows, macOS or Linux machine. The
first step to contributing is ensuring you can run the demo successfully from
your local machine.

On all platforms, the minimum requirements are:

- Docker
- [Docker Compose](https://docs.docker.com/compose/install/#install-compose) v2.0.0+

### Clone Repo

- Clone the Webstore Demo repository:

```shell
git clone https://github.com/open-telemetry/opentelemetry-demo.git
```

### Open Folder

- Navigate to the cloned folder:

```shell
cd opentelemetry-demo/
```

### Gradle Update [Windows Only]

- Navigate to the Java Ad Service folder to install and update Gradle:

```shell
cd .\src\adservice\
.\gradlew installDist
.\gradlew wrapper --gradle-version 7.4.2
```

### Run Docker Compose

- Start the demo (It can take ~20min the first time the command is executed as
  all the images will be build):

```shell
docker compose up -d
```

### Verify the Webstore & the Telemetry

Once the images are built and containers are started you can access:

- Webstore-Proxy (Via Nginx Proxy): http://nginx:90/ (`nginx` DNS name needs to be added )
  - [Defined here](https://github.com/opensearch-project/opentelemetry-demo/blob/079750428f1bddf16c029f30f478396e45559fec/.env#L58)
- Webstore: http://frontend:8080/ (`frontend` DNS name needs to be added )
  - [Defined here](https://github.com/opensearch-project/opentelemetry-demo/blob/079750428f1bddf16c029f30f478396e45559fec/.env#L63)
- Dashboards: http://dashboards:5061/ (`dashboards` DNS name needs to be added )
- Feature Flags UI: http://featureflag:8881/ (`featureflag` DNS name needs to be added )
  - [Defined here](https://github.com/opensearch-project/opentelemetry-demo/blob/079750428f1bddf16c029f30f478396e45559fec/.env#LL47C31-L47C31)
- Load Generator UI: http://loadgenerator:8089/ (`loadgenerator` DNS name needs to be added)
  - [Defined here](https://github.com/opensearch-project/opentelemetry-demo/blob/079750428f1bddf16c029f30f478396e45559fec/.env#L66)

OpenSearch has [documented](https://opensearch.org/docs/latest/observing-your-data/trace/trace-analytics-jaeger/#setting-up-opensearch-to-use-jaeger-data) the usage of the Observability plugin with jaeger as a trace signal source.


### Review the Documentation

The Demo team is committed to keeping the demo up to date. That means the
documentation as well as the code. When making changes to any service or feature
remember to find the related docs and update those as well. Most (but not all)
documentation can be found on the OTel website under [Demo docs][docs].

