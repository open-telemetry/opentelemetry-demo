#!/bin/bash
# IncidentFox: Master incident trigger script
# 
# This script provides a unified interface for triggering various incident scenarios
# in the OpenTelemetry Demo by manipulating feature flags.

set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENARIOS_DIR="${SCRIPT_DIR}/scenarios"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
FLAGD_CONFIG="${REPO_ROOT}/src/flagd/demo.flagd.json"

# incident.io configuration
INCIDENTIO_API_KEY="${INCIDENTIO_API_KEY:-}"  # Set via env var: export INCIDENTIO_API_KEY=inc_xxx
INCIDENTIO_API_BASE="https://api.incident.io"
INCIDENTIO_DELAY="${INCIDENTIO_DELAY:-180}"  # 3 minutes default

# Severity IDs (from incident.io organization)
SEVERITY_ID_MINOR="01KCSZ7E54DSD4TTVPXFEEQ2PV"
SEVERITY_ID_MAJOR="01KCSZ7E54R7NQE5570YHFA3C8"
SEVERITY_ID_CRITICAL="01KCSZ7E54WJQBBZ0HBYQ152FW"

# Flag for triggering incident.io
TRIGGER_INCIDENTIO=false

# Kubernetes mode
KUBE_MODE=false
KUBE_NAMESPACE="${KUBE_NAMESPACE:-otel-demo}"
KUBE_CONFIGMAP="${KUBE_CONFIGMAP:-flagd-config}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print functions
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# ============================================================================
# incident.io Alert Mapping
# ============================================================================

# Get flag config for a scenario
# Returns: flag_name|default_variant
get_scenario_flag() {
    local scenario="$1"
    local variant="${2:-}"
    
    case "$scenario" in
        service-failure)
            echo "paymentFailure|${variant:-50%}"
            ;;
        high-cpu)
            echo "adHighCpu|${variant:-on}"
            ;;
        memory-leak)
            echo "emailMemoryLeak|${variant:-on}"
            ;;
        cache-failure)
            echo "recommendationCacheFailure|${variant:-on}"
            ;;
        kafka-lag)
            echo "kafkaQueueProblems|${variant:-on}"
            ;;
        latency-spike)
            echo "imageSlowLoad|${variant:-on}"
            ;;
        catalog-failure)
            echo "productCatalogFailure|${variant:-on}"
            ;;
        traffic-spike)
            echo "loadGeneratorFloodHomepage|${variant:-on}"
            ;;
        ad-gc-pressure)
            echo "adHighCpu|${variant:-on}"
            ;;
        llm-inaccuracy)
            echo "llmInaccuracy|${variant:-on}"
            ;;
        llm-rate-limit)
            echo "llmRateLimit|${variant:-on}"
            ;;
        service-unreachable)
            echo "paymentServiceUnreachable|${variant:-on}"
            ;;
        *)
            echo ""
            ;;
    esac
}

# Get incident.io alert config for a scenario
# Returns: name|severity|summary
get_incidentio_alert() {
    local scenario="$1"
    
    case "$scenario" in
        service-failure)
            echo "Payment Service - High Error Rate|critical|Payment service is experiencing a high rate of failed transactions. Customers cannot complete purchases."
            ;;
        high-cpu)
            echo "Ad Service - High CPU Usage|major|CPU utilization in the Ad service has exceeded 80% threshold. Service degradation possible."
            ;;
        memory-leak)
            echo "Email Service - Memory Leak Detected|major|Email service memory usage is growing abnormally. OOM kill risk if not addressed."
            ;;
        cache-failure)
            echo "Recommendation Service - Cache Failure|major|Recommendation cache is failing, causing increased latency and database load."
            ;;
        kafka-lag)
            echo "Kafka - Consumer Lag Critical|critical|Kafka consumer lag has exceeded threshold. Order processing is delayed."
            ;;
        latency-spike)
            echo "Frontend - Slow Image Loading|minor|Image loading times have increased significantly. User experience degraded."
            ;;
        catalog-failure)
            echo "Product Catalog - Service Failure|critical|Product catalog service is failing. Users cannot browse products."
            ;;
        traffic-spike)
            echo "Load Generator - Traffic Flood|major|Abnormal traffic spike detected. Possible DDoS or load generator misconfiguration."
            ;;
        ad-gc-pressure)
            echo "Ad Service - GC Pressure|major|Ad service is experiencing high garbage collection pressure. Latency spikes expected."
            ;;
        llm-inaccuracy)
            echo "LLM Service - Inaccurate Responses|minor|LLM service is returning inaccurate or low-quality responses."
            ;;
        llm-rate-limit)
            echo "LLM Service - Rate Limited|major|LLM service is being rate limited. AI-powered features degraded."
            ;;
        *)
            echo "Unknown Incident - $scenario|minor|An unknown incident scenario was triggered: $scenario"
            ;;
    esac
}

