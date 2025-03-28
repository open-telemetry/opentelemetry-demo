#!/bin/bash

# Check if helm is installed
if ! command -v docker &> /dev/null; then
    echo "Error: docker is not installed or not in PATH. Please install docker and try again."
    exit 1
fi

docker-compose --env-file ../../.env --env-file ../../.env.override --file ../docker/docker-compose.yml down