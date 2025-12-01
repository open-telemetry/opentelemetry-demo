#!/bin/bash
set -e

REGISTRY="quay.io"
NAMESPACE="jeremyh"
SHOP_IMAGE="${REGISTRY}/${NAMESPACE}/shop-dc-shim:0.0.9"
LOAD_GEN_IMAGE="${REGISTRY}/${NAMESPACE}/shop-dc-load-generator:0.0.5"

# Build shop-dc-shim service
docker buildx build --platform linux/amd64 -t ${SHOP_IMAGE} -f ./Dockerfile --push --progress=plain .

# Build load generator
docker buildx build --platform linux/amd64 -t ${LOAD_GEN_IMAGE} -f ./load-generator/Dockerfile --push --progress=plain .

echo "Shop service: ${SHOP_IMAGE}"
echo "Load generator: ${LOAD_GEN_IMAGE}"
