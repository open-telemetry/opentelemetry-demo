#!/bin/bash

if [ -z "$1" ]
then
    echo "Please provide a service name"
    exit 1
fi

docker compose build "$1"
docker compose stop "$1"
docker compose rm --force "$1"
docker compose create "$1"
docker compose start "$1"
