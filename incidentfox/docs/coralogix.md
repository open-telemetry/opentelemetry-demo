# Coralogix Integration (IncidentFox Lab)

This guide shows how to connect this OpenTelemetry Demo / IncidentFox lab to **Coralogix**, so your AI SRE agent can query Coralogix logs/metrics/traces produced by the synthetic incidents.

## Demo UIs (OpenTelemetry Demo / IncidentFox)

In this EKS+Helm setup the demo exposes several UIs via Kubernetes `Service` type `LoadBalancer` (or you can use `kubectl port-forward`).

- **Demo storefront UI**: `frontend-proxy` on port **8080**
- **Grafana**: `grafana` (service port **80**; often port-forward to 3000)
- **Prometheus**: `prometheus` on port **9090**
- **Jaeger UI**: `jaeger-query` on port **16686** (often internal; port-forward recommended)

## What you’re wiring up (high level)

- **Demo services** already emit OTLP (traces/metrics/logs) to `otel-collector`.
- **Goal**: keep the existing local backends (Jaeger/Prometheus/OpenSearch) *and also* get the same telemetry into Coralogix.
- **Recommended approach on Kubernetes/EKS**: install Coralogix’s `otel-integration` Helm chart (runs a pre-configured OpenTelemetry Collector in-cluster), then configure the demo collector to **fan-out** OTLP to the Coralogix collector.

This avoids guessing Coralogix’s public ingestion endpoints and keeps your demo architecture intact.

## Prereqs (Coralogix)

- Create a **Send-Your-Data API key** in Coralogix.
- Identify your **Coralogix domain** (example from Coralogix docs: `eu2.coralogix.com`).
  - If your UI URL looks like `https://<tenant>.app.<region>.coralogix.com/...`, your Helm `global.domain` should be **`<region>.coralogix.com`** (NOT the full UI host).
    - Example: UI `https://incidentfox.app.cx498.coralogix.com` → use **`cx498.coralogix.com`**.

## Step 1: Install Coralogix’s Kubernetes integration

Coralogix documents this as “Setup Kubernetes complete observability integration”.

### 1a) Create the required Kubernetes secret

Coralogix expects a secret named `coralogix-keys` with a key named `PRIVATE_KEY`.

```bash
kubectl create namespace coralogix --dry-run=client -o yaml | kubectl apply -f -
kubectl -n coralogix create secret generic coralogix-keys --from-literal=PRIVATE_KEY="<private_key>"
```

### 1b) Install the Helm chart

```bash
helm repo add coralogix https://cgx.jfrog.io/artifactory/coralogix-charts-virtual
helm repo update

helm upgrade --install otel-coralogix-integration coralogix/otel-integration \
  --namespace coralogix \
  --render-subchart-notes \
  --set global.domain="<domain_name>" \
  --set global.clusterName="<cluster_name>"
```

## Step 2: Find the Coralogix collector OTLP endpoint inside the cluster

After install:

```bash
kubectl get svc -n coralogix
```

You’re looking for a Service that exposes **OTLP gRPC 4317** (and optionally OTLP HTTP 4318).

Copy its DNS name in the form:

- `<service-name>.coralogix.svc.cluster.local:4317`

## Step 3 (recommended): Fan-out demo telemetry to Coralogix

This repo’s collector supports an “extras” config overlay file:

- `src/otel-collector/otelcol-config-extras.yml`

We included a ready-to-uncomment exporter example that forwards OTLP to the Coralogix in-cluster collector. See:

- `src/otel-collector/otelcol-config-extras.yml` (Coralogix section)

### Kubernetes/Helm deployment note

If you’re deploying the demo via the upstream `open-telemetry/opentelemetry-demo` Helm chart (as `incidentfox/scripts/build-all.sh` does), the exact way to override the collector config depends on the chart version.

Practical workflow:

- Deploy Coralogix integration first (Step 1)
- Identify the Coralogix collector Service (Step 2)
- Update the demo collector config to add an **OTLP exporter** pointing at that Service
- Restart the demo collector pod(s)

If you want, paste the chart version you’re deploying (or the rendered collector ConfigMap) and I’ll give you the exact `helm upgrade` override for your setup.

## Verification (quick)

1. Trigger some traffic or an incident:

```bash
./incidentfox/scripts/trigger-incident.sh high-cpu
```

2. In Coralogix, confirm you see:
- **Logs** from your `otel-demo` namespace pods
- **Traces** for demo services (if you enabled fan-out)
- **Kubernetes** dashboards populated (from the integration chart)

## Troubleshooting

- **No data at all**: confirm `coralogix-keys` exists in the namespace you installed the chart into (`coralogix`) and contains `PRIVATE_KEY`.
- **K8s data but no app traces/metrics**: install succeeded, but demo telemetry isn’t being forwarded yet—complete Step 3.
- **Fan-out configured but still no app traces**: verify you chose the Coralogix collector Service/port that exposes OTLP **gRPC 4317**, and restart the demo collector after config changes.

## Recommended Coralogix setup for IncidentFox demos (AI SRE agent)

This is a pragmatic “realistic deployment” baseline that makes a good demo and gives your AI SRE agent real artifacts to discover and use.

### API keys / access model

- **Ingest key (already done)**: “Send-Your-Data API key” used only by collectors/agents to ship telemetry.
- **Agent read key (recommended)**: create a separate **Personal API Key** with *read-only* permissions for:
  - logs search / saved views
  - tracing / APM search
  - metrics query
  - dashboards (list + read)
  - alerts (list + read)
- **Optional agent write key** (later): a separate key with limited write permissions for “incident workflows” (create annotations, acknowledge/resolve alerts, create temporary dashboards/views).

Store the agent key out-of-band (AWS Secrets Manager + ExternalSecrets) and inject it only into the agent, not into the demo services.

### Dashboards to create (minimal, high-signal)

- **Golden signals (by service)**: RPS, error rate, p50/p95 latency, saturation (CPU/mem), broken down by `service.name`.
- **Kubernetes health**: node/pod CPU+mem, restarts, pending pods, HPA/ASG changes.
- **IncidentFox scenario dashboards**: one dashboard per synthetic incident type (high CPU, latency, Kafka issues, DB pressure), with 4–8 focused widgets each.

### Saved views (Logs + Tracing)

Saved views are great for agent discovery because they’re “named investigations”.

- **Logs**:
  - “Errors (otel-demo)” (filter: `k8s.namespace.name = otel-demo` AND severity >= error)
  - “Payments (fraud/payment)” (filter by `service.name`)
  - “Kubernetes events” (filter for event stream / kube-events)
- **Tracing**:
  - “High latency requests” (p95 latency slice)
  - “Error traces last 30m” (status != OK)

### Alerts to wire up (map to incident scenarios)

- **High error rate** (frontend / checkout / payment)
- **High p95 latency** (frontend-proxy / frontend)
- **Pod crashloop / restarts** (by deployment)
- **Node/pod CPU saturation** (supports high-cpu synthetic incident)
- **Queue lag / Kafka unhealthy** (supports message pipeline incidents)

For demos, route alerts to a single destination (Slack/email/webhook) so IncidentFox can “receive a trigger” and then pivot into investigation.

### Metadata conventions (so the agent can “crawl” reliably)

Decide a stable mapping and stick to it:

- **Application**: environment or product boundary (e.g. `otel-demo`)
- **Subsystem**: service identity (use `service.name`, plus `k8s.*` attrs)
- **Environment**: `dev` / `demo` / `prod` (tag/resource attribute)
- **Cluster name**: `incidentfox-demo`

This makes “list dashboards → find relevant widgets → run underlying queries” deterministic.

