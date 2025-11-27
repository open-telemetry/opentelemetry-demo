# Agent Integration Guide

This guide explains how to connect your IncidentFox AI SRE agent to the OpenTelemetry Demo.

## Overview

The IncidentFox agent needs access to three types of observability data:

1. **Metrics** - Via Prometheus API
2. **Traces** - Via Jaeger API
3. **Logs** - Via OpenSearch API

Optionally, the agent may also:
- Query Grafana dashboards
- Read Kubernetes state (when deployed on k8s)
- Interact with the feature flag service to remediate issues

## Observability Endpoints

### Docker Compose Deployment

When running locally via Docker Compose:

```yaml
# Metrics
prometheus:
  query_api: "http://localhost:9090/api/v1"
  
# Traces
jaeger:
  query_api: "http://localhost:16686/api"
  ui: "http://localhost:16686"
  
# Logs
opensearch:
  api: "http://localhost:9200"
  
# Dashboards
grafana:
  api: "http://localhost:3000/grafana/api"
  username: "admin"
  password: "admin"
  
# OTel Collector (for custom instrumentation)
otel_collector:
  otlp_grpc: "localhost:4317"
  otlp_http: "http://localhost:4318"
```

### Kubernetes Deployment

When running on Kubernetes (kind/k3d/AWS):

```yaml
# From within the cluster
prometheus:
  query_api: "http://prometheus.otel-demo.svc.cluster.local:9090/api/v1"
  
jaeger:
  query_api: "http://jaeger-query.otel-demo.svc.cluster.local:16686/api"
  
opensearch:
  api: "http://opensearch.otel-demo.svc.cluster.local:9200"
  
grafana:
  api: "http://grafana.otel-demo.svc.cluster.local/api"
```

From outside the cluster (port-forwarded):
```bash
kubectl port-forward -n otel-demo svc/prometheus 9090:9090
kubectl port-forward -n otel-demo svc/jaeger-query 16686:16686
kubectl port-forward -n otel-demo svc/opensearch 9200:9200
```

## Example Agent Configuration

Save this as `agent-config.yaml`:

```yaml
# IncidentFox: Example agent configuration for OTel Demo
agent:
  name: "incidentfox-agent"
  environment: "lab"
  
datasources:
  # Metrics source
  metrics:
    type: "prometheus"
    endpoint: "http://localhost:9090"
    query_api: "http://localhost:9090/api/v1"
    scrape_interval: "15s"
    
  # Traces source
  traces:
    type: "jaeger"
    endpoint: "http://localhost:16686"
    query_api: "http://localhost:16686/api"
    trace_retention: "1h"
    
  # Logs source
  logs:
    type: "opensearch"
    endpoint: "http://localhost:9200"
    index_pattern: "logs-*"
    
  # Optional: Dashboard access
  dashboards:
    type: "grafana"
    endpoint: "http://localhost:3000/grafana"
    api_key: ""  # or use username/password
    username: "admin"
    password: "admin"

# Kubernetes integration (when running on k8s)
kubernetes:
  enabled: true
  namespace: "otel-demo"
  kubeconfig: "~/.kube/config"
  context: "kind-incidentfox-lab"

# Incident detection
detection:
  # Check these metrics for anomalies
  key_metrics:
    - "up"
    - "http_server_request_duration_seconds"
    - "http_server_requests_total"
    - "process_cpu_seconds_total"
    - "process_resident_memory_bytes"
    
  # Alert thresholds
  thresholds:
    error_rate: 0.05  # 5% error rate
    latency_p99: 5.0  # 5 seconds
    cpu_percent: 90.0  # 90% CPU
    memory_percent: 90.0  # 90% memory

# Remediation actions
remediation:
  # Can the agent modify feature flags?
  modify_feature_flags: true
  feature_flag_service: "http://localhost:8080/feature"
  
  # Can the agent restart services?
  restart_services: false
  
  # Can the agent scale services?
  scale_services: false
```

## Querying Observability Data

### Prometheus Queries

```bash
# Current CPU usage per service
curl -G 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=rate(process_cpu_seconds_total[5m])'

# HTTP request rate per service
curl -G 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=rate(http_server_requests_total[5m])'

# Memory usage per service
curl -G 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=process_resident_memory_bytes'

# Error rate
curl -G 'http://localhost:9090/api/v1/query' \
  --data-urlencode 'query=rate(http_server_requests_total{status_code=~"5.."}[5m])'

# Query range (time series data)
curl -G 'http://localhost:9090/api/v1/query_range' \
  --data-urlencode 'query=rate(http_server_requests_total[5m])' \
  --data-urlencode 'start=2024-01-01T00:00:00Z' \
  --data-urlencode 'end=2024-01-01T01:00:00Z' \
  --data-urlencode 'step=15s'
```

### Jaeger Trace Queries

```bash
# List services
curl 'http://localhost:16686/api/services'

# Find traces for a service
curl 'http://localhost:16686/api/traces?service=frontend&limit=20'

# Get a specific trace
curl 'http://localhost:16686/api/traces/{trace_id}'

# Search traces with tags
curl 'http://localhost:16686/api/traces?service=checkout&tags={"http.status_code":"500"}'
```

### OpenSearch Log Queries

```bash
# Search logs
curl -X POST 'http://localhost:9200/logs-*/_search' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {
      "bool": {
        "must": [
          {"match": {"severity": "ERROR"}},
          {"range": {"@timestamp": {"gte": "now-1h"}}}
        ]
      }
    },
    "size": 100,
    "sort": [{"@timestamp": "desc"}]
  }'

# Get logs for specific service
curl -X POST 'http://localhost:9200/logs-*/_search' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {
      "term": {"service.name": "frontend"}
    },
    "size": 50
  }'

# Aggregate error counts by service
curl -X POST 'http://localhost:9200/logs-*/_search' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {"match": {"severity": "ERROR"}},
    "size": 0,
    "aggs": {
      "services": {
        "terms": {"field": "service.name.keyword"}
      }
    }
  }'
```

## Example: Detecting a Service Failure

Here's a Python example showing how the agent might detect and diagnose a service failure:

```python
import requests
from datetime import datetime, timedelta

class IncidentFoxAgent:
    def __init__(self, config):
        self.prometheus_url = config['metrics']['query_api']
        self.jaeger_url = config['traces']['query_api']
        self.opensearch_url = config['logs']['endpoint']
    
    def check_service_health(self):
        """Check if all services are up"""
        query = 'up{job=~".*"}'
        response = requests.get(
            f'{self.prometheus_url}/query',
            params={'query': query}
        )
        results = response.json()['data']['result']
        
        down_services = [
            r['metric']['job']
            for r in results
            if r['value'][1] == '0'
        ]
        
        return down_services
    
    def get_error_rate(self, service, window='5m'):
        """Calculate error rate for a service"""
        query = f'''
            sum(rate(http_server_requests_total{{
                service_name="{service}",
                http_status_code=~"5.."
            }}[{window}]))
            /
            sum(rate(http_server_requests_total{{
                service_name="{service}"
            }}[{window}]))
        '''
        response = requests.get(
            f'{self.prometheus_url}/query',
            params={'query': query}
        )
        data = response.json()['data']['result']
        if data:
            return float(data[0]['value'][1])
        return 0.0
    
    def get_error_traces(self, service, limit=20):
        """Find traces with errors for a service"""
        response = requests.get(
            f'{self.jaeger_url}/traces',
            params={
                'service': service,
                'tags': '{"error":"true"}',
                'limit': limit
            }
        )
        return response.json()['data']
    
    def get_error_logs(self, service, since_minutes=15):
        """Get recent error logs for a service"""
        query = {
            "query": {
                "bool": {
                    "must": [
                        {"match": {"service.name": service}},
                        {"match": {"severity": "ERROR"}},
                        {"range": {
                            "@timestamp": {
                                "gte": f"now-{since_minutes}m"
                            }
                        }}
                    ]
                }
            },
            "size": 100,
            "sort": [{"@timestamp": "desc"}]
        }
        
        response = requests.post(
            f'{self.opensearch_url}/logs-*/_search',
            json=query,
            headers={'Content-Type': 'application/json'}
        )
        return response.json()['hits']['hits']
    
    def diagnose_incident(self, service):
        """Full incident diagnosis"""
        print(f"🔍 Diagnosing issues with {service}...")
        
        # Check error rate
        error_rate = self.get_error_rate(service)
        print(f"   Error rate: {error_rate*100:.2f}%")
        
        # Get sample error traces
        error_traces = self.get_error_traces(service, limit=5)
        print(f"   Found {len(error_traces)} error traces")
        
        # Get error logs
        error_logs = self.get_error_logs(service)
        print(f"   Found {len(error_logs)} error logs")
        
        # Analyze and return diagnosis
        return {
            'service': service,
            'error_rate': error_rate,
            'sample_traces': error_traces[:3],
            'sample_logs': error_logs[:5],
            'severity': 'high' if error_rate > 0.1 else 'medium'
        }

# Usage
agent = IncidentFoxAgent(config)

# Monitor for issues
down_services = agent.check_service_health()
if down_services:
    print(f"🚨 Services down: {down_services}")
    for service in down_services:
        diagnosis = agent.diagnose_incident(service)
        print(f"Diagnosis: {diagnosis}")
```

## Feature Flag Control (Remediation)

The agent can resolve issues by toggling feature flags:

```bash
# Check current flags
curl http://localhost:8080/feature/api/flags

# Disable a problematic feature (turn off an incident)
kubectl edit configmap -n otel-demo flagd-config

# Or use the flagd API
curl -X POST http://localhost:8093/flagd.evaluation.v1.Service/ResolveBoolean \
  -H "Content-Type: application/json" \
  -d '{
    "flagKey": "adFailure",
    "context": {}
  }'
```

See the [Incident Scenarios](incident-scenarios.md) guide for flag names.

## Testing the Integration

### 1. Start the Demo
```bash
docker compose up -d
```

### 2. Verify Endpoints
```bash
# Test each endpoint
curl http://localhost:9090/-/healthy
curl http://localhost:16686/api/services
curl http://localhost:9200/_cluster/health
```

### 3. Trigger a Test Incident
```bash
./incidentfox/scripts/trigger-incident.sh service-failure
```

### 4. Run Your Agent
```bash
python incidentfox-agent.py --config incidentfox/agent-config/example-config.yaml
```

### 5. Verify Detection
The agent should detect:
- Increased error rate in metrics
- Error traces in Jaeger
- Error logs in OpenSearch

## Next Steps

- [Trigger Incident Scenarios](incident-scenarios.md)
- [Deploy to AWS](aws-deployment.md)
- See `agent-config/example-config.yaml` for full configuration