# Trigger incident.io alert in background after delay
trigger_incidentio_alert() {
    local scenario="$1"
    local delay="$2"
    
    # Get alert config
    local alert_config
    alert_config=$(get_incidentio_alert "$scenario")
    
    local alert_name alert_severity alert_summary
    alert_name=$(echo "$alert_config" | cut -d'|' -f1)
    alert_severity=$(echo "$alert_config" | cut -d'|' -f2)
    alert_summary=$(echo "$alert_config" | cut -d'|' -f3)
    
    # Map severity to ID
    local severity_id
    case "$alert_severity" in
        critical) severity_id="$SEVERITY_ID_CRITICAL" ;;
        major)    severity_id="$SEVERITY_ID_MAJOR" ;;
        minor)    severity_id="$SEVERITY_ID_MINOR" ;;
        *)        severity_id="$SEVERITY_ID_MAJOR" ;;
    esac
    
    # Generate unique idempotency key
    local idempotency_key="failure-injection-${scenario}-$(date +%s)"
    
    print_info "incident.io alert scheduled:"
    echo "  • Name: ${alert_name}"
    echo "  • Severity: ${alert_severity}"
    echo "  • Delay: ${delay} seconds"
    echo ""
    
    # Run in background
    (
        sleep "$delay"
        
        response=$(curl -s -X POST "${INCIDENTIO_API_BASE}/v2/incidents" \
            -H "Authorization: Bearer ${INCIDENTIO_API_KEY}" \
            -H "Content-Type: application/json" \
            -d "{
                \"name\": \"${alert_name}\",
                \"idempotency_key\": \"${idempotency_key}\",
                \"severity_id\": \"${severity_id}\",
                \"visibility\": \"public\",
                \"summary\": \"${alert_summary}\"
            }" 2>/dev/null)
        
        if echo "$response" | grep -q '"incident"'; then
            incident_ref=$(echo "$response" | grep -o '"reference":"[^"]*"' | cut -d'"' -f4)
            echo ""
            echo -e "${GREEN}✓${NC} incident.io alert created: ${incident_ref} - ${alert_name}"
        else
            echo ""
            echo -e "${RED}✗${NC} Failed to create incident.io alert"
        fi
    ) &
    
    print_success "incident.io alert will fire in ${delay} seconds (background)"
}

# ============================================================================
# Kubernetes Flag Management
# ============================================================================

