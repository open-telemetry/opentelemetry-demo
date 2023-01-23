#!/usr/bin/env bash
# A thin wrapper around "docker-compose" that merges multiple environments files before
# running any commands.
set -euxo pipefail

# Change to the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "${SCRIPT_DIR}"

ENV_GLOBAL=".env"
ENV_SENTRY=".env.sentry"
ENV_MERGED=".env.merged"

if [[ ! -f "${ENV_SENTRY}" ]]; then
    touch "${ENV_SENTRY}"
fi

# Merge env files
cat "${ENV_GLOBAL}" "${ENV_SENTRY}" > "${ENV_MERGED}"
ENV_FILE_ARGS=(--env-file "${ENV_MERGED}")

# Organize compose override files
OVERRIDE_ARGS=(
    --file
    docker-compose.yml
    --file
    docker-compose.sentry.yml
)
if [[ -f "docker-compose.override.yml" ]]; then
    OVERRIDE_ARGS+=(
        --file
        docker-compose.override.yml
    )
fi

docker-compose "${ENV_FILE_ARGS[@]}" "${OVERRIDE_ARGS[@]}" "$@"
