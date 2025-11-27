#!/bin/bash
# IncidentFox: Master incident trigger script
# 
# This script provides a unified interface for triggering various incident scenarios
# in the OpenTelemetry Demo by manipulating feature flags.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENARIOS_DIR="${SCRIPT_DIR}/scenarios"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
FLAGD_CONFIG="${REPO_ROOT}/src/flagd/demo.flagd.json"

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

Examples:
  # Trigger a high CPU incident
  $0 high-cpu
  
  # Trigger service failure with specific rate
  $0 service-failure 50%
  
  # Clear all incidents
  $0 clear-all
  
  # Check what's currently active
  $0 --status

Environment Variables:
  KUBE_CONTEXT          Kubernetes context to use (for --kube mode)
  KUBE_NAMESPACE        Kubernetes namespace (default: otel-demo)

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
    print_info "Checking current incident status..."
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
    print_info "Clearing all active incidents..."
    
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
    local args=("$@")
    
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
    
    # Get the scenario script
    local script
    script=$(get_scenario_script "$scenario") || return 1
    
    # Check if script is executable
    if [ ! -x "$script" ]; then
        chmod +x "$script"
    fi
    
    print_info "Triggering incident: ${scenario}"
    
    # Execute the scenario script
    if "$script" "${args[@]}"; then
        print_success "Incident triggered successfully"
        print_info "Monitor the effects:"
        echo "  • Grafana:    http://localhost:8080/grafana"
        echo "  • Prometheus: http://localhost:9090"
        echo "  • Jaeger:     http://localhost:8080/jaeger/ui"
        echo ""
        print_info "To clear this incident: $0 clear-all"
    else
        print_error "Failed to trigger incident"
        return 1
    fi
}

# Main logic
main() {
    # Parse arguments
    if [ $# -eq 0 ]; then
        show_help
        exit 0
    fi
    
    case "$1" in
        --help|-h)
            show_help
            exit 0
            ;;
        --list|-l)
            list_scenarios
            exit 0
            ;;
        --status|-s)
            check_status
            exit 0
            ;;
        --*)
            print_error "Unknown option: $1"
            show_help
            exit 1
            ;;
        *)
            # Trigger the scenario
            trigger_scenario "$@"
            ;;
    esac
}

# Run main
main "$@"