# Set a flag in Kubernetes ConfigMap
kube_set_flag() {
    local flag_name="$1"
    local variant="$2"
    
    print_info "Setting flag '${flag_name}' to '${variant}' on Kubernetes..."
    
    # Get current config
    local current_config
    current_config=$(kubectl get configmap "$KUBE_CONFIGMAP" -n "$KUBE_NAMESPACE" -o jsonpath='{.data.demo\.flagd\.json}' 2>/dev/null)
    
    if [ -z "$current_config" ]; then
        print_error "Failed to get ConfigMap ${KUBE_CONFIGMAP} in namespace ${KUBE_NAMESPACE}"
        return 1
    fi
    
    # Update the flag
    local new_config
    new_config=$(echo "$current_config" | jq ".flags.${flag_name}.defaultVariant = \"${variant}\"")
    
    # Patch the ConfigMap
    kubectl patch configmap "$KUBE_CONFIGMAP" -n "$KUBE_NAMESPACE" \
        --type merge \
        -p "{\"data\":{\"demo.flagd.json\":$(echo "$new_config" | jq -c . | jq -Rs .)}}" > /dev/null
    
    if [ $? -eq 0 ]; then
        print_success "Flag '${flag_name}' set to '${variant}' on Kubernetes"
        
        # Restart flagd to pick up changes
        kubectl rollout restart deployment/flagd -n "$KUBE_NAMESPACE" > /dev/null 2>&1 || true
        print_info "Restarted flagd deployment to apply changes"
    else
        print_error "Failed to patch ConfigMap"
        return 1
    fi
}

# Clear all flags in Kubernetes
kube_clear_all_flags() {
    print_info "Clearing all flags on Kubernetes..."
    
    # Get current config
    local current_config
    current_config=$(kubectl get configmap "$KUBE_CONFIGMAP" -n "$KUBE_NAMESPACE" -o jsonpath='{.data.demo\.flagd\.json}' 2>/dev/null)
    
    if [ -z "$current_config" ]; then
        print_error "Failed to get ConfigMap"
        return 1
    fi
    
    # Set all flags to "off"
    local new_config
    new_config=$(echo "$current_config" | jq '.flags |= with_entries(.value.defaultVariant = "off")')
    
    # Patch the ConfigMap
    kubectl patch configmap "$KUBE_CONFIGMAP" -n "$KUBE_NAMESPACE" \
        --type merge \
        -p "{\"data\":{\"demo.flagd.json\":$(echo "$new_config" | jq -c . | jq -Rs .)}}" > /dev/null
    
    if [ $? -eq 0 ]; then
        print_success "All flags cleared on Kubernetes"
        kubectl rollout restart deployment/flagd -n "$KUBE_NAMESPACE" > /dev/null 2>&1 || true
        print_info "Restarted flagd deployment to apply changes"
    else
        print_error "Failed to clear flags"
        return 1
    fi
}

# Check status on Kubernetes
kube_check_status() {
    print_info "Checking flag status on Kubernetes (namespace: ${KUBE_NAMESPACE})..."
    echo ""
    
    local config
    config=$(kubectl get configmap "$KUBE_CONFIGMAP" -n "$KUBE_NAMESPACE" -o jsonpath='{.data.demo\.flagd\.json}' 2>/dev/null)
    
    if [ -z "$config" ]; then
        print_error "Failed to get ConfigMap"
        return 1
    fi
    
    local active_flags
    active_flags=$(echo "$config" | jq -r '.flags | to_entries[] | select(.value.defaultVariant != "off") | "\(.key): \(.value.defaultVariant)"')
    
    if [ -z "$active_flags" ]; then
        print_success "No active incidents on Kubernetes"
    else
        print_warning "Active incidents on Kubernetes:"
        echo "$active_flags" | while read -r line; do
            echo "  • ${line}"
        done
    fi
}

