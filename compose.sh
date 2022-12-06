#!/usr/bin/env bash
# A thin wrapper around "docker-compose" that merges multiple environments files before
# running any commands.
set -euxo pipefail

# Change to the script directory
cd "$(dirname "$(realpath "$0")")"

ENV_GLOBAL=".env"
ENV_SENTRY=".env.sentry"
ENV_MERGED=".env.merged"

if [[ ! -f "${ENV_SENTRY}" ]]; then
    touch "${ENV_SENTRY}"
fi

# Merge env files
cat "${ENV_GLOBAL}" "${ENV_SENTRY}" > "${ENV_MERGED}"

docker-compose --env-file "${ENV_MERGED}" "$@"
