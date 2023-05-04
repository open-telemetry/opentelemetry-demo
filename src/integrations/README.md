# OpenSearch Integrations

This service runs after the OpenSearch cluster and dashboard services have started.
Its purpose is to setup the necessary assets for the Observability plugin to be able to function as an Observability store and visualizations.

For additional information about how OpenSearch connects to OTEL exporter see [here](https://opensearch.org/docs/latest/observing-your-data/trace/trace-analytics-jaeger/#setting-up-opensearch-to-use-jaeger-data)

## Observability supported features
 - Traces analytics
 - Metrics analytics
 - Logs analytics
 - Monitoring Metrics KPI
 - Loading relevant Integrations (WEB related) for specific pre-canned dashboards  


## Assets that are installed

### Index & mappings
 - create the Logs / Traces / Metrics index template
 - create the Logs / Traces / Metrics data-stream based on these index template

### Datasource
 - setup Prometheus datasource

### Config
 - setup alerts channels (Email/Slack)  

### Monitor
 - setup alerts monitors   

### Dashboards
 - setup dashboards for WEB server logs and metrics 


