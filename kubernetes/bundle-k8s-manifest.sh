#!/usr/bin/env bash
# bundle-k8s.sh (bash-compatible)
# Combine *.yml/*.yaml into one multi-document YAML, ordered by kind.

set -euo pipefail

print_help() {
  cat <<'EOF'
Usage: bundle-k8s.sh -i INPUT_DIR [-o OUTPUT_FILE] [-v VERSION] [-h]

Combine all Kubernetes manifest YAMLs from INPUT_DIR into OUTPUT_FILE,
ordered by resource kind.

Required:
  -i INPUT_DIR    Input directory containing YAML manifests

Optional:
  -o OUTPUT_FILE  Output file (default: deployment.yaml)
  -v VERSION      OpenTelemetry version variable (stored only; not applied yet)
  -h              Show this help and exit

Examples:
  ./bundle-k8s.sh -i ./manifests
  ./bundle-k8s.sh -i ./yamls -o all.yaml -v 1.30.1
EOF
}

# Defaults
INPUT_DIR=""
OUTPUT_FILE="deployment.yaml"
OTEL_VERSION=""

# Parse options (positional args are ignored by design)
while getopts ":hi:o:v:" opt; do
  case "$opt" in
    h) print_help; exit 0 ;;
    i) INPUT_DIR="$OPTARG" ;;
    o) OUTPUT_FILE="$OPTARG" ;;
    v) OTEL_VERSION="$OPTARG" ;;
    \?) echo "Unknown option: -$OPTARG" >&2; print_help; exit 1 ;;
    :)  echo "Option -$OPTARG requires an argument." >&2; print_help; exit 1 ;;
  esac
done

# Require -i
if [[ -z "${INPUT_DIR}" ]]; then
  echo "Error: -i INPUT_DIR is required." >&2
  print_help
  exit 1
fi
if [[ ! -d "${INPUT_DIR}" ]]; then
  echo "Input directory not found: ${INPUT_DIR}" >&2
  exit 1
fi

# Ensure output directory exists (if a path with directories was provided)
outdir="$(dirname -- "${OUTPUT_FILE}")"
if [[ -n "${outdir}" && "${outdir}" != "." ]]; then
  mkdir -p "${outdir}"
fi

echo "Input dir: ${INPUT_DIR}"
echo "Output file: ${OUTPUT_FILE}"
if [[ -n "${OTEL_VERSION}" ]]; then
  echo "OTEL_VERSION set to: ${OTEL_VERSION}"
fi

# Kind ordering (bash/macOS compatible)
kind_weight() {
  local k
  k="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  case "$k" in
    customresourcedefinition) echo 10 ;;
    namespace)                echo 20 ;;
    storageclass)             echo 25 ;;
    priorityclass)            echo 28 ;;
    serviceaccount)           echo 30 ;;
    clusterrole)              echo 35 ;;
    clusterrolebinding)       echo 36 ;;
    role)                     echo 37 ;;
    rolebinding)              echo 38 ;;
    podsecuritypolicy)        echo 39 ;;
    configmap)                echo 40 ;;
    secret)                   echo 41 ;;
    service)                  echo 45 ;;
    endpointslice|endpoints)  echo 46 ;;
    ingressclass)             echo 47 ;;
    ingress)                  echo 48 ;;
    networkpolicy)            echo 49 ;;
    poddisruptionbudget)      echo 50 ;;
    daemonset)                echo 60 ;;
    statefulset)              echo 61 ;;
    deployment)               echo 62 ;;
    job)                      echo 63 ;;
    cronjob)                  echo 64 ;;
    horizontalpodautoscaler)  echo 70 ;;
    destinationrule|virtualservice|gateway) echo 75 ;;
    mutatingwebhookconfiguration|validatingwebhookconfiguration) echo 80 ;;
    kustomization)            echo 99 ;;
    *)                        echo 90 ;;
  esac
}

TMPLIST="$(mktemp)"; trap 'rm -f "$TMPLIST"' EXIT

# Collect YAML files (handle spaces/newlines safely). Avoid GNU sort -z for macOS.
declare -a files=()
while IFS= read -r -d '' f; do
  files+=("$f")
done < <(find "${INPUT_DIR}" -type f \( -iname '*.yaml' -o -iname '*.yml' \) -print0)

if [[ "${#files[@]}" -eq 0 ]]; then
  echo "No YAML files found in ${INPUT_DIR}" >&2
  exit 1
fi

# Determine kind and weight for each file
for f in "${files[@]}"; do
  kind="$(
    LC_ALL=C sed -n 's/^[[:space:]]*[Kk][Ii][Nn][Dd][[:space:]]*:[[:space:]]*\([A-Za-z0-9_.-][A-Za-z0-9_.-]*\).*/\1/p' "$f" | head -n1
  )"
  [[ -z "${kind:-}" ]] && kind="Unknown"
  w="$(kind_weight "$kind")"
  printf "%s\t%s\t%s\n" "$w" "$f" "$kind" >> "$TMPLIST"
done

# Sort by weight, then filename (portable, no mapfile required)
sorted=()
while IFS= read -r line; do
  sorted+=("$line")
done < <(sort -t $'\t' -k1,1n -k2,2 "$TMPLIST")

{
  echo "# Generated on $(date -u +'%Y-%m-%dT%H:%M:%SZ')"
  echo "# Input directory: ${INPUT_DIR}"
  if [[ -n "${OTEL_VERSION}" ]]; then
    echo "# OpenTelemetry version: ${OTEL_VERSION}"
  fi
} > "${OUTPUT_FILE}"

first=1
for line in "${sorted[@]}"; do
  IFS=$'\t' read -r weight fpath kind <<< "$line"

  if [[ $first -eq 1 ]]; then
    first=0
  else
    echo "---" >> "${OUTPUT_FILE}"
  fi

  echo "# Source: ${fpath}" >> "${OUTPUT_FILE}"

  # Append file contents, stripping a leading UTF-8 BOM if present
  if dd if="${fpath}" bs=3 count=1 2>/dev/null | grep -q $'\xEF\xBB\xBF'; then
    tail -c +4 "${fpath}" >> "${OUTPUT_FILE}"
  else
    cat "${fpath}" >> "${OUTPUT_FILE}"
  fi
done

echo "Wrote $(wc -l < "${OUTPUT_FILE}") lines to ${OUTPUT_FILE}"