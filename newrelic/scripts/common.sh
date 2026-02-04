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
NR_K8S_CHART_VERSION="0.10.0"
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

# Generic function to prompt for environment variables
# Usage: prompt_for_env_var VAR_NAME PROMPT_TEXT REQUIRED
prompt_for_env_var() {
  local var_name="$1"
  local prompt_text="$2"
  local required="${3:-false}"

  set +u
  local current_value="${!var_name}"

  if [ -z "$current_value" ]; then
    echo -n "$prompt_text: "
    read -r input_value
    if [ -n "$input_value" ]; then
      eval "export $var_name=\"$input_value\""
    fi
  else
    echo "Using $var_name from environment variable."
  fi

  # Check if required and empty
  current_value="${!var_name}"
  if [ "$required" = "true" ] && [ -z "$current_value" ]; then
    echo "Error: $var_name is required but empty."
    exit 1
  fi

  set -u
}

# Validate and normalize yes/no answers
# Usage: validate_yesno_answer VAR_NAME
validate_yesno_answer() {
  local var_name="$1"

  set +u
  local current_value="${!var_name}"

  # If already set to y or n, no validation needed
  if [ "$current_value" = "y" ] || [ "$current_value" = "n" ]; then
    set -u
    return
  fi

  # Normalize and validate the answer
  case "$current_value" in
    [yY]|[yY][eE][sS])
      eval "export $var_name=\"y\""
      ;;
    [nN]|[nN][oO])
      eval "export $var_name=\"n\""
      ;;
    *)
      echo "Error: Invalid value '$current_value' for $var_name. Must be 'y' or 'n'."
      exit 1
      ;;
  esac

  set -u
}

# Set NEW_RELIC_LICENSE_KEY variable from environment or prompt user
prompt_for_license_key() {
  prompt_for_env_var "NEW_RELIC_LICENSE_KEY" "Please enter your New Relic License Key" true
}

# Set NEW_RELIC_API_KEY variable from environment or prompt user
prompt_for_api_key() {
  prompt_for_env_var "NEW_RELIC_API_KEY" "Please enter your New Relic API Key" true
}

# Set NEW_RELIC_ACCOUNT_ID variable from environment or prompt user
prompt_for_account_id() {
  prompt_for_env_var "NEW_RELIC_ACCOUNT_ID" "Please enter your New Relic Account ID" true
}

# Prompt user to confirm if installation is for an OpenShift cluster
prompt_for_openshift() {
  prompt_for_env_var "IS_OPENSHIFT_CLUSTER" "Is this installation for an OpenShift cluster? (y/n, default: n)" false
  validate_yesno_answer "IS_OPENSHIFT_CLUSTER"
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
