# IncidentFox Agent Developer Guide

Quick start for developers building AI agents using this playground. **You don't need to understand the infrastructure** - just how to use it.

---

## 🎯 What You Need to Know

The playground is a **live microservices environment** on AWS with:
- 25 services running 24/7
- Real metrics, logs, and traces
- Controllable failure injection
- Full observability stack

**Your job:** Build an AI agent that monitors these services and responds to incidents.

---

## 📍 Access Information

### Observability Endpoints (Live on AWS)

**Prometheus (Metrics):**
```
http://a0427e6dd73914823b12d6dc8a50956e-1942052069.us-west-2.elb.amazonaws.com:9090
```

**Grafana (Dashboards):**
```
http://abffcf5b990ec4bd685aef627eb2daf1-1789943242.us-west-2.elb.amazonaws.com/grafana/
Username: admin
Password: (ask team for password or run export script)
```

**OpenSearch (Logs):**
```
http://a69e2338e2ac54261846aded2148d966-2107276263.us-west-2.elb.amazonaws.com:9200
```

**Jaeger (Traces) - Port Forward:**
```bash
kubectl port-forward -n otel-demo svc/jaeger-query 16686:16686
# Then: http://localhost:16686
```

**Frontend (Test App):**
```
http://a06d7f5e0e0c949aebbaba8fb471d596-1428151517.us-west-2.elb.amazonaws.com:8080
```

---

## 🚀 Quick Start (5 Minutes)

### 1. Get Access

**Ask your team for:**
- AWS credentials (or use existing `playground` profile)
- kubectl access (or run: `aws eks update-kubeconfig --name incidentfox-demo --region us-west-2`)

**Verify access:**
```bash
# Check you can query metrics
curl "http://a0427e6dd73914823b12d6dc8a50956e-1942052069.us-west-2.elb.amazonaws.com:9090/api/v1/query?query=up"

# Check you can see services
kubectl get pods -n otel-demo
```

---

### 2. Understand the Services

**25 microservices simulating an e-commerce site:**

| Service | What It Does | Port |
|---------|-------------|------|
| frontend | Web UI | 8080 |
| cart | Shopping cart | 8080 |
| checkout | Order processing | 8080 |
| payment | Payment processing | 8080 |
| product-catalog | Product database | 8080 |
| recommendation | Product suggestions | 8080 |
| kafka | Message queue | 9092 |
| postgresql | Database | 5432 |

**See full list:** [docs/incident-scenarios.md](docs/incident-scenarios.md)

---

### 3. Your Agent Configuration

**Point your agent at these endpoints:**

```yaml
# agent-config.yaml
datasources:
  metrics:
    endpoint: "http://a0427e6dd73914823b12d6dc8a50956e-1942052069.us-west-2.elb.amazonaws.com:9090"
    query_api: "http://a0427e6dd73914823b12d6dc8a50956e-1942052069.us-west-2.elb.amazonaws.com:9090/api/v1"
  
  traces:
    # Port-forward first: kubectl port-forward -n otel-demo svc/jaeger-query 16686:16686
    endpoint: "http://localhost:16686"
    query_api: "http://localhost:16686/api"
  
  logs:
    endpoint: "http://a69e2338e2ac54261846aded2148d966-2107276263.us-west-2.elb.amazonaws.com:9200"
    index_pattern: "otel-logs-*"
```

**See full config template:** [agent-config/example-config.yaml](agent-config/example-config.yaml)

---

## 🔥 Triggering Incidents

### Available Scenarios (12 total)

```bash
cd /Users/apple/Desktop/aws-playground/incidentfox

# List all scenarios
./scripts/trigger-incident.sh --list

# Trigger specific incident
./scripts/trigger-incident.sh high-cpu
./scripts/trigger-incident.sh service-failure 50%
./scripts/trigger-incident.sh memory-leak

# Check what's active
./scripts/trigger-incident.sh --status

# Clear all incidents
./scripts/trigger-incident.sh clear-all
```

