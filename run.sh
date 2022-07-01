#!/usr/bin/env bash

source .env

docker compose \
    -f ./docker-compose.oiq.yml \
    up \
    --remove-orphans \
    --force-recreate \
    -d
