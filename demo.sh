#!/bin/sh

set -eu

# Constants
ELASTIC_STACK_VERSION="9.5.3"
ENV_OVERRIDE_FILE=".env.override"
NAMESPACE="opentelemetry-operator-system"
HELM_REPO_NAME="open-telemetry"
HELM_REPO_URL='https://open-telemetry.github.io/opentelemetry-helm-charts'

DEMO_RELEASE="my-otel-demo"
DEMO_CHART="open-telemetry/opentelemetry-demo"
DEMO_HELM_VERSION='0.40.7'

KUBE_STACK_RELEASE="opentelemetry-kube-stack"
KUBE_STACK_CHART="open-telemetry/opentelemetry-kube-stack"
KUBE_STACK_VERSION='0.14.12'
KUBE_STACK_VALUES_URL='https://raw.githubusercontent.com/elastic/elastic-agent/refs/tags/v'$ELASTIC_STACK_VERSION'/deploy/helm/edot-collector/kube-stack/values.yaml'
SECRET_NAME='elastic-secret-otel'

DOCKER_COLLECTOR_CONFIG='./src/otel-collector/otelcol-elastic-config.yaml'
COLLECTOR_CONTRIB_IMAGE=docker.elastic.co/elastic-agent/elastic-agent:$ELASTIC_STACK_VERSION

# Detect sed variant: GNU sed uses --version, BSD sed doesn't
# GNU sed: sed -i (no empty string needed)
# BSD sed: sed -i '' (empty string required)
if sed --version >/dev/null 2>&1; then
  SED_IS_BSD="false"
else
  SED_IS_BSD="true"
fi

# Portable sed in-place editing function
# Usage: sed_in_place "s/pattern/replacement/g" file
sed_in_place() {
  if [ "$SED_IS_BSD" = "true" ]; then
    sed -i '' "$@"
  else
    sed -i "$@"
  fi
}

# Variables
platform=""
destroy="false"
self_hosted="false"
upstream="false"
elastic_otlp_endpoint=""
elastic_otlp_api_key=""

usage() {
  echo "Usage: $0 [docker|k8s] [self-hosted]"
  echo
  echo "Options:"
  echo "  docker              Deploy to Docker (requires Elastic Cloud credentials)"
  echo "  docker self-hosted  Deploy to Docker with local start-local backend"
  echo "  docker upstream     Deploy to Docker with no EDOT, vanilla OTel"
  echo "  k8s                 Deploy to Kubernetes"
  echo "  k8s upstream        Deploy to Kubernetes with no EDOT, vanilla OTel"
  echo
  echo "Self-hosted mode requires start-local with EDOT:"
  echo "  curl -fsSL https://elastic.co/start-local | sh -s -- --edot"
  echo
  echo "To destroy: $0 destroy [docker|k8s]"
  exit 1
}

parse_args() {
  # Support legacy 3-argument format for CI/tests
  if [ -n "${CI:-}" ] && [ $# -eq 3 ] && [ "${1#-}" = "$1" ]; then
    # First arg doesn't start with dash, assume legacy positional format
    platform="$1"
    elastic_otlp_endpoint="$2"
    elastic_otlp_api_key="$3"
    return
  fi

  while [ $# -gt 0 ]; do
    case "$1" in
      k8s) platform="k8s"; shift ;;
      docker) platform="docker"; shift ;;
      self-hosted) self_hosted="true"; shift ;;
      upstream) upstream="true"; shift;;
      destroy)
        destroy="true"
        shift;
        if [ "${1:-}" = "docker" ] || [ "${1:-}" = "k8s" ]; then
          platform="$1"
          shift
        fi
        ;;
      *) shift ;;
    esac
  done
}

update_env_var() {
  VAR="$1"
  VAL="$2"
  tmp=$(mktemp) || exit 1

  if grep -q "^$VAR=" "$ENV_OVERRIDE_FILE"; then
    sed_in_place "s|^$VAR=.*|$VAR=\"$VAL\"|" "$ENV_OVERRIDE_FILE"
  else
    echo "$VAR=\"$VAL\"" >>"$ENV_OVERRIDE_FILE"
  fi
}

# Read a secret from the terminal without echo and assign it to a variable by name
# Usage: read_secret variable_name "Prompt: "
read_secret() {
  var_name="$1"
  prompt="$2"
  printf "%s" "$prompt"
  stty -echo 2>/dev/null || :
  trap 'stty echo 2>/dev/null' 0 INT TERM HUP
  read -r "${var_name?}"
  stty echo 2>/dev/null || :
  trap - 0 INT TERM HUP
  echo
}

