#!/bin/bash
# setup-telemetry.sh - Set up telemetry systems for the weekly contest
# 
# This script configures:
# - Loki for logs (with public access)
# - Grafana with anonymous read-only access
# - Jaeger for traces (with public access)
# - Prometheus for metrics (with public access)
# - OTel Collector pipeline routing
#
# Usage: ./setup-telemetry.sh [--install-loki] [--status] [--urls]

set -e

NAMESPACE="otel-demo"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

#######################################
# Show current URLs
#######################################
show_urls() {
    echo ""
    echo "========================================="
    echo "         TELEMETRY SYSTEM URLS          "
    echo "========================================="
    echo ""
    
    # Demo App
    FRONTEND_URL=$(kubectl -n $NAMESPACE get svc frontend-proxy -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
    echo "Demo Application:"
    echo "  http://${FRONTEND_URL}:8080"
    echo ""
    
    # Grafana
    GRAFANA_URL=$(kubectl -n $NAMESPACE get svc grafana-public -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
    if [ -n "$GRAFANA_URL" ]; then
        echo "Grafana (Logs + Dashboards):"
        echo "  http://${GRAFANA_URL}/grafana"
    else
        echo "Grafana: Not exposed publicly"
    fi
    echo ""
    
    # Jaeger
    JAEGER_URL=$(kubectl -n $NAMESPACE get svc jaeger-public -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
    if [ -n "$JAEGER_URL" ]; then
        echo "Jaeger (Traces):"
        echo "  http://${JAEGER_URL}"
    else
        echo "Jaeger: Not exposed publicly"
    fi
    echo ""
    
    # Prometheus
    PROMETHEUS_URL=$(kubectl -n $NAMESPACE get svc prometheus-public -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
    if [ -n "$PROMETHEUS_URL" ]; then
        echo "Prometheus (Metrics):"
        echo "  http://${PROMETHEUS_URL}"
    else
        echo "Prometheus: Not exposed publicly"
    fi
    echo ""
    
    # Loki API
    LOKI_URL=$(kubectl -n $NAMESPACE get svc loki-public -o jsonpath='{.status.loadBalancer.ingress[0].hostname}' 2>/dev/null)
    if [ -n "$LOKI_URL" ]; then
        echo "Loki API (for AI agents):"
        echo "  http://${LOKI_URL}:3100"
    else
        echo "Loki API: Not exposed publicly"
    fi
    echo ""
    echo "========================================="
}

#######################################
# Show status of all telemetry systems
#######################################
show_status() {
    echo ""
    log_info "Checking telemetry system status..."
    echo ""
    
    echo "=== Pods ==="
    kubectl -n $NAMESPACE get pods | grep -E "grafana|jaeger|prometheus|loki|otel-collector" || true
    
    echo ""
    echo "=== Public Services ==="
    kubectl -n $NAMESPACE get svc | grep -E "public|NAME" || true
    
    echo ""
    echo "=== Loki ==="
    kubectl -n $NAMESPACE get pods -l app.kubernetes.io/name=loki 2>/dev/null | head -5 || echo "Loki not installed"
    
    show_urls
}

#######################################
# Install Loki via Helm
#######################################
install_loki() {
    log_info "Installing Loki..."
    
    # Add Grafana Helm repo
    helm repo add grafana https://grafana.github.io/helm-charts 2>/dev/null || true
    helm repo update grafana
    
    # Check if values file exists
    VALUES_FILE="$SCRIPT_DIR/../helm/values-loki.yaml"
    if [ ! -f "$VALUES_FILE" ]; then
        log_warn "Creating default Loki values file..."
        mkdir -p "$SCRIPT_DIR/../helm"
        cat > "$VALUES_FILE" << 'EOF'
# Loki - Single Binary Mode (simple deployment)
deploymentMode: SingleBinary

loki:
  auth_enabled: false
  commonConfig:
    replication_factor: 1
    path_prefix: /var/loki
  schemaConfig:
    configs:
      - from: 2024-01-01
        store: tsdb
        object_store: filesystem
        schema: v13
        index:
          prefix: index_
          period: 24h
  storage:
    type: filesystem
    filesystem:
      chunks_directory: /var/loki/chunks
      rules_directory: /var/loki/rules
  rulerConfig:
    storage:
      type: local
      local:
        directory: /var/loki/rules
  limits_config:
    allow_structured_metadata: true
    volume_enabled: true

singleBinary:
  replicas: 1
  persistence:
    enabled: true
    size: 10Gi

# Disable components not needed for single binary
backend:
  replicas: 0
read:
  replicas: 0
write:
  replicas: 0
gateway:
  enabled: false
chunksCache:
  enabled: false
resultsCache:
  enabled: false
EOF
    fi
    
    # Install or upgrade Loki
    helm upgrade --install loki grafana/loki \
        --namespace $NAMESPACE \
        -f "$VALUES_FILE" \
        --wait --timeout 5m
    
    log_info "Loki installed successfully"
}

#######################################
# Create public LoadBalancer services
#######################################
create_public_services() {
    log_info "Creating public LoadBalancer services..."
    
    # Grafana public service
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: grafana-public
  namespace: $NAMESPACE
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
    service.beta.kubernetes.io/aws-load-balancer-type: nlb
spec:
  type: LoadBalancer
  selector:
    app.kubernetes.io/name: grafana
  ports:
    - name: http
      port: 80
      targetPort: 3000
      protocol: TCP
EOF
    
    # Jaeger public service
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: jaeger-public
  namespace: $NAMESPACE
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
    service.beta.kubernetes.io/aws-load-balancer-type: nlb
spec:
  type: LoadBalancer
  selector:
    app.kubernetes.io/name: jaeger
    app.kubernetes.io/component: all-in-one
  ports:
    - name: http
      port: 80
      targetPort: 16686
      protocol: TCP
EOF
    
    # Prometheus public service
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: prometheus-public
  namespace: $NAMESPACE
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
    service.beta.kubernetes.io/aws-load-balancer-type: nlb
spec:
  type: LoadBalancer
  selector:
    app.kubernetes.io/name: prometheus
  ports:
    - name: http
      port: 80
      targetPort: 9090
      protocol: TCP
EOF
    
    # Loki public service (for AI agent access)
    cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Service
metadata:
  name: loki-public
  namespace: $NAMESPACE
  annotations:
    service.beta.kubernetes.io/aws-load-balancer-scheme: internet-facing
    service.beta.kubernetes.io/aws-load-balancer-type: nlb
spec:
  type: LoadBalancer
  selector:
    app.kubernetes.io/name: loki
    app.kubernetes.io/component: single-binary
  ports:
    - name: http
      port: 3100
      targetPort: 3100
      protocol: TCP
EOF
    
    log_info "Public services created. DNS may take 1-2 minutes to propagate."
}

#######################################
# Configure Grafana for anonymous access
#######################################
configure_grafana_anonymous() {
    log_info "Configuring Grafana for anonymous read-only access..."
    
    # Get current ConfigMap
    CURRENT_INI=$(kubectl -n $NAMESPACE get configmap grafana -o jsonpath='{.data.grafana\.ini}' 2>/dev/null)
    
    if echo "$CURRENT_INI" | grep -q "enabled = true" && echo "$CURRENT_INI" | grep -q "org_role = Viewer"; then
        log_info "Grafana already configured for anonymous access"
        return
    fi
    
    # Update the ConfigMap to enable anonymous access
    kubectl -n $NAMESPACE get configmap grafana -o yaml | \
        sed 's/enabled = false/enabled = true/g' | \
        sed 's/org_role = Admin/org_role = Viewer/g' | \
        kubectl apply -f -
    
    # Restart Grafana to apply changes
    kubectl -n $NAMESPACE rollout restart deployment/grafana
    kubectl -n $NAMESPACE rollout status deployment/grafana --timeout=60s
    
    log_info "Grafana configured for anonymous read-only access"
}

#######################################
# Configure OTel Collector pipeline
#######################################
configure_otel_collector() {
    log_info "Configuring OTel Collector pipeline..."
    
    cat > /tmp/otel-collector-config.yaml << 'EOF'
connectors:
  spanmetrics: {}
exporters:
  otlp:
    endpoint: jaeger-collector:4317
    tls:
      insecure: true
  otlphttp/prometheus:
    endpoint: http://prometheus:9090/api/v1/otlp
    tls:
      insecure: true
  otlphttp/loki:
    endpoint: http://loki:3100/otlp
    tls:
      insecure: true
extensions:
  health_check:
    endpoint: ${env:MY_POD_IP}:13133
processors:
  batch: {}
  k8sattributes:
    extract:
      metadata:
      - k8s.namespace.name
      - k8s.deployment.name
      - k8s.statefulset.name
      - k8s.daemonset.name
      - k8s.cronjob.name
      - k8s.job.name
      - k8s.node.name
      - k8s.pod.name
      - k8s.pod.uid
      - k8s.pod.start_time
    passthrough: false
    pod_association:
    - sources:
      - from: resource_attribute
        name: k8s.pod.ip
    - sources:
      - from: resource_attribute
        name: k8s.pod.uid
    - sources:
      - from: connection
  memory_limiter:
    check_interval: 5s
    limit_percentage: 80
    spike_limit_percentage: 25
  resource:
    attributes:
    - action: insert
      from_attribute: k8s.pod.uid
      key: service.instance.id
  resourcedetection:
    detectors:
    - env
    - system
  transform:
    error_mode: ignore
    trace_statements:
    - context: span
      statements:
      - replace_pattern(name, "\\?.*", "")
      - replace_match(name, "GET /api/products/*", "GET /api/products/{productId}")
receivers:
  httpcheck/frontend-proxy:
    targets:
    - endpoint: http://frontend-proxy:8080
  nginx:
    collection_interval: 10s
    endpoint: http://image-provider:8081/status
  otlp:
    protocols:
      grpc:
        endpoint: ${env:MY_POD_IP}:4317
      http:
        cors:
          allowed_origins:
          - http://*
          - https://*
        endpoint: ${env:MY_POD_IP}:4318
  postgresql:
    endpoint: postgresql:5432
    metrics:
      postgresql.blks_hit:
        enabled: true
      postgresql.blks_read:
        enabled: true
      postgresql.deadlocks:
        enabled: true
      postgresql.tup_deleted:
        enabled: true
      postgresql.tup_fetched:
        enabled: true
      postgresql.tup_inserted:
        enabled: true
      postgresql.tup_returned:
        enabled: true
      postgresql.tup_updated:
        enabled: true
    password: otel
    tls:
      insecure: true
    username: root
  prometheus:
    config:
      scrape_configs:
      - job_name: opentelemetry-collector
        scrape_interval: 10s
        static_configs:
        - targets:
          - ${env:MY_POD_IP}:8888
  redis:
    collection_interval: 10s
    endpoint: valkey-cart:6379
    username: valkey
  jaeger:
    protocols:
      grpc:
        endpoint: ${env:MY_POD_IP}:14250
      thrift_compact:
        endpoint: ${env:MY_POD_IP}:6831
      thrift_http:
        endpoint: ${env:MY_POD_IP}:14268
  zipkin:
    endpoint: ${env:MY_POD_IP}:9411
service:
  extensions:
  - health_check
  pipelines:
    logs:
      exporters:
      - otlphttp/loki
      processors:
      - k8sattributes
      - memory_limiter
      - resourcedetection
      - resource
      - batch
      receivers:
      - otlp
    metrics:
      exporters:
      - otlphttp/prometheus
      processors:
      - k8sattributes
      - memory_limiter
      - resourcedetection
      - resource
      - batch
      receivers:
      - httpcheck/frontend-proxy
      - nginx
      - otlp
      - postgresql
      - redis
      - spanmetrics
    traces:
      exporters:
      - otlp
      - spanmetrics
      processors:
      - k8sattributes
      - memory_limiter
      - resourcedetection
      - resource
      - transform
      - batch
      receivers:
      - otlp
      - jaeger
      - zipkin
  telemetry:
    metrics:
      level: detailed
      readers:
      - periodic:
          exporter:
            otlp:
              endpoint: otel-collector:4318
              protocol: http/protobuf
          interval: 10000
          timeout: 5000
EOF

    kubectl -n $NAMESPACE create configmap otel-collector \
        --from-file=relay=/tmp/otel-collector-config.yaml \
        --dry-run=client -o yaml | kubectl apply -f -
    
    kubectl -n $NAMESPACE rollout restart deployment/otel-collector
    kubectl -n $NAMESPACE rollout status deployment/otel-collector --timeout=60s
    
    log_info "OTel Collector configured"
}

#######################################
# Add Loki datasource to Grafana
#######################################
configure_grafana_loki_datasource() {
    log_info "Configuring Loki datasource in Grafana..."
    
    # Get current datasources ConfigMap
    kubectl -n $NAMESPACE get configmap grafana-datasources -o yaml > /tmp/grafana-ds.yaml
    
    # Check if Loki is already configured
    if grep -q "loki" /tmp/grafana-ds.yaml; then
        log_info "Loki datasource already configured"
        return
    fi
    
    # This would require more complex patching - skip for now
    log_warn "Loki datasource may need manual configuration in Grafana UI"
    log_warn "Go to: Grafana -> Connections -> Data sources -> Add Loki -> URL: http://loki:3100"
}

#######################################
# Upload SRE Dashboards to Grafana
#######################################
upload_dashboards() {
    log_info "Uploading SRE dashboards to Grafana..."
    
    DASHBOARD_DIR="$SCRIPT_DIR/../grafana-dashboards"
    
    if [ ! -d "$DASHBOARD_DIR" ]; then
        log_error "Dashboard directory not found: $DASHBOARD_DIR"
        return 1
    fi
    
    # Get Grafana password
    GRAFANA_PASSWORD=$(kubectl -n $NAMESPACE get secret grafana -o jsonpath='{.data.admin-password}' 2>/dev/null | base64 -d)
    if [ -z "$GRAFANA_PASSWORD" ]; then
        log_error "Could not get Grafana password from secret"
        return 1
    fi
    
    # Port-forward to Grafana
    kubectl -n $NAMESPACE port-forward svc/grafana 3000:80 &
    PF_PID=$!
    sleep 3
    
    # Create SRE Dashboards folder
    curl -s -X POST "http://admin:${GRAFANA_PASSWORD}@localhost:3000/grafana/api/folders" \
        -H "Content-Type: application/json" \
        -d '{"title": "SRE Dashboards", "uid": "sre-dashboards"}' > /dev/null 2>&1 || true
    
    # Upload all SRE dashboards
    for f in "$DASHBOARD_DIR"/sre-*.json; do
        if [ -f "$f" ]; then
            name=$(basename "$f" .json)
            result=$(curl -s -X POST "http://admin:${GRAFANA_PASSWORD}@localhost:3000/grafana/api/dashboards/db" \
                -H "Content-Type: application/json" \
                -d @"$f" | jq -r '.status // .message' 2>/dev/null)
            log_info "  $name: $result"
        fi
    done
    
    # Cleanup
    kill $PF_PID 2>/dev/null || true
    
    log_info "SRE dashboards uploaded"
}

#######################################
# Delete broken provisioned dashboards
#######################################
delete_broken_dashboards() {
    log_info "Deleting broken provisioned dashboards..."
    
    # Delete broken dashboard ConfigMaps
    kubectl -n $NAMESPACE delete configmap grafana-dashboard-demo-dashboard 2>/dev/null || true
    kubectl -n $NAMESPACE delete configmap grafana-dashboard-spanmetrics-dashboard 2>/dev/null || true
    kubectl -n $NAMESPACE delete configmap grafana-dashboard-apm-dashboard 2>/dev/null || true
    kubectl -n $NAMESPACE delete configmap grafana-dashboard-exemplars-dashboard 2>/dev/null || true
    
    log_info "Broken dashboards deleted"
}

#######################################
# Full setup
#######################################
full_setup() {
    log_info "Starting full telemetry setup..."
    echo ""
    
    # Check if Loki is installed
    if ! kubectl -n $NAMESPACE get pods -l app.kubernetes.io/name=loki 2>/dev/null | grep -q Running; then
        log_warn "Loki not found. Installing..."
        install_loki
    else
        log_info "Loki already installed"
    fi
    
    create_public_services
    configure_grafana_anonymous
    configure_otel_collector
    configure_grafana_loki_datasource
    delete_broken_dashboards
    upload_dashboards
    
    echo ""
    log_info "Waiting for LoadBalancers to be ready..."
    sleep 30
    
    show_urls
    
    echo ""
    log_info "Setup complete!"
    echo ""
    echo "Next steps:"
    echo "  1. Wait 1-2 minutes for DNS to propagate"
    echo "  2. Test the URLs above"
    echo "  3. Run: $0 --status to verify everything is working"
}

#######################################
# Main
#######################################
case "${1:-}" in
    --status)
        show_status
        ;;
    --urls)
        show_urls
        ;;
    --install-loki)
        install_loki
        ;;
    --public-services)
        create_public_services
        ;;
    --configure-grafana)
        configure_grafana_anonymous
        ;;
    --configure-otel)
        configure_otel_collector
        ;;
    --upload-dashboards)
        upload_dashboards
        ;;
    --help|-h)
        echo "Usage: $0 [OPTION]"
        echo ""
        echo "Options:"
        echo "  (no option)        Run full setup"
        echo "  --status           Show status of all telemetry systems"
        echo "  --urls             Show public URLs"
        echo "  --install-loki     Install Loki only"
        echo "  --public-services  Create public LoadBalancer services only"
        echo "  --configure-grafana Configure Grafana anonymous access"
        echo "  --configure-otel   Configure OTel Collector pipeline"
        echo "  --upload-dashboards Upload SRE dashboards to Grafana"
        echo "  --help             Show this help"
        ;;
    *)
        full_setup
        ;;
esac
