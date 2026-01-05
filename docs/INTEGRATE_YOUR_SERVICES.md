# Integrate Your Services with Azure Data Explorer

This guide explains how to configure your own applications to send OpenTelemetry data to Azure Data Explorer (ADX) using the patterns from this demo.

## Overview

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Your Services     │     │   OTel Collector    │     │  Azure Data Explorer│
│                     │     │                     │     │                     │
│  ┌───────────────┐  │     │  ┌───────────────┐  │     │  ┌───────────────┐  │
│  │ Service A     │──┼─────┼─►│ OTLP Receiver │──┼─────┼─►│ OTelTraces    │  │
│  │ (Python)      │  │     │  └───────────────┘  │     │  ├───────────────┤  │
│  └───────────────┘  │     │  ┌───────────────┐  │     │  │ OTelMetrics   │  │
│  ┌───────────────┐  │     │  │ ADX Exporter  │  │     │  ├───────────────┤  │
│  │ Service B     │──┼─────┼─►│               │──┼─────┼─►│ OTelLogs      │  │
│  │ (Node.js)     │  │     │  └───────────────┘  │     │  └───────────────┘  │
│  └───────────────┘  │     │                     │     │                     │
│  ┌───────────────┐  │     │                     │     │                     │
│  │ Service C     │──┼─────┤                     │     │                     │
│  │ (Java/.NET)   │  │ OTLP│                     │     │                     │
│  └───────────────┘  │     │                     │     │                     │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

## Prerequisites

- Azure subscription
- Azure Data Explorer cluster (use Terraform from this repo or create manually)
- OpenTelemetry Collector deployed (Kubernetes, Docker, or standalone)
- Service Principal with ADX permissions (Ingestor + Viewer roles)

---

## Step 1: Set Up Azure Data Explorer

### Option A: Use Terraform (Recommended)

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your settings
terraform init && terraform apply
```

This creates:
- ADX cluster with database
- Tables: `OTelTraces`, `OTelMetrics`, `OTelLogs`
- Ingestion mappings
- Service Principal with permissions

### Option B: Manual Setup

1. Create ADX cluster and database in Azure Portal
2. Run the schema script to create tables:

```bash
# Connect to your ADX cluster and run:
# adx/schema.kql
```

The schema creates three tables:

| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `OTelTraces` | Distributed traces | TraceId, SpanId, ServiceName, Duration |
| `OTelMetrics` | Metrics data | MetricName, Value, ServiceName |
| `OTelLogs` | Log entries | SeverityText, Body, ServiceName |

---

## Step 2: Configure OpenTelemetry Collector

### Minimal ADX Configuration

Create `otel-collector-config.yaml`:

```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

exporters:
  azuredataexplorer:
    cluster_uri: ${env:ADX_CLUSTER_URI}
    application_id: ${env:AZURE_CLIENT_ID}
    application_key: ${env:AZURE_CLIENT_SECRET}
    tenant_id: ${env:AZURE_TENANT_ID}
    db_name: ${env:ADX_DATABASE}

    # Table names (must match schema)
    metrics_table_name: "OTelMetrics"
    logs_table_name: "OTelLogs"
    traces_table_name: "OTelTraces"

    # Ingestion mappings (created by schema.kql)
    metrics_table_json_mapping: "otel_metrics_mapping"
    logs_table_json_mapping: "otel_logs_mapping"
    traces_table_json_mapping: "otel_traces_mapping"

    # Use "managed" for low latency, "queued" for high throughput
    ingestion_type: managed

processors:
  batch:
    send_batch_size: 1000
    timeout: 10s

  memory_limiter:
    check_interval: 5s
    limit_percentage: 80

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [azuredataexplorer]

    metrics:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [azuredataexplorer]

    logs:
      receivers: [otlp]
      processors: [memory_limiter, batch]
      exporters: [azuredataexplorer]
```

### Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `ADX_CLUSTER_URI` | ADX cluster endpoint | `https://mycluster.eastus.kusto.windows.net` |
| `ADX_DATABASE` | Database name | `otel_demo` |
| `AZURE_TENANT_ID` | Azure AD tenant | `12345678-1234-...` |
| `AZURE_CLIENT_ID` | Service Principal app ID | `87654321-4321-...` |
| `AZURE_CLIENT_SECRET` | Service Principal secret | `your-secret` |

---

## Step 3: Instrument Your Services

### Python

```bash
pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
```

```python
from opentelemetry import trace, metrics
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export.batch import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource

# Configure resource (identifies your service)
resource = Resource.create({
    "service.name": "my-python-service",
    "service.version": "1.0.0",
    "deployment.environment": "production"
})

# Set up tracing
trace.set_tracer_provider(TracerProvider(resource=resource))
tracer_provider = trace.get_tracer_provider()

# Export to OTel Collector
otlp_exporter = OTLPSpanExporter(
    endpoint="http://otel-collector:4317",  # Your collector endpoint
    insecure=True
)
tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))

# Use in your code
tracer = trace.get_tracer(__name__)

@tracer.start_as_current_span("process_order")
def process_order(order_id):
    # Your business logic
    pass
```