### Common Scenarios for Testing

**1. Service Down (Critical)**
```bash
./scripts/trigger-incident.sh service-unreachable
```
**Expected:** Payment service stops responding, checkout fails

**2. High Error Rate (High Severity)**
```bash
./scripts/trigger-incident.sh service-failure 75%
```
**Expected:** 75% of payment requests fail with HTTP 500

**3. Performance Degradation (Medium)**
```bash
./scripts/trigger-incident.sh high-cpu
```
**Expected:** Ad service CPU spikes to 90%+

**4. Memory Leak (Gradual Failure)**
```bash
./scripts/trigger-incident.sh memory-leak
```
**Expected:** Email service memory grows, eventually OOM killed

**Complete catalog:** [docs/incident-scenarios.md](docs/incident-scenarios.md)

---

## 📊 Querying Observability Data

### Prometheus Queries

**Service health:**
```bash
curl -G "http://a0427e6dd73914823b12d6dc8a50956e-1942052069.us-west-2.elb.amazonaws.com:9090/api/v1/query" \
  --data-urlencode 'query=up'
```

**Error rate:**
```bash
curl -G "http://a0427e6dd73914823b12d6dc8a50956e-1942052069.us-west-2.elb.amazonaws.com:9090/api/v1/query" \
  --data-urlencode 'query=sum(rate(http_server_requests_total{http_status_code=~"5.."}[5m])) by (service_name)'
```

**CPU usage:**
```bash
curl -G "http://a0427e6dd73914823b12d6dc8a50956e-1942052069.us-west-2.elb.amazonaws.com:9090/api/v1/query" \
  --data-urlencode 'query=rate(process_cpu_seconds_total[1m])'
```

**More examples:** [agent-config/endpoints.yaml](agent-config/endpoints.yaml)

---

### OpenSearch Log Queries

**Recent error logs:**
```bash
curl -X POST "http://a69e2338e2ac54261846aded2148d966-2107276263.us-west-2.elb.amazonaws.com:9200/otel-logs-*/_search" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {"match": {"severity": "ERROR"}},
    "size": 20,
    "sort": [{"@timestamp": "desc"}]
  }'
```

**Logs for specific service:**
```bash
curl -X POST "http://a69e2338e2ac54261846aded2148d966-2107276263.us-west-2.elb.amazonaws.com:9200/otel-logs-*/_search" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {"term": {"service.name.keyword": "frontend"}},
    "size": 50
  }'
```

---

### Jaeger Trace Queries

**Port-forward first:**
```bash
kubectl port-forward -n otel-demo svc/jaeger-query 16686:16686 &
```

**List services:**
```bash
curl "http://localhost:16686/api/services"
```

**Find error traces:**
```bash
curl 'http://localhost:16686/api/traces?service=payment&tags={"error":"true"}&limit=20'
```

---

## 🧪 Testing Your Agent

### Test Cycle

**1. Baseline (No Incidents):**
```bash
# Verify all services healthy
curl "http://a0427e6dd73914823b12d6dc8a50956e-1942052069.us-west-2.elb.amazonaws.com:9090/api/v1/query?query=up" | jq '.data.result[] | select(.value[1]=="0")'
# Should return empty (all services up)
```

**2. Trigger Incident:**
```bash
./scripts/trigger-incident.sh service-failure 50%
```

**3. Monitor Agent:**
- Does it detect the issue? (within 1-2 minutes)
- Does it identify the failing service? (payment)
- Does it correlate metrics, logs, traces?
- Does it diagnose root cause? (feature flag)

**4. Agent Remediation (Optional):**
```bash
# If your agent can remediate, it should disable the flag:
./scripts/trigger-incident.sh clear-all
```

**5. Verify Recovery:**
```bash
# Confirm error rate dropped
curl -G "http://a0427e6dd73914823b12d6dc8a50956e-1942052069.us-west-2.elb.amazonaws.com:9090/api/v1/query" \
  --data-urlencode 'query=rate(http_server_requests_total{service_name="payment",http_status_code=~"5.."}[5m])'
```

---

## 🔍 Debugging Your Agent

### View Service Status

```bash
# All pods
kubectl get pods -n otel-demo

# Specific service logs
kubectl logs -n otel-demo -l app.kubernetes.io/component=payment --tail=100

# Follow logs
kubectl logs -n otel-demo -l app.kubernetes.io/component=payment -f
```

### Check Metrics

**Grafana UI:**
1. Open: http://abffcf5b990ec4bd685aef627eb2daf1-1789943242.us-west-2.elb.amazonaws.com/grafana/
2. Login: admin / (get password from team)
3. Go to Dashboards → Browse

**Prometheus UI:**
1. Open: http://a0427e6dd73914823b12d6dc8a50956e-1942052069.us-west-2.elb.amazonaws.com:9090
2. Go to Graph tab
3. Enter PromQL query

---

## 📝 Common Agent Development Tasks

### Query Current State

```python
import requests

PROMETHEUS_URL = "http://a0427e6dd73914823b12d6dc8a50956e-1942052069.us-west-2.elb.amazonaws.com:9090"

# Check if all services are up
response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={
    'query': 'up{job=~".*"}'
})

results = response.json()['data']['result']
for result in results:
    service = result['metric']['job']
    status = result['value'][1]
    print(f"{service}: {'UP' if status == '1' else 'DOWN'}")
```

### Detect Anomalies

```python
# Get error rate for each service
query = '''
sum(rate(http_server_requests_total{http_status_code=~"5.."}[5m])) by (service_name)
/
sum(rate(http_server_requests_total[5m])) by (service_name)
'''

response = requests.get(f"{PROMETHEUS_URL}/api/v1/query", params={'query': query})
for result in response.json()['data']['result']:
    service = result['metric']['service_name']
    error_rate = float(result['value'][1])
    if error_rate > 0.05:  # 5% threshold
        print(f"🚨 {service}: {error_rate*100:.2f}% error rate")
```

### Search Logs

```python
OPENSEARCH_URL = "http://a69e2338e2ac54261846aded2148d966-2107276263.us-west-2.elb.amazonaws.com:9200"

# Find recent errors
query = {
    "query": {
        "bool": {
            "must": [
                {"match": {"severity": "ERROR"}},
                {"range": {"@timestamp": {"gte": "now-5m"}}}
            ]
        }
    },
    "size": 50,
    "sort": [{"@timestamp": "desc"}]
}

response = requests.post(f"{OPENSEARCH_URL}/otel-logs-*/_search", json=query)
for hit in response.json()['hits']['hits']:
    log = hit['_source']
    print(f"{log['@timestamp']} [{log['service.name']}] {log['body']}")
```

---

## 🎓 Learning Path

### Day 1: Explore
1. Browse the frontend app
2. Look at Grafana dashboards
3. Query Prometheus for basic metrics
4. Trigger one simple incident (high-cpu)

### Day 2: Understand Failure Patterns
1. Trigger each of the 12 incidents
2. Observe metrics, logs, traces for each
3. Note the signatures (how to detect each type)

### Day 3: Build Detection
1. Write code to query Prometheus
2. Implement anomaly detection
3. Test against triggered incidents

### Day 4: Build Diagnosis
1. Correlate metrics + logs + traces
2. Identify root cause from signals
3. Test diagnosis accuracy

### Day 5: Build Remediation
1. Implement flag disabling (clear incidents)
2. Test end-to-end: detect → diagnose → remediate
3. Measure time to resolution

---

## 📚 Documentation for You

**Essential:**
1. This guide (AGENT-DEV-GUIDE.md) - Start here
2. [docs/incident-scenarios.md](docs/incident-scenarios.md) - All 12 failure scenarios
3. [agent-config/endpoints.yaml](agent-config/endpoints.yaml) - API endpoints reference
4. [agent-config/example-config.yaml](agent-config/example-config.yaml) - Config template

