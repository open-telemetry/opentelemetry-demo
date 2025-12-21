# How Helm Values Work: From YAML to Running Code

## The "Magic" Explained

You write YAML configuration → Helm injects it into templates → Kubernetes creates resources → Your application code reads them at runtime.

Let's trace through a real example!

---

## Example 1: Environment Variables

### Step 1: You Write in values-incidentfox.yaml

```yaml
loadGenerator:
  env:
    - name: LOCUST_USERS
      value: "10"
    - name: LOCUST_AUTOSTART
      value: "true"
```

### Step 2: Helm Template Processes It

Helm charts have **template files** (usually in a separate repo). For example, the load-generator template might look like:

```yaml
# templates/load-generator-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: load-generator
spec:
  template:
    spec:
      containers:
      - name: load-generator
        image: otel-demo:load-generator
        env:
        {{- range .Values.loadGenerator.env }}
        - name: {{ .name }}
          value: {{ .value }}
        {{- end }}
```

**The `{{ }}` syntax** is Go templating. Helm replaces these placeholders with your values.

### Step 3: Helm Renders Final YAML

When you run `helm install`, Helm combines the template + your values:

```yaml
# Rendered output sent to Kubernetes
apiVersion: apps/v1
kind: Deployment
metadata:
  name: load-generator
spec:
  template:
    spec:
      containers:
      - name: load-generator
        image: otel-demo:load-generator
        env:
        - name: LOCUST_USERS
          value: "10"           # ← From your values file!
        - name: LOCUST_AUTOSTART
          value: "true"         # ← From your values file!
```

### Step 4: Kubernetes Creates the Pod

Kubernetes receives this YAML and:
1. Creates a Deployment resource
2. Deployment creates a Pod
3. Pod runs the container

### Step 5: Application Code Reads It

Inside the load-generator container (Python code):

```python
import os

# Read environment variables set by Kubernetes
users = int(os.getenv('LOCUST_USERS', '1'))  # Gets "10" from your values!
autostart = os.getenv('LOCUST_AUTOSTART') == 'true'  # Gets "true"

if autostart:
    # Your values file controls this behavior!
    start_load_test(users=users)
```

**This is how your YAML controls the code!** 🎯

---

## Example 2: Annotations (Labels for Monitoring)

### Step 1: You Write

```yaml
podAnnotations:
  incidentfox.io/monitored: "true"
  incidentfox.io/environment: "lab"
```

### Step 2: Helm Template

```yaml
# templates/deployment.yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    metadata:
      annotations:
        {{- range $key, $value := .Values.podAnnotations }}
        {{ $key }}: {{ $value | quote }}
        {{- end }}
```

### Step 3: Rendered Output

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    metadata:
      annotations:
        incidentfox.io/monitored: "true"
        incidentfox.io/environment: "lab"
```

### Step 4: Kubernetes Creates Pod with Metadata

```bash
$ kubectl get pod recommendation-78ffd8f87-wjtst -o yaml
```

Shows:
```yaml
metadata:
  annotations:
    incidentfox.io/monitored: "true"
    incidentfox.io/environment: "lab"
```

### Step 5: Your Agent Discovers It

```python
# Your AI agent code
pods = kubernetes_client.list_pods(
    namespace="otel-demo",
    label_selector="incidentfox.io/monitored=true"
)

# Returns all pods with your annotation!
for pod in pods:
    environment = pod.metadata.annotations.get('incidentfox.io/environment')
    print(f"Monitoring {pod.name} in {environment} environment")
```

**Your YAML controls what your agent monitors!** 🎯

---

## Example 3: Prometheus Alerts

### Step 1: You Write Alert Rules

```yaml
prometheus:
  serverFiles:
    alerting_rules.yml:
      groups:
        - name: incidentfox-alerts
          rules:
            - alert: HighErrorRate
              expr: |
                sum(rate(http_server_requests_total{http_status_code=~"5.."}[5m]))
                / sum(rate(http_server_requests_total[5m])) > 0.05
              labels:
                severity: high
                incidentfox: "true"
```

### Step 2: Helm Creates ConfigMap

```yaml
# Rendered
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-alerting-rules
data:
  alerting_rules.yml: |
    groups:
      - name: incidentfox-alerts
        rules:
          - alert: HighErrorRate
            expr: |
              sum(rate(http_server_requests_total{http_status_code=~"5.."}[5m]))
              / sum(rate(http_server_requests_total[5m])) > 0.05
            labels:
              severity: high
              incidentfox: "true"
```

### Step 3: Prometheus Pod Mounts ConfigMap

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: prometheus
spec:
  template:
    spec:
      containers:
      - name: prometheus
        volumeMounts:
        - name: alerting-rules
          mountPath: /etc/prometheus/rules/
      volumes:
      - name: alerting-rules
        configMap:
          name: prometheus-alerting-rules  # ← ConfigMap from Step 2
```