### Node.js / TypeScript

```bash
npm install @opentelemetry/api @opentelemetry/sdk-node @opentelemetry/exporter-trace-otlp-grpc
```

```javascript
const { NodeSDK } = require('@opentelemetry/sdk-node');
const { OTLPTraceExporter } = require('@opentelemetry/exporter-trace-otlp-grpc');
const { Resource } = require('@opentelemetry/resources');
const { SemanticResourceAttributes } = require('@opentelemetry/semantic-conventions');

const sdk = new NodeSDK({
  resource: new Resource({
    [SemanticResourceAttributes.SERVICE_NAME]: 'my-node-service',
    [SemanticResourceAttributes.SERVICE_VERSION]: '1.0.0',
  }),
  traceExporter: new OTLPTraceExporter({
    url: 'http://otel-collector:4317',
  }),
});

sdk.start();

// Use in your code
const { trace } = require('@opentelemetry/api');
const tracer = trace.getTracer('my-node-service');

function processOrder(orderId) {
  return tracer.startActiveSpan('process_order', (span) => {
    try {
      // Your business logic
      span.setAttribute('order.id', orderId);
    } finally {
      span.end();
    }
  });
}
```

### Java (Spring Boot)

```xml
<!-- pom.xml -->
<dependency>
    <groupId>io.opentelemetry</groupId>
    <artifactId>opentelemetry-api</artifactId>
</dependency>
<dependency>
    <groupId>io.opentelemetry</groupId>
    <artifactId>opentelemetry-sdk</artifactId>
</dependency>
<dependency>
    <groupId>io.opentelemetry</groupId>
    <artifactId>opentelemetry-exporter-otlp</artifactId>
</dependency>
```

Or use the Java Agent (zero-code instrumentation):

```bash
java -javaagent:opentelemetry-javaagent.jar \
     -Dotel.service.name=my-java-service \
     -Dotel.exporter.otlp.endpoint=http://otel-collector:4317 \
     -jar my-app.jar
```

### .NET

```bash
dotnet add package OpenTelemetry.Exporter.OpenTelemetryProtocol
```

```csharp
using OpenTelemetry;
using OpenTelemetry.Trace;
using OpenTelemetry.Resources;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddOpenTelemetry()
    .ConfigureResource(resource => resource
        .AddService("my-dotnet-service", serviceVersion: "1.0.0"))
    .WithTracing(tracing => tracing
        .AddAspNetCoreInstrumentation()
        .AddHttpClientInstrumentation()
        .AddOtlpExporter(options =>
        {
            options.Endpoint = new Uri("http://otel-collector:4317");
        }));
```

### Go

```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/sdk/resource"
    "go.opentelemetry.io/otel/sdk/trace"
    semconv "go.opentelemetry.io/otel/semconv/v1.17.0"
)

func initTracer() (*trace.TracerProvider, error) {
    exporter, err := otlptracegrpc.New(ctx,
        otlptracegrpc.WithEndpoint("otel-collector:4317"),
        otlptracegrpc.WithInsecure(),
    )
    if err != nil {
        return nil, err
    }

    tp := trace.NewTracerProvider(
        trace.WithBatcher(exporter),
        trace.WithResource(resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceName("my-go-service"),
            semconv.ServiceVersion("1.0.0"),
        )),
    )
    otel.SetTracerProvider(tp)
    return tp, nil
}
```

---

## Step 4: Deploy the Collector

### Kubernetes Deployment

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: otel-collector-config
  namespace: observability
data:
  config.yaml: |
    # Paste your otel-collector-config.yaml content here
---
apiVersion: v1
kind: Secret
metadata:
  name: adx-credentials
  namespace: observability
type: Opaque
stringData:
  AZURE_TENANT_ID: "your-tenant-id"
  AZURE_CLIENT_ID: "your-client-id"
  AZURE_CLIENT_SECRET: "your-client-secret"
  ADX_CLUSTER_URI: "https://yourcluster.region.kusto.windows.net"
  ADX_DATABASE: "otel_demo"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: otel-collector
  namespace: observability
spec:
  replicas: 1
  selector:
    matchLabels:
      app: otel-collector
  template:
    metadata:
      labels:
        app: otel-collector
    spec:
      containers:
      - name: collector
        image: otel/opentelemetry-collector-contrib:0.96.0
        args:
          - --config=/etc/otel/config.yaml
        ports:
          - containerPort: 4317  # OTLP gRPC
          - containerPort: 4318  # OTLP HTTP
        envFrom:
          - secretRef:
              name: adx-credentials
        volumeMounts:
          - name: config
            mountPath: /etc/otel
      volumes:
        - name: config
          configMap:
            name: otel-collector-config
---
apiVersion: v1
kind: Service
metadata:
  name: otel-collector
  namespace: observability
spec:
  selector:
    app: otel-collector
  ports:
    - name: otlp-grpc
      port: 4317
    - name: otlp-http
      port: 4318