**Reference (as needed):**
- [docs/agent-integration.md](docs/agent-integration.md) - Detailed integration guide
- [README.md](README.md) - System overview

**Infrastructure (only if curious):**
- [docs/aws-deployment.md](docs/aws-deployment.md) - How it's deployed
- [docs/secrets.md](docs/secrets.md) - How secrets work

---

## 🔑 Getting Secrets

**To access Grafana, RDS, etc., you need passwords:**

```bash
cd /Users/apple/Desktop/aws-playground/incidentfox

# Export all secrets
./scripts/export-secrets-to-1password.sh

# Shows:
# - PostgreSQL password
# - Grafana password
# - RDS password (if deployed)
```

**Or ask team lead for 1Password vault access.**

---

## 🎯 Common Workflows

### Workflow 1: Test Incident Detection

```bash
# 1. Trigger incident
./scripts/trigger-incident.sh service-failure 75%

# 2. Run your agent
python agent.py

# 3. Agent should detect:
#    - High error rate in payment service
#    - Errors in logs
#    - Failed traces

# 4. Clear incident
./scripts/trigger-incident.sh clear-all

# 5. Verify agent detects recovery
```

---

### Workflow 2: Test Different Failure Types

```bash
# CPU spike
./scripts/trigger-incident.sh high-cpu
# Agent should detect: High CPU metrics for ad service

# Memory leak
./scripts/trigger-incident.sh memory-leak
# Agent should detect: Growing memory, eventual OOM

# Latency spike
./scripts/trigger-incident.sh latency-spike
# Agent should detect: P99 latency increase

# Each tests different detection logic!
```

---

### Workflow 3: Multi-Service Cascading Failure

```bash
# Trigger cascade
./scripts/trigger-incident.sh service-unreachable  # Payment down
./scripts/trigger-incident.sh kafka-lag            # Queue backs up

# Agent should:
# 1. Detect payment service down
# 2. Detect checkout errors (can't reach payment)
# 3. Detect Kafka lag (orders not processing)
# 4. Identify payment as root cause
# 5. Recommend: Fix payment service first
```

---

## 🐛 Troubleshooting

### "Can't Access Endpoints"

**Fix:**
```bash
# Check kubectl works
kubectl get pods -n otel-demo

# If not, update kubeconfig
aws eks update-kubeconfig --name incidentfox-demo --region us-west-2

# Check LoadBalancers exist
kubectl get svc -n otel-demo | grep LoadBalancer
```

---

### "No Data in Prometheus"

**Check:**
```bash
# Are services running?
kubectl get pods -n otel-demo

# Check Prometheus targets
curl "http://a0427e6dd73914823b12d6dc8a50956e-1942052069.us-west-2.elb.amazonaws.com:9090/api/v1/targets"
```

---

### "Incidents Not Working"

**Verify:**
```bash
# Check flagd is running
kubectl get pods -n otel-demo | grep flagd

# Check flag file
kubectl exec -n otel-demo deployment/flagd -- cat /etc/flagd/demo.flagd.json | jq '.flags.adHighCpu.defaultVariant'
```

---

## 🤝 Team Collaboration

### If Playground is Down

**Check with team:**
```bash
# Is cluster running?
aws eks describe-cluster --name incidentfox-demo --region us-west-2

# Are pods running?
kubectl get pods -n otel-demo
```

**Restart if needed:**
```bash
# Ask team to run:
cd /Users/apple/Desktop/aws-playground/incidentfox
./scripts/build-all.sh status
```

---

### Sharing Findings

**When you find interesting patterns:**
1. Note the incident scenario
2. Capture the metrics query
3. Link to trace ID in Jaeger
4. Document expected vs actual behavior

**Example:**
```
Incident: service-failure 50%
Metric: sum(rate(http_server_requests_total{service_name="payment",http_status_code=~"5.."}[5m])) = 8.5
Expected: ~50% error rate
Actual: 50.2% error rate ✓
Trace: http://localhost:16686/trace/abc123def456
Agent Detection Time: 45 seconds
```