### Step 4: Prometheus Loads Rules

When Prometheus container starts:
1. Reads `/etc/prometheus/rules/alerting_rules.yml` (mounted from ConfigMap)
2. Parses the PromQL expression
3. Evaluates it every 30s against metrics
4. Fires alert if condition met

### Step 5: Your Agent Sees Alerts

```python
# Query Prometheus for active alerts
response = requests.get('http://prometheus:9090/api/v1/alerts')
alerts = response.json()['data']['alerts']

for alert in alerts:
    if alert['labels'].get('incidentfox') == 'true':
        # Your YAML configured this alert!
        print(f"IncidentFox alert firing: {alert['labels']['alertname']}")
        # Handle the incident...
```

**Your YAML controls what alerts fire!** 🎯

---

## Example 4: Feature Flags (Most Complex!)

### Step 1: You Write Feature Flag Config

```yaml
# In values-incidentfox.yaml (though this might not be in the actual file)
featureFlags:
  flagd:
    config:
      recommendationCacheFailure:
        defaultVariant: "off"
        variants:
          on: true
          off: false
```

### Step 2: Helm Creates ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: flagd-config
data:
  demo.flagd.json: |
    {
      "flags": {
        "recommendationCacheFailure": {
          "defaultVariant": "off",
          "variants": {
            "on": true,
            "off": false
          }
        }
      }
    }
```

### Step 3: Flagd Service Reads Config

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: flagd
spec:
  template:
    spec:
      containers:
      - name: flagd
        command: ["flagd", "start", "--uri", "file:///etc/flagd/demo.flagd.json"]
        volumeMounts:
        - name: config
          mountPath: /etc/flagd
      volumes:
      - name: config
        configMap:
          name: flagd-config  # ← ConfigMap with your feature flags
```

### Step 4: Application Checks Flag at Runtime

In recommendation service (Python):

```python
from openfeature import api
from openfeature.contrib.provider.flagd import FlagdProvider

# Connect to flagd service
api.set_provider(FlagdProvider(host="flagd", port=8013))
client = api.get_client()

# Your application code checks the flag
def get_recommendations(user_id):
    # Check feature flag (reads from flagd, which reads your ConfigMap!)
    cache_failure_enabled = client.get_boolean_value(
        "recommendationCacheFailure",
        default_value=False
    )
    
    if cache_failure_enabled:
        # Your YAML enabled this via values → ConfigMap → flagd → app!
        # Simulate cache failure
        return get_recommendations_without_cache(user_id)
    else:
        # Normal path
        return get_recommendations_with_cache(user_id)
```

**When you run:**
```bash
./trigger-incident.sh cache-failure
```

It updates the ConfigMap → flagd reloads → app behavior changes!

---

## The Complete Flow Visualized

```
┌─────────────────────────────────────────────────────────────┐
│ 1. YOUR CONFIGURATION                                       │
│    values-incidentfox.yaml                                  │
│                                                             │
│    loadGenerator:                                           │
│      env:                                                   │
│        - name: LOCUST_USERS                                 │
│          value: "10"                                        │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓ helm install (with template)
                   
┌─────────────────────────────────────────────────────────────┐
│ 2. HELM TEMPLATE (from upstream chart repo)                │
│    charts/opentelemetry-demo/templates/deployment.yaml     │
│                                                             │
│    containers:                                              │
│    - name: load-generator                                   │
│      env:                                                   │
│      {{- range .Values.loadGenerator.env }}                │
│      - name: {{ .name }}                                    │
│        value: {{ .value }}                                  │
│      {{- end }}                                             │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓ helm renders
                   
┌─────────────────────────────────────────────────────────────┐
│ 3. KUBERNETES YAML (sent to API)                           │
│                                                             │
│    apiVersion: apps/v1                                      │
│    kind: Deployment                                         │
│    spec:                                                    │
│      containers:                                            │
│      - name: load-generator                                 │
│        env:                                                 │
│        - name: LOCUST_USERS                                 │
│          value: "10"        ← YOUR VALUE!                   │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓ kubectl apply / K8s API
                   
┌─────────────────────────────────────────────────────────────┐
│ 4. KUBERNETES CREATES RESOURCES                            │
│                                                             │
│    ┌─────────────────┐                                     │
│    │  Deployment     │ (Kubernetes resource)               │
│    └────────┬────────┘                                     │
│             │                                                │
│             ↓ creates                                        │
│    ┌─────────────────┐                                     │
│    │  ReplicaSet     │                                      │
│    └────────┬────────┘                                     │
│             │                                                │
│             ↓ creates                                        │
│    ┌─────────────────┐                                     │
│    │  Pod            │                                      │
│    │  ENV:           │                                      │
│    │   LOCUST_USERS="10"   ← YOUR VALUE!                  │
│    └─────────────────┘                                     │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓ Pod runs on Node
                   
┌─────────────────────────────────────────────────────────────┐
│ 5. CONTAINER STARTS (on EC2 node)                          │
│                                                             │
│    Docker/containerd runs:                                  │
│    docker run \                                             │
│      -e LOCUST_USERS=10 \      ← YOUR VALUE!               │
│      -e LOCUST_AUTOSTART=true \                            │
│      otel-demo:load-generator                              │
└──────────────────┬──────────────────────────────────────────┘
                   │
                   ↓ Application starts
                   
┌─────────────────────────────────────────────────────────────┐
│ 6. PYTHON CODE READS ENVIRONMENT                           │
│                                                             │
│    # locustfile.py                                          │
│    import os                                                │
│                                                             │
│    users = int(os.getenv('LOCUST_USERS', '1'))            │
│    # users = 10  ← YOUR VALUE FROM YAML!                   │
│                                                             │
│    autostart = os.getenv('LOCUST_AUTOSTART') == 'true'    │
│    # autostart = True  ← YOUR VALUE!                       │
│                                                             │
│    if autostart:                                            │
│        print(f"Auto-starting with {users} users")          │
│        start_locust(users)  ← YOUR YAML CONTROLS THIS!     │
└─────────────────────────────────────────────────────────────┘
```