# Help text
show_help() {
    cat << EOF
IncidentFox Incident Trigger Script

Usage: $0 [SCENARIO] [OPTIONS]

Available Scenarios:
  high-cpu              Trigger CPU spike in ad service
  memory-leak           Trigger memory leak in email service
  service-failure       Trigger payment service failures
  service-unreachable   Make payment service unreachable
  latency-spike         Trigger slow image loading
  kafka-lag             Trigger Kafka message queue lag
  cache-failure         Trigger recommendation cache failure
  catalog-failure       Trigger product catalog failure
  ad-gc-pressure        Trigger GC pressure in ad service
  traffic-spike         Trigger load generator flood
  llm-inaccuracy        Trigger LLM inaccurate responses
  llm-rate-limit        Trigger LLM rate limit errors
  
  list-active           Show currently active incidents
  clear-all             Disable all active incidents

Options:
  --list                List all available scenarios
  --help                Show this help message
  --status              Show current incident status
  --kube                Use Kubernetes mode (edit configmap)
  --dry-run             Show what would be done without doing it
  --incidentio          Also create an incident.io incident after delay
  --incidentio-delay N  Delay in seconds before creating incident (default: 180)

Examples:
  # Trigger a high CPU incident
  $0 high-cpu
  
  # Trigger service failure with specific rate
  $0 service-failure 50%
  
  # Trigger failure AND create incident.io alert after 3 minutes
  $0 service-failure --incidentio
  
  # Trigger failure AND create incident.io alert after 1 minute
  $0 high-cpu --incidentio --incidentio-delay 60
  
  # Clear all incidents
  $0 clear-all
  
  # Check what's currently active
  $0 --status

Environment Variables:
  KUBE_CONTEXT          Kubernetes context to use (for --kube mode)
  KUBE_NAMESPACE        Kubernetes namespace (default: otel-demo)
  INCIDENTIO_API_KEY    incident.io API key (for --incidentio mode)
  INCIDENTIO_DELAY      Default delay before incident creation (default: 180)

EOF
}