```

### Docker Compose

```yaml
version: '3.8'
services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.96.0
    command: --config=/etc/otel/config.yaml
    volumes:
      - ./otel-collector-config.yaml:/etc/otel/config.yaml
    environment:
      - ADX_CLUSTER_URI=https://yourcluster.region.kusto.windows.net
      - ADX_DATABASE=otel_demo
      - AZURE_TENANT_ID=your-tenant-id
      - AZURE_CLIENT_ID=your-client-id
      - AZURE_CLIENT_SECRET=your-client-secret
    ports:
      - "4317:4317"  # OTLP gRPC
      - "4318:4318"  # OTLP HTTP

  your-service:
    build: .
    environment:
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
      - OTEL_SERVICE_NAME=my-service
    depends_on:
      - otel-collector
```

---

## Step 5: Query Your Data in ADX

Once data flows, query it in Azure Data Explorer:

### Service Health Dashboard

```kql
// RED metrics (Rate, Errors, Duration) for all services
OTelTraces
| where Timestamp > ago(1h)
| where SpanKind == "Server"
| summarize
    Requests = count(),
    Errors = countif(StatusCode == "Error"),
    P50_ms = percentile(Duration / 1000000, 50),
    P95_ms = percentile(Duration / 1000000, 95),
    P99_ms = percentile(Duration / 1000000, 99)
    by ServiceName
| extend ErrorRate = round(100.0 * Errors / Requests, 2)
| order by Requests desc
```

### Find Slow Requests

```kql
OTelTraces
| where Timestamp > ago(1h)
| where Duration > 1000000000  // > 1 second (in nanoseconds)
| project
    Timestamp,
    ServiceName,
    SpanName,
    Duration_ms = Duration / 1000000,
    TraceId
| order by Duration_ms desc
| take 100
```

### Error Analysis

```kql
OTelTraces
| where Timestamp > ago(1h)
| where StatusCode == "Error"
| summarize ErrorCount = count() by ServiceName, SpanName, StatusMessage
| order by ErrorCount desc
```

### Correlate Logs with Traces

```kql
let errorTraces = OTelTraces
| where Timestamp > ago(1h)
| where StatusCode == "Error"
| project TraceId, ServiceName;

OTelLogs
| where Timestamp > ago(1h)
| join kind=inner errorTraces on TraceId
| project Timestamp, ServiceName, SeverityText, Body
| order by Timestamp desc
```

---

## Grafana Integration

Add ADX as a datasource in Grafana:

```yaml
# grafana/provisioning/datasources/adx.yaml
apiVersion: 1
datasources:
  - name: Azure Data Explorer
    type: grafana-azure-data-explorer-datasource
    url: ${ADX_CLUSTER_URI}
    jsonData:
      clusterUrl: ${ADX_CLUSTER_URI}
      tenantId: ${AZURE_TENANT_ID}
      clientId: ${AZURE_CLIENT_ID}
      defaultDatabase: ${ADX_DATABASE}
    secureJsonData:
      clientSecret: ${AZURE_CLIENT_SECRET}
```

Install the ADX plugin:
```bash
grafana-cli plugins install grafana-azure-data-explorer-datasource
```

---

## Best Practices

### 1. Use Resource Attributes

Always set these attributes on your services:

```
service.name        - Unique service identifier
service.version     - Version number
deployment.environment - dev/staging/prod
```

### 2. Batch and Buffer

Configure the collector for reliability:

```yaml
processors:
  batch:
    send_batch_size: 1000
    send_batch_max_size: 2000
    timeout: 10s

exporters:
  azuredataexplorer:
    sending_queue:
      enabled: true
      num_consumers: 10
      queue_size: 5000
    retry_on_failure:
      enabled: true
      initial_interval: 5s
      max_interval: 30s
```

### 3. Use Managed Ingestion for Low Latency

```yaml
exporters:
  azuredataexplorer:
    ingestion_type: managed  # ~30 second latency
```

Use `queued` for high-throughput batch scenarios (higher latency but more efficient).

### 4. Set Appropriate Retention

In ADX, configure retention based on your needs:

```kql
// 1 year retention, 30 days hot cache
.alter table OTelTraces policy retention softdelete = 365d
.alter table OTelTraces policy caching hot = 30d
```

---

## Troubleshooting

### No Data in ADX

1. Check collector logs:
   ```bash
   kubectl logs -l app=otel-collector -n observability
   ```

2. Verify credentials:
   ```bash
   kubectl get secret adx-credentials -o yaml
   ```

3. Test ADX connectivity:
   ```bash
   curl https://yourcluster.region.kusto.windows.net
   ```

### High Latency

- Increase batch size
- Add more collector replicas
- Use `queued` ingestion type

### Missing Traces

- Verify `service.name` is set
- Check OTLP endpoint is reachable from your service
- Ensure sampling is not dropping traces

---

## Support

- [OpenTelemetry Documentation](https://opentelemetry.io/docs/)
- [ADX Exporter Documentation](https://github.com/open-telemetry/opentelemetry-collector-contrib/tree/main/exporter/azuredataexplorerexporter)
- [Azure Data Explorer Documentation](https://docs.microsoft.com/en-us/azure/data-explorer/)