---

## Real Example From Your Cluster

### Actual Environment Variables in Your Load Generator:

```bash
$ kubectl get pod -n otel-demo -l app.kubernetes.io/component=load-generator \
    -o jsonpath='{.items[0].spec.containers[0].env[*]}'
```

**Result (from your running cluster):**
```json
{
  "name": "LOCUST_USERS",
  "value": "10"              ← Configured somewhere in values!
}
{
  "name": "LOCUST_AUTOSTART",
  "value": "true"            ← Auto-starts load testing!
}
{
  "name": "LOCUST_HOST",
  "value": "http://frontend-proxy:8080"  ← Target for load testing
}
```

**This proves:** Your values files set these environment variables, and the Python code inside the container reads them!

---

## How Different Config Types Work

### Type 1: Environment Variables → Application Behavior

**Flow:**
```
YAML values → Pod env vars → os.getenv() in code → Behavior change
```

**Example:**
- `LOCUST_USERS: "10"` → Code creates 10 concurrent users
- `LOCUST_AUTOSTART: "true"` → Code automatically starts load test
- `OTEL_EXPORTER_OTLP_ENDPOINT` → Code sends metrics to collector

---

### Type 2: ConfigMaps → Configuration Files

**Flow:**
```
YAML values → ConfigMap → Volume mount → App reads file
```

**Example: Prometheus Alert Rules**

```yaml
# 1. Your values
prometheus:
  serverFiles:
    alerting_rules.yml:
      groups:
        - name: my-alerts
          rules:
            - alert: ServiceDown
              expr: up == 0
```

```yaml
# 2. Helm creates ConfigMap
apiVersion: v1
kind: ConfigMap
metadata:
  name: prometheus-rules
data:
  alerting_rules.yml: |
    groups:
      - name: my-alerts
        rules:
          - alert: ServiceDown
            expr: up == 0
```

```yaml
# 3. Pod mounts ConfigMap as file
volumes:
- name: rules
  configMap:
    name: prometheus-rules

volumeMounts:
- name: rules
  mountPath: /etc/prometheus/rules/
```

```bash
# 4. Inside container, file exists:
$ ls /etc/prometheus/rules/
alerting_rules.yml  ← Your YAML became this file!

# 5. Prometheus reads it:
$ cat /etc/prometheus/prometheus.yml
rule_files:
  - /etc/prometheus/rules/*.yml  ← Loads your rules!
```

---

### Type 3: Annotations/Labels → Metadata

**Flow:**
```
YAML values → Pod metadata → Kubernetes API → Your agent queries it
```

**Example:**

```yaml
# 1. Your values
podAnnotations:
  incidentfox.io/monitored: "true"
```

```yaml
# 2. Pod gets metadata
apiVersion: v1
kind: Pod
metadata:
  annotations:
    incidentfox.io/monitored: "true"
```

```python
# 3. Your agent queries Kubernetes API
import kubernetes

v1 = kubernetes.client.CoreV1Api()
pods = v1.list_namespaced_pod(
    namespace="otel-demo",
    label_selector="incidentfox.io/monitored=true"
)

# Returns pods with your annotation!
```

---

### Type 4: Service Configuration → Network Routing

**Flow:**
```
YAML values → Service resource → AWS Load Balancer → Public internet
```

**Example:**

```yaml
# 1. Your values
frontendProxy:
  service:
    type: LoadBalancer
    annotations:
      service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
```