ensure_env_values() {
  if [ -n "${CI:-}" ]; then
    return 0
  fi

  echo
  if ! check_existing_credentials; then
    if [ -z "$elastic_otlp_endpoint" ]; then
      printf "🔑 Enter your Elastic OTLP endpoint: "
      read -r elastic_otlp_endpoint
    fi
  fi

  if [ -z "$elastic_otlp_api_key" ]; then
    read_secret elastic_otlp_api_key "🔑 Enter your Elastic API key: "
  fi
  echo
}

check_existing_credentials() {
  if [ ! -f "$ENV_OVERRIDE_FILE" ]; then
    return 1
  fi

  elastic_otlp_endpoint=$(grep "^ELASTIC_OTLP_ENDPOINT=" "$ENV_OVERRIDE_FILE" | cut -d'=' -f2- | tr -d '"')
  elastic_otlp_api_key=$(grep "^ELASTIC_OTLP_API_KEY=" "$ENV_OVERRIDE_FILE" | cut -d'=' -f2- | tr -d '"')

  if [ -n "$elastic_otlp_endpoint" ] && [ -n "$elastic_otlp_api_key" ] &&
    [ "$elastic_otlp_endpoint" != "YOUR_ENDPOINT" ] &&
    [ "$elastic_otlp_api_key" != "YOUR_API_KEY" ]; then
    echo "✅ Using existing credentials from $ENV_OVERRIDE_FILE"
    return 0
  fi

  elastic_otlp_endpoint=""
  elastic_otlp_api_key=""
  return 1
}

start_docker() {
  ensure_env_values

  update_env_var "ELASTIC_OTLP_ENDPOINT" "$elastic_otlp_endpoint"
  update_env_var "ELASTIC_OTLP_API_KEY" "$elastic_otlp_api_key"
  update_env_var "OTEL_COLLECTOR_CONFIG" "$DOCKER_COLLECTOR_CONFIG"
  update_env_var "COLLECTOR_CONTRIB_IMAGE" "$COLLECTOR_CONTRIB_IMAGE"

  export ELASTIC_OTLP_ENDPOINT="$elastic_otlp_endpoint"
  export ELASTIC_OTLP_API_KEY="$elastic_otlp_api_key"

  make start
}

start_docker_upstream() {
  ensure_env_values

  export ELASTIC_OTLP_ENDPOINT="$elastic_otlp_endpoint"
  export ELASTIC_OTLP_API_KEY="$elastic_otlp_api_key"

  export OTEL_COLLECTOR_CONFIG_EXTRAS="./src/otel-collector/otelcol-config-extras-elastic.yml"

  # Here we use docker compose instead of make start as we do not want to use the .env.override file.
  # This allows us to run the upstream demo, no EDOT collector and no EDOT SDKs.
  docker compose --env-file .env \
    -f docker-compose.yml \
    -f docker-compose.elastic.yml \
    up --force-recreate --remove-orphans --detach
}

start_docker_self_hosted() {
  echo
  echo "🏠 Self-hosted mode: forwarding telemetry to local start-local collector"
  echo

  update_env_var "COLLECTOR_CONTRIB_IMAGE" "$COLLECTOR_CONTRIB_IMAGE"

  # Use docker compose with the self-hosted override file to connect
  # the otel-collector to the elastic-start-local network
  docker compose --env-file .env --env-file .env.override \
    -f docker-compose.yml \
    -f docker-compose.elastic-self-hosted.yml \
    up --force-recreate --remove-orphans --detach

  echo ""
  echo "OpenTelemetry Demo is running."
  echo "Go to http://localhost:8080 for the demo UI."
}

ensure_k8s_prereqs() {
  helm repo add "$HELM_REPO_NAME" "$HELM_REPO_URL" --force-update
  kubectl create namespace "$NAMESPACE" --dry-run=client -o yaml | kubectl apply -f -
}

apply_k8s_secret() {
  ensure_env_values
  kubectl create secret generic "$SECRET_NAME" \
    --namespace "$NAMESPACE" \
    --from-literal=elastic_endpoint="$elastic_otlp_endpoint" \
    --from-literal=elastic_api_key="$elastic_otlp_api_key" \
    --dry-run=client -o yaml | kubectl apply -f -
}

install_kube_stack() {
  helm upgrade --install "$KUBE_STACK_RELEASE" "$KUBE_STACK_CHART" \
    --namespace "$NAMESPACE" \
    --values "$KUBE_STACK_VALUES_URL" \
    --values kubernetes/elastic-helm/kube-stack-overrides.yml \
    --version "$KUBE_STACK_VERSION"
}

install_demo_chart() {
  helm upgrade --install "$DEMO_RELEASE" "$DEMO_CHART" --version "$DEMO_HELM_VERSION" -f kubernetes/elastic-helm/demo.yml
}

start_k8s() {
  ensure_k8s_prereqs
  apply_k8s_secret

  update_env_var "ELASTIC_OTLP_ENDPOINT" "$elastic_otlp_endpoint"
  update_env_var "ELASTIC_OTLP_API_KEY" "$elastic_otlp_api_key"

  install_kube_stack
  install_demo_chart
}

start_k8s_upstream() {
  ensure_env_values

  export ELASTIC_OTLP_ENDPOINT="$elastic_otlp_endpoint"
  export ELASTIC_OTLP_API_KEY="$elastic_otlp_api_key"

  kubectl create secret generic elastic-secret-otel \
    --from-literal=elastic_otlp_endpoint="$elastic_otlp_endpoint" \
    --from-literal=elastic_api_key="$elastic_otlp_api_key" \
    --dry-run=client -o yaml | kubectl apply -f -

  helm repo add open-telemetry https://open-telemetry.github.io/opentelemetry-helm-charts
  helm install my-otel-demo open-telemetry/opentelemetry-demo -f ./kubernetes/elastic-helm/demo-upstream.yml
}

destroy_docker() {
  echo
  make stop
  echo
}

destroy_k8s() {
  echo
  helm uninstall "$DEMO_RELEASE" --ignore-not-found
  helm uninstall "$KUBE_STACK_RELEASE" -n "$NAMESPACE" --ignore-not-found
  kubectl delete secret "$SECRET_NAME" -n "$NAMESPACE" --ignore-not-found
  kubectl delete namespace "$NAMESPACE" --ignore-not-found --wait=false --timeout=60s
  echo
}

main() {
  echo '----------------------------------------------------'
  echo '🚀 OpenTelemetry Demo with Elastic Observability'
  echo '----------------------------------------------------'

  parse_args "$@"

  if [ "$destroy" = "true" ]; then
    if [ -z "$platform" ]; then
      echo "⌛️ Destroying Docker and Kubernetes resources..."
      destroy_docker
      destroy_k8s
      echo "✅ Done! Destroyed Docker and Kubernetes resources."
      exit 0
    fi

    if [ "$platform" = "docker" ]; then
      echo "⌛️ Destroying Docker resources..."
      destroy_docker
      echo "✅ Done! Destroyed Docker resources."
      exit 0
    fi

    if [ "$platform" = "k8s" ]; then
      echo "⌛️ Destroying Kubernetes resources..."
      destroy_k8s
      echo "✅ Done! Destroyed Kubernetes resources."
      exit 0
    fi

    usage
  fi

  if [ "$platform" != "docker" ] && [ "$platform" != "k8s" ]; then
    usage
  fi

  echo
  if [ "$self_hosted" = "true" ]; then
    echo "⌛️ Starting OTel Demo + EDOT on '$platform' (self-hosted mode)..."
  elif [ "$upstream" = "true" ]; then
    echo "⌛️ Starting OTel Demo '$platform' (no EDOT)..."
  else
    echo "⌛️ Starting OTel Demo + EDOT on '$platform'..."
  fi

  if [ "$platform" = "docker" ]; then
    if [ "$self_hosted" = "true" ]; then
      start_docker_self_hosted
    elif [ "$upstream" = "true" ]; then
      start_docker_upstream
    else
      start_docker
    fi
  else
    if [ "$upstream" = "true" ]; then
      start_k8s_upstream
    else
      start_k8s
    fi
  fi
  echo
  if [ "$self_hosted" = "true" ]; then
    echo "🎉 OTel Demo and EDOT are running on '$platform'; data is flowing to local Elasticsearch."
    echo
    echo "📊 Open Kibana at http://localhost:5601"
    echo "🛒 Open Demo at http://localhost:8080"
  elif [ "$upstream" = "true" ]; then
    echo "🎉 OTel Demo and OTel collector are running on '$platform'; data is flowing to Elastic."
  else
    echo "🎉 OTel Demo and EDOT are running on '$platform'; data is flowing to Elastic."
  fi
}

main "$@"