# List all scenarios
list_scenarios() {
    print_info "Available incident scenarios:"
    echo ""
    
    for script in "${SCENARIOS_DIR}"/*.sh; do
        if [ -f "$script" ]; then
            name=$(basename "$script" .sh)
            description=$(grep "^# Description:" "$script" | sed 's/# Description: //')
            printf "  ${GREEN}%-20s${NC} %s\n" "$name" "$description"
        fi
    done
}

# Check current status
check_status() {
    if [ "$KUBE_MODE" = true ]; then
        kube_check_status
        return $?
    fi
    
    print_info "Checking current incident status (local)..."
    echo ""
    
    if [ ! -f "$FLAGD_CONFIG" ]; then
        print_error "Flag configuration not found: $FLAGD_CONFIG"
        return 1
    fi
    
    # Parse JSON and show active flags
    active_flags=$(jq -r '.flags | to_entries[] | select(.value.defaultVariant != "off") | .key' "$FLAGD_CONFIG" 2>/dev/null || echo "")
    
    if [ -z "$active_flags" ]; then
        print_success "No active incidents"
    else
        print_warning "Active incidents:"
        echo "$active_flags" | while read -r flag; do
            variant=$(jq -r ".flags.${flag}.defaultVariant" "$FLAGD_CONFIG")
            echo "  • ${flag}: ${variant}"
        done
    fi
}

# Clear all incidents
clear_all() {
    if [ "$KUBE_MODE" = true ]; then
        kube_clear_all_flags
        return $?
    fi
    
    print_info "Clearing all active incidents (local)..."
    
    # Create a backup
    cp "$FLAGD_CONFIG" "${FLAGD_CONFIG}.backup"
    print_info "Created backup: ${FLAGD_CONFIG}.backup"
    
    # Set all flags to "off"
    jq '.flags |= with_entries(.value.defaultVariant = "off")' "$FLAGD_CONFIG" > "${FLAGD_CONFIG}.tmp"
    mv "${FLAGD_CONFIG}.tmp" "$FLAGD_CONFIG"
    
    print_success "All incidents cleared"
    print_info "Flagd will reload the configuration automatically (may take 5-10 seconds)"
}

# Map scenario name to script
get_scenario_script() {
    local scenario="$1"
    local script="${SCENARIOS_DIR}/${scenario}.sh"
    
    if [ ! -f "$script" ]; then
        print_error "Unknown scenario: $scenario"
        print_info "Run '$0 --list' to see available scenarios"
        return 1
    fi
    
    echo "$script"
}

# Trigger a scenario
trigger_scenario() {
    local scenario="$1"
    shift
    
    # Parse remaining args, separating scenario args from our flags
    local scenario_args=()
    local incidentio_delay="$INCIDENTIO_DELAY"
    local use_kube="$KUBE_MODE"
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --incidentio)
                TRIGGER_INCIDENTIO=true
                shift
                ;;
            --incidentio-delay)
                incidentio_delay="$2"
                shift 2
                ;;
            --kube|-k)
                use_kube=true
                shift
                ;;
            *)
                scenario_args+=("$1")
                shift
                ;;
        esac
    done
    
    # Special handling for meta-commands
    case "$scenario" in
        list-active)
            check_status
            return 0
            ;;
        clear-all)
            clear_all
            return 0
            ;;
    esac
    
    print_info "Triggering incident: ${scenario}"
    
    # Kubernetes mode: directly set the flag
    if [ "$use_kube" = true ]; then
        local flag_config
        flag_config=$(get_scenario_flag "$scenario" "${scenario_args[0]:-}")
        
        if [ -z "$flag_config" ]; then
            print_error "Unknown scenario for Kubernetes mode: $scenario"
            return 1
        fi
        
        local flag_name flag_variant
        flag_name=$(echo "$flag_config" | cut -d'|' -f1)
        flag_variant=$(echo "$flag_config" | cut -d'|' -f2)
        
        if kube_set_flag "$flag_name" "$flag_variant"; then
            print_success "Incident triggered on Kubernetes"
        else
            print_error "Failed to trigger incident on Kubernetes"
            return 1
        fi
    else
        # Local mode: run the scenario script
    local script
    script=$(get_scenario_script "$scenario") || return 1
    
    if [ ! -x "$script" ]; then
        chmod +x "$script"
    fi
    
        if ! "$script" "${scenario_args[@]:-}"; then
            print_error "Failed to trigger incident"
            return 1
        fi
        print_success "Incident triggered successfully (local)"
    fi
    
    # Trigger incident.io if requested
    if [ "$TRIGGER_INCIDENTIO" = true ]; then
        echo ""
        trigger_incidentio_alert "$scenario" "$incidentio_delay"
    fi
    
    echo ""
    if [ "$use_kube" = true ]; then
        print_info "Monitor on Coralogix or run: $0 --status --kube"
    else
        print_info "Monitor the effects:"
        echo "  • Grafana:    http://localhost:8080/grafana"
        echo "  • Prometheus: http://localhost:9090"
        echo "  • Jaeger:     http://localhost:8080/jaeger/ui"
    fi
    echo ""
    print_info "To clear: $0 clear-all$([ "$use_kube" = true ] && echo ' --kube')"
}

# Main logic
main() {
    # Parse arguments
    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi
    
    # Pre-parse for global flags
    local args=()
    while [[ $# -gt 0 ]]; do
    case "$1" in
        --help|-h)
            show_help
            exit 0
            ;;
        --list|-l)
            list_scenarios
            exit 0
            ;;
            --kube|-k)
                KUBE_MODE=true
                shift
                ;;
            --namespace)
                KUBE_NAMESPACE="$2"
                shift 2
                ;;
        --status|-s)
                # Need to check if --kube was already parsed
                for arg in "$@"; do
                    if [[ "$arg" == "--kube" || "$arg" == "-k" ]]; then
                        KUBE_MODE=true
                    fi
                done
            check_status
            exit 0
            ;;
            --incidentio)
                TRIGGER_INCIDENTIO=true
                shift
                ;;
            --incidentio-delay)
                INCIDENTIO_DELAY="$2"
                shift 2
            ;;
        *)
                args+=("$1")
                shift
            ;;
    esac
    done
    
    # Need at least a scenario
    if [ ${#args[@]} -eq 0 ]; then
        print_error "No scenario specified"
        show_help
        exit 1
    fi
    
    # Build extra flags to pass
    local extra_flags=()
    if [ "$TRIGGER_INCIDENTIO" = true ]; then
        extra_flags+=(--incidentio --incidentio-delay "$INCIDENTIO_DELAY")
    fi
    if [ "$KUBE_MODE" = true ]; then
        extra_flags+=(--kube)
    fi
    
    # Trigger the scenario
    trigger_scenario "${args[@]}" "${extra_flags[@]:-}"
}

# Run main
main "$@"

