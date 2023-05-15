# <img src="https://opentelemetry.io/img/logos/opentelemetry-logo-nav.png" alt="OTel logo" width="32"> + <img src="https://avatars.githubusercontent.com/u/80134844?s=240&v=4" alt="OTel logo" width="35"> OpenTelemetry Demo with OpenSearch 

The following guide describes how to setup the OpenTelemetry demo with OpenSearch Observability using [Docker compose](#docker-compose) or [Kubernetes](#kubernetes).

## Docker compose

OpenSearch has [documented](https://opensearch.org/docs/latest/observing-your-data/trace/trace-analytics-jaeger/#setting-up-opensearch-to-use-jaeger-data) the usage of the Observability plugin with jaeger as a trace signal source.
The next instructions are similar and use the same docker compose file.
1. Start the demo with the following command from the repository's root directory:
   ```
   docker-compose up -d
   ```

### Explore and analyze the data With OpenSearch Observability
Review revised OpenSearch [Observability Architecture](architecture.md)

### Service map
![Service map](https://docs.aws.amazon.com/images/opensearch-service/latest/developerguide/images/ta-dashboards-services.png)

### Traces
![Traces](https://opensearch.org/docs/2.6/images/ta-trace.png)

### Correlation
![Correlation](https://opensearch.org/docs/latest/images/observability-trace.png)

### Logs
![Logs](https://opensearch.org/docs/latest/images/trace_log_correlation.gif)