#!/bin/bash
DOCKER_BUILDKIT=1 docker build . -f ./src/$1/Dockerfile -t ghcr.io/middleware-labs/otel-demo-$1:latest
docker push ghcr.io/middleware-labs/otel-demo-$1:latest