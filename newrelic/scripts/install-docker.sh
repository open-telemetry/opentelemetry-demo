#!/bin/bash

# Check if helm is installed
if ! command -v docker &> /dev/null; then
    echo "Error: docker is not installed or not in PATH. Please install docker and try again."
    exit 1
fi

# Prompt the user for input
echo -n "Please enter your New Relic License Key: "
read user_input

# Check if input is empty
if [ -z "$user_input" ]; then
    echo "Error: Empty key. Please enter your New Relic License Key."
    exit 1
fi

# Export the New Relic license key 
if ! export NEW_RELIC_LICENSE_KEY=$user_input; then
    echo "Error: Failed to export NEW_RELIC_LICENSE_KEY environment variable."
    exit 1
fi

# Run docker compose with comprehensive error handling
if ! docker compose --env-file ../../.env --env-file ../../.env.override --file ../docker/docker-compose.yml up --force-recreate --remove-orphans --detach; then
    echo "Error: Docker Compose deployment failed."
    echo "Possible reasons:"
    echo "  - Environment files not found"
    echo "  - Docker Compose configuration issue"
    echo "  - Insufficient permissions"
    echo "  - Docker daemon not running"
    exit 1
fi

# export NEW_RELIC_LICENSE_KEY=$user_input && docker compose --env-file ../../.env --env-file ../../.env.override --file ../docker/docker-compose.yml up --force-recreate --remove-orphans --detach