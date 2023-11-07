# OTEL Collector Pipeline

The next diagram describes the Observability signals pipeline defined inside the OTEL collector

```mermaid
%%{
  init: {
    'theme': 'base',
    'themeVariables': {
      'primaryColor': '#BB2528',
      'primaryTextColor': '#fff',
      'primaryBorderColor': '#7C0000',
      'lineColor': '#F8B229',
      'secondaryColor': '#006100',
      'tertiaryColor': '#fff'
    }
  }
}%%

graph LR
    otlp-->otlpReceiverTraces["otlp Receiver"]
    style otlpReceiverTraces fill:#f9d,stroke:#333,stroke-width:4px
    otlp-->otlpReceiverMetrics["otlp Receiver"]
    style otlpReceiverMetrics fill:#f9d,stroke:#333,stroke-width:4px
    otlp-->otlpReceiverLogs["otlp Receiver"]
    style otlpReceiverLogs fill:#f9d,stroke:#333,stroke-width:4px
    otlpServiceGraph-->otlpServiceGraphReceiver["otlp/servicegraph Receiver"]
    spanmetrics-->spanmetricsReceiver["spanmetrics Receiver"]

    subgraph Traces Pipeline
    otlpReceiverTraces-->tracesProcessor["Traces Processor"]
    style tracesProcessor fill:#9cf,stroke:#333,stroke-width:4px
    tracesProcessor-->otlpExporter["otlp Exporter"]
    tracesProcessor-->loggingExporterTraces["Logging Exporter"]

    tracesProcessor-->spanmetricsExporter["Spanmetrics Exporter"]
    tracesProcessor-->otlp2Exporter["otlp/2 Exporter"]
    end
    
    subgraph Metrics/Servicegraph Pipeline
    otlpServiceGraphReceiver-->metricsServiceGraphProcessor["Metrics/ServiceGraph Processor"]
    style otlpServiceGraphReceiver fill:#f9d,stroke:#333,stroke-width:4px
    metricsServiceGraphProcessor-->prometheusServiceGraphExporter["Prometheus/ServiceGraph Exporter"]
    style metricsServiceGraphProcessor fill:#9cf,stroke:#333,stroke-width:4px
    end
    
    subgraph Metrics Pipeline
    otlpReceiverMetrics-->metricsProcessor["Metrics Processor"]
    style metricsProcessor fill:#9cf,stroke:#333,stroke-width:4px

    spanmetricsReceiver-->metricsProcessor
    style spanmetricsReceiver fill:#f9d,stroke:#333,stroke-width:4px
    metricsProcessor-->prometheusExporter["Prometheus Exporter"]
    metricsProcessor-->loggingExporterMetrics["Logging Exporter"]
    end

    subgraph Logs Pipeline
    otlpReceiverLogs-->logsProcessor["Logs Processor"]
    style logsProcessor fill:#9cf,stroke:#333,stroke-width:4px
    logsProcessor-->loggingExporterLogs["Logging Exporter"]
    end


```

### Traces
The traces  pipeline consists of a receiver, multiple processors, and multiple exporters.

**Receiver (otlp):**
This is where the data comes in from. In your configuration, the traces pipeline is using the otlp receiver. OTLP stands for OpenTelemetry Protocol. This receiver is configured to accept data over both gRPC and HTTP protocols. The HTTP protocol is also configured to allow CORS from any origin.

**Processors (memory_limiter, batch, servicegraph):**
Once the data is received, it is processed before being exported. The processors in the traces pipeline are:

1. **memory_limiter:** This processor checks memory usage every second (check_interval: 1s) and ensures it does not exceed 4000 MiB (limit_mib: 4000). It also allows for a spike limit of 800 MiB (spike_limit_mib: 800).

2. **batch:** This processor batches together traces before sending them on to the exporters, improving efficiency.

3. **servicegraph:** This processor is specifically designed for creating a service graph from the traces. It is configured with certain parameters for handling latency histogram buckets, dimensions, store configurations, and so on.

**Exporters (otlp, logging, spanmetrics, otlp/2):**
After processing, the data is sent to the configured exporters:

1. **otlp:** This exporter sends data to an endpoint configured as jaeger:4317 over OTLP with TLS encryption in insecure mode.

2. **logging:** This exporter logs the traces.

3. **spanmetrics:** This is likely a custom exporter defined as a connector in your configuration. It seems to be designed to create metrics from spans, but this is mostly conjecture based on the name.

4. **otlp/2:** This exporter sends data to an endpoint configured as data-prepper:21890 over OTLP with TLS encryption in insecure mode.

### Metrics
**Metrics Pipeline**

This pipeline handles metric data.

- **Receivers (otlp, spanmetrics):**

Metric data comes in from the `otlp` receiver and the `spanmetrics` receiver.
- **Processors (filter, memory_limiter, batch):**
The data is then processed:
1. **filter:** This processor excludes specific metrics. In this configuration, it is set to strictly exclude the queueSize metric.
2. **memory_limiter:** Similar to the traces pipeline, this processor ensures memory usage doesn't exceed a certain limit.
3. **batch:** This processor batches together metrics before sending them to the exporters, enhancing efficiency.

- **Exporters (prometheus, logging):**
The processed data is then exported:
1. **prometheus:** This exporter sends metrics to an endpoint configured as
2. **otelcol:9464**. It also converts resource information to Prometheus labels and enables OpenMetrics.
3. **logging:** This exporter logs the metrics.

### Logs

**Logs Pipeline**

This pipeline handles log data.

- **Receiver (otlp):**

    Log data comes in from the otlp receiver. 
- **Processors (memory_limiter, batch):**
The data is then processed:
1. **memory_limiter:** Similar to the traces and metrics pipelines, this processor ensures memory usage doesn't exceed a certain limit.
2. **batch:** This processor batches together logs before sending them to the exporter, enhancing efficiency.

- **Exporter (logging):**

The processed data is then exported:
 -  Logs Pipeline
