#!/bin/bash
set -euo pipefail

# General variables
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
SRC_DIR=${SRC_DIR:-"$SCRIPT_DIR/../../src"} #.env.override
COMMON_SCRIPT_PATH="$SCRIPT_DIR/common.sh"
TS=$(date +"%Y%m%d_%H%M%S")
TS_FULL=$(date +"%Y-%m-%d %H:%M:%S")

# Kubernetes variables
OTEL_DEMO_CHART_VERSION="0.40.2"
NR_K8S_CHART_VERSION="0.9.10"
OTEL_DEMO_RELEASE_NAME=otel-demo
NR_K8S_RELEASE_NAME=nr-k8s-otel-collector
OTEL_DEMO_NAMESPACE=opentelemetry-demo
NR_LICENSE_SECRET=newrelic-license-key
OTEL_DEMO_VALUES_PATH=${OTEL_DEMO_VALUES_PATH:-"$SCRIPT_DIR/../k8s/helm/opentelemetry-demo.yaml"}
OTEL_DEMO_RENDER_PATH=${OTEL_DEMO_RENDER_PATH:-"$SCRIPT_DIR/../k8s/rendered/opentelemetry-demo.yaml"}
NR_K8S_VALUES_PATH=${NR_K8S_VALUES_PATH:-"$SCRIPT_DIR/../k8s/helm/nr-k8s-otel-collector.yaml"}
NR_K8S_RENDER_PATH=${NR_K8S_RENDER_PATH:-"$SCRIPT_DIR/../k8s/rendered/nr-k8s-otel-collector.yaml"}

# Docker variables
DOCKER_COMPOSE_PATH=${DOCKER_COMPOSE_PATH:-"$SCRIPT_DIR/../../docker-compose.yml"}
NR_DOCKER_COMPOSE_PATH=${NR_DOCKER_COMPOSE_PATH:-"$SCRIPT_DIR/../docker/docker-compose.yml"}

# Check if required tools are installed and error out if not
check_tool_installed() {
    if ! command -v "$1" &> /dev/null; then
        echo "Error: $1 is not installed or not in PATH."
        exit 1
    fi
}

# Set NEW_RELIC_LICENSE_KEY variable from environment or prompt user
prompt_for_license_key() {
    set +u
    if [ -z "$NEW_RELIC_LICENSE_KEY" ]; then
        echo -n "Please enter your New Relic License Key: "
        read NEW_RELIC_LICENSE_KEY
    else
        echo "Using New Relic License Key from environment variable."
    fi
    if [ -z "$NEW_RELIC_LICENSE_KEY" ]; then
        echo "Error: Empty key. Please enter your New Relic License Key."
        exit 1
    fi
    set -u
}

# Check if a file exists and error out if not
check_file_exists() {
    if [ ! -f "$1" ]; then
        echo "Error: File $1 does not exist."
        exit 1
    fi
}

# Ensure Helm repository is added and updated
ensure_helm_repo() {
  local repo_name=$1
  local repo_url=$2
  if helm repo list | grep -q "$repo_name"; then
    echo "Helm repository '$repo_name' is already added."
  else
    helm repo add "$repo_name" "$repo_url"
  fi
  if ! helm repo update "$repo_name"; then
    echo "Error: Failed to update $repo_name Helm repository."
    exit 1
  fi
}

# Prompt user to confirm if installation is for an OpenShift cluster
prompt_for_openshift() {
  set +u
  if [ -z "$IS_OPENSHIFT_CLUSTER" ]; then
    while true; do
      echo -n "Is this installation for an OpenShift cluster? (y/n): "
      read -r response
      case "$response" in
        [yY]|[yY][eE][sS])
          IS_OPENSHIFT_CLUSTER="y"
          break
          ;;
        [nN]|[nN][oO])
          IS_OPENSHIFT_CLUSTER="n"
          break
          ;;
        *)
          echo "Please enter 'y' or 'n'."
          ;;
      esac
    done
  else
    echo "Using OpenShift cluster setting from environment variable (IS_OPENSHIFT_CLUSTER=$IS_OPENSHIFT_CLUSTER)."
  fi
  set -u
}

function sed_i() {
  if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS/BSD: needs the empty string argument
    sed -i '' "$@"
  else
    # Linux/GNU: standard -i
    sed -i "$@"
  fi
}

function parse_repo_owner() {
  local origin_repo_url=$(git config --get remote.origin.url)
  local ssh_regex='^git@github.com:([^/]+)/([^.]+)(\.git)?$'
  local https_regex='^https://github.com/([^/]+)/([^.]+)(\.git)?$'

  if [[ $origin_repo_url =~ $ssh_regex ]]; then
    echo "${BASH_REMATCH[1]}"
  elif [[ $origin_repo_url =~ $https_regex ]]; then
    echo "${BASH_REMATCH[1]}"
  else
    echo "unable to parse repository owner from URL: $origin_repo_url"
    exit 1
  fi
}