```yaml
# 2. Kubernetes creates Service
apiVersion: v1
kind: Service
metadata:
  name: frontend-proxy
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-type: "nlb"
spec:
  type: LoadBalancer
  ports:
  - port: 8080
    targetPort: 8080
```

```bash
# 3. AWS Cloud Controller sees this and creates:
- Network Load Balancer in AWS
- Target Group pointing to pods
- Security Groups
- Health checks

# 4. You get a public URL:
$ kubectl get svc frontend-proxy -n otel-demo
NAME             TYPE           EXTERNAL-IP
frontend-proxy   LoadBalancer   abc123.us-west-2.elb.amazonaws.com

# 5. Users can access:
http://abc123.us-west-2.elb.amazonaws.com:8080
```

---

## Why This Matters for IncidentFox

### Example: Your Agent Detects High Latency

```python
# 1. Prometheus alert (from your YAML) fires
{
  "labels": {
    "alertname": "HighLatency",
    "service_name": "recommendation",
    "severity": "medium",
    "incidentfox": "true"     ← From your values-incidentfox.yaml!
  },
  "annotations": {
    "summary": "High latency in recommendation"
  }
}

# 2. Your agent queries for more context
pods = k8s.get_pods(
    label_selector="incidentfox.io/monitored=true"  ← From your values!
)

# 3. Agent checks feature flags
flag = flagd.get("recommendationCacheFailure")  ← ConfigMap from values!

# 4. Agent takes action
if flag == "on":
    # Disable the flag
    flagd.set("recommendationCacheFailure", "off")
    
    # This updates ConfigMap → flagd reloads → app behavior changes!
```

**All orchestrated by your YAML values!** 🎯

---

## The "Magic" Is Actually:

1. **Helm Templates** - Go templates with `{{ .Values.foo }}`
2. **Kubernetes Resources** - YAML files describing desired state
3. **Container Environment** - Docker sets env vars from Kubernetes
4. **Application Code** - Reads env vars / files at runtime

## You Can See It Happening!

### Watch Helm Render Templates:

```bash
cd incidentfox/helm

# See what Helm would generate (without installing)
helm template test-release ./chart-directory \
  -f values-aws-simple.yaml \
  -f values-incidentfox.yaml \
  | less

# You'll see the final YAML that goes to Kubernetes!
```

### Watch Kubernetes Apply:

```bash
# See what Kubernetes has
kubectl get deployment load-generator -n otel-demo -o yaml

# You'll see your values as env vars, volumes, annotations, etc.
```

### Watch Application Use It:

```bash
# Exec into container
kubectl exec -it deployment/load-generator -n otel-demo -- sh

# Check environment variables
$ env | grep LOCUST
LOCUST_USERS=10          ← From your values-incidentfox.yaml!
LOCUST_AUTOSTART=true    ← From your values!

# Check if config files exist
$ ls /etc/flagd/
demo.flagd.json          ← From ConfigMap from your values!

$ cat /etc/flagd/demo.flagd.json
{
  "flags": {
    "recommendationCacheFailure": {
      "defaultVariant": "off"   ← From your values!
    }
  }
}
```

---

## Summary: The Flow

```
You edit YAML values
  ↓
Helm renders templates (substitutes {{ .Values.* }})
  ↓
Generates Kubernetes YAML
  ↓
Kubernetes API creates resources
  ↓
Kubelet on Node starts containers
  ↓
Container runs with your config (env vars, files, etc.)
  ↓
Application code reads config (os.getenv, file.read, etc.)
  ↓
Behavior changes based on your YAML!
```

**It's not magic - it's layers of abstraction!** 

- **Helm**: Template engine (like Jinja2, Handlebars)
- **Kubernetes**: Deployment orchestrator
- **Docker**: Container runtime
- **App Code**: Reads standard env vars/files

Each layer just passes configuration to the next layer. Your YAML at the top controls the whole stack! 🎯

---

## Try It Yourself

### Change a Value:

```bash
# 1. Edit values
vim incidentfox/helm/values-incidentfox.yaml
# Change: LOCUST_USERS: "20"

# 2. Upgrade
helm upgrade otel-demo ./chart \
  -n otel-demo \
  -f values-incidentfox.yaml

# 3. Helm will:
#    - Re-render templates with new value
#    - Update Deployment with new env var
#    - Kubernetes rolls out new pods
#    - New pods have LOCUST_USERS=20

# 4. Check it worked:
kubectl exec deployment/load-generator -n otel-demo -- env | grep LOCUST_USERS
# Output: LOCUST_USERS=20
```

**Your YAML change propagated all the way to running code!** 🚀


<function_calls>
<invoke name="Shell">
<parameter name="command">kubectl get pod -n otel-demo -l app.kubernetes.io/component=load-generator -o yaml 2>&1 | grep -A15 "env:" | head -20