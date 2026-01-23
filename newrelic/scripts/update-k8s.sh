#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# update-k8s.sh
#
# Purpose:
#   Updates the OpenTelemetry Demo and New Relic K8s Helm chart versions,
#   and generates their Kubernetes manifests for deployment.
#   Should be run after syncing with the latest upstream changes.
#
# How to run:
#   ./update-k8s.sh
#   (Run from the newrelic/scripts directory)
#
# Environment variables:
#   TARGET_REPO       - Optional. GitHub repository to create the pull request
#                       against in the format 'owner/repo'. Defaults to
#                       'newrelic/opentelemetry-demo'.
#   GH_TOKEN or GITHUB_TOKEN - Required. GitHub token with permissions to create
#                              issues and pull requests. gh auth login can also
#                              be used to authenticate the GitHub CLI prior to
#                              running this script. When used in GitHub Actions,
#                              the token should also have permissions to modify
#                              repository contents.
#
# Dependencies:
#   - helm
#   - yq (YAML processor)
#   - gh (GitHub CLI)
#   - Access to the project source and Helm values files
# -----------------------------------------------------------------------------
set -euo pipefail

source "$(dirname "$0")/common.sh"

check_tool_installed helm
check_tool_installed yq
check_tool_installed gh

template_chart() {
    local release="$1"
    local chart="$2"
    local version="$3"
    local namespace="$4"
    local values="$5"
    local output="$6"
    helm template "$release" "$chart" --version "$version" -n "$namespace" --create-namespace -f "$values" > "$output"
}

update_version_in_script() {
    local var_name="$1"
    local version="$2"
    local script="$3"
    if [ -f "$script" ]; then
        sed -i '' "s/^$var_name=.*/$var_name=\"$version\"/" "$script"
        echo "Updated $var_name in $script to $version"
    fi
}

ensure_helm_repo "newrelic" "https://helm-charts.newrelic.com"
ensure_helm_repo "open-telemetry" "https://open-telemetry.github.io/opentelemetry-helm-charts"

check_file_exists "$OTEL_DEMO_VALUES_PATH"
check_file_exists "$NR_K8S_VALUES_PATH"

LATEST_OTEL_DEMO_CHART_VERSION=$(helm search repo open-telemetry/opentelemetry-demo --versions | awk 'NR==2 {print $2}')
CURR_OTEL_DEMO_CHART_VERSION=$(cat $COMMON_SCRIPT_PATH | sed -n 's/^OTEL_DEMO_CHART_VERSION="\([0-9]\{1,\}\.[0-9]\{1,\}\.[0-9]\{1,\}\)"$/\1/p')

echo "Latest OpenTelemetry Demo chart version: $LATEST_OTEL_DEMO_CHART_VERSION"
echo "Current OpenTelemetry Demo chart version: $CURR_OTEL_DEMO_CHART_VERSION"

OTEL_DEMO_UPDATED=false

if [ "$LATEST_OTEL_DEMO_CHART_VERSION" != "" ] && [ "$LATEST_OTEL_DEMO_CHART_VERSION" != "$CURR_OTEL_DEMO_CHART_VERSION" ]; then
  echo "Updating opentelemetry-demo chart version to $LATEST_OTEL_DEMO_CHART_VERSION"
  template_chart "otel-demo" "open-telemetry/opentelemetry-demo" "$LATEST_OTEL_DEMO_CHART_VERSION" "opentelemetry-demo" "$OTEL_DEMO_VALUES_PATH" "$OTEL_DEMO_RENDER_PATH"
  update_version_in_script "OTEL_DEMO_CHART_VERSION" "$LATEST_OTEL_DEMO_CHART_VERSION" "$COMMON_SCRIPT_PATH"
  echo "Completed updating the OpenTelemetry Demo app!"
  OTEL_DEMO_UPDATED=true
else
  echo "opentelemetry-demo chart is up to date."
fi

LATEST_NR_K8S_CHART_VERSION=$(helm search repo newrelic/nr-k8s-otel-collector --versions | awk 'NR==2 {print $2}')
CURR_NR_K8S_CHART_VERSION=$(cat $COMMON_SCRIPT_PATH | sed -n 's/^NR_K8S_CHART_VERSION="\([0-9]\{1,\}\.[0-9]\{1,\}\.[0-9]\{1,\}\)"$/\1/p')

echo "Latest New Relic K8s chart version: $LATEST_NR_K8S_CHART_VERSION"
echo "Current New Relic K8s chart version: $CURR_NR_K8S_CHART_VERSION"

NR_K8S_UPDATED=false

if [ "$LATEST_NR_K8S_CHART_VERSION" != "" ] && [ "$LATEST_NR_K8S_CHART_VERSION" != "$CURR_NR_K8S_CHART_VERSION" ]; then
  echo "Updating NR K8s chart version to $LATEST_NR_K8S_CHART_VERSION"
  template_chart "nr-k8s-otel-collector" "newrelic/nr-k8s-otel-collector" "$LATEST_NR_K8S_CHART_VERSION" "opentelemetry-demo" "$NR_K8S_VALUES_PATH" "$NR_K8S_RENDER_PATH"
  update_version_in_script "NR_K8S_CHART_VERSION" "$LATEST_NR_K8S_CHART_VERSION" "$COMMON_SCRIPT_PATH"
  echo "Completed updating the New Relic K8s instrumentation!"
  NR_K8S_UPDATED=true
else
  echo "NR K8s chart is up to date."
fi

if [ "$OTEL_DEMO_UPDATED" = false ] && [ "$NR_K8S_UPDATED" = false ]; then
  echo "No updates were necessary. Charts are up to date."
fi

TARGET_REPO="${TARGET_REPO:-newrelic/opentelemetry-demo}"
REPO_OWNER=$(parse_repo_owner)

COMMIT_DESC=""
BODY_DESC=""

if [ "$OTEL_DEMO_UPDATED" = true ]; then
  COMMIT_DESC+="otel-demo $LATEST_OTEL_DEMO_CHART_VERSION"
  BODY_DESC+="* opentelemetry-demo-$LATEST_OTEL_DEMO_CHART_VERSION"$'\n'
fi

if [ "$NR_K8S_UPDATED" = true ]; then
  if [ -n "$COMMIT_DESC" ]; then
    COMMIT_DESC+=","
  fi
  COMMIT_DESC+="nr-k8s $LATEST_NR_K8S_CHART_VERSION"
  BODY_DESC+="* nr-k8s-otel-collector-$LATEST_NR_K8S_CHART_VERSION"$'\n'
fi

COMMIT_MSG="chore: update chart versions - $COMMIT_DESC"
PR_BODY=$(cat <<EOF
This PR was generated on $TS_FULL by update-k8s.sh to update chart versions.

**Updates:**
$BODY_DESC
EOF
)

git checkout -b chore/update-chart-versions_$TS
git commit -a -m "$COMMIT_MSG"
git push -u origin chore/update-chart-versions_$TS

gh pr create --head $REPO_OWNER:chore/update-chart-versions_$TS \
  --title "$COMMIT_MSG" \
  --body "$PR_BODY" \
  --base main \
  --repo $TARGET_REPO

if [ $? -ne 0 ]; then
  echo "create pull request against $TARGET_REPO failed"
  exit 1
else
  echo "pull request for chart version updates created successfully against $TARGET_REPO"
fi

echo "chart version updates completed successfully"