---

## 🎯 Agent Development Checklist

### Phase 1: Detection (Week 1)
- [ ] Query Prometheus for service health
- [ ] Detect when services go down
- [ ] Detect high error rates
- [ ] Detect latency spikes
- [ ] Test against all 12 incident scenarios

### Phase 2: Diagnosis (Week 2)
- [ ] Correlate metrics + logs + traces
- [ ] Identify affected service(s)
- [ ] Determine failure pattern
- [ ] Find root cause signals
- [ ] Generate diagnosis report

### Phase 3: Remediation (Week 3)
- [ ] Disable problematic feature flags
- [ ] Verify incident resolution
- [ ] Measure time to recovery
- [ ] Handle edge cases

### Phase 4: Integration (Week 4)
- [ ] Deploy agent to same VPC/EKS cluster
- [ ] Connect to RDS for state persistence
- [ ] Implement notification (Slack, PagerDuty)
- [ ] Production testing

---

## 💡 Pro Tips

**1. Use Grafana Explore for ad-hoc queries**
- Faster than writing code
- Great for understanding data structure
- Can export queries to PromQL/LogQL

**2. Keep incidents active for testing**
- Don't clear immediately
- Test agent detection multiple times
- Iterate on detection logic

**3. Use port-forwarding for internal services**
```bash
# Jaeger
kubectl port-forward -n otel-demo svc/jaeger-query 16686:16686 &

# PostgreSQL (if needed)
kubectl port-forward -n otel-demo svc/postgresql 5432:5432 &
```

**4. Check CODE-TOUR.md for technical deep-dives**
- Understand how services communicate
- Learn request flows
- See observability architecture

---

## 📞 Getting Help

**Questions about:**
- Playground infrastructure → Ask infrastructure team
- Incident scenarios → Check [docs/incident-scenarios.md](docs/incident-scenarios.md)
- API endpoints → Check [agent-config/endpoints.yaml](agent-config/endpoints.yaml)
- Agent integration → Check [docs/agent-integration.md](docs/agent-integration.md)

**Escalation:**
- Playground down or broken → Infrastructure team
- Need new incident scenario → File request with SRE team
- Need different observability data → Check if already available

---

## 🚀 Your First Day Checklist

- [ ] Get AWS/kubectl access
- [ ] Verify you can query Prometheus
- [ ] Browse Grafana dashboards
- [ ] Trigger one incident (high-cpu)
- [ ] Observe the failure in metrics/logs
- [ ] Clear the incident
- [ ] Write simple detection code
- [ ] Test against 2-3 more incidents

**Welcome to the IncidentFox playground! You're ready to build AI agents that actually work.** 🎉

---

## Quick Reference Card

```
ENDPOINTS:
  Prometheus: http://a0427e6dd73914823b12d6dc8a50956e-1942052069.us-west-2.elb.amazonaws.com:9090
  Grafana:    http://abffcf5b990ec4bd685aef627eb2daf1-1789943242.us-west-2.elb.amazonaws.com/grafana/
  OpenSearch: http://a69e2338e2ac54261846aded2148d966-2107276263.us-west-2.elb.amazonaws.com:9200
  Jaeger:     kubectl port-forward -n otel-demo svc/jaeger-query 16686:16686

TRIGGER INCIDENTS:
  cd /Users/apple/Desktop/aws-playground/incidentfox
  ./scripts/trigger-incident.sh <scenario>

SCENARIOS:
  high-cpu, memory-leak, service-failure, service-unreachable,
  latency-spike, kafka-lag, cache-failure, traffic-spike

CLEAR ALL:
  ./scripts/trigger-incident.sh clear-all

VIEW PODS:
  kubectl get pods -n otel-demo

VIEW LOGS:
  kubectl logs -n otel-demo -l app.kubernetes.io/component=<service> --tail=100
```

