#!/bin/bash
set -e

REGISTRY="quay.io"
NAMESPACE="jeremyh"
SHOP_IMAGE="${REGISTRY}/${NAMESPACE}/shop-dc-shim:0.0.9b"

# Build shop-dc-shim service
docker buildx build --platform linux/amd64 -t ${SHOP_IMAGE} -f ./Dockerfile --push --progress=plain .

echo "Shop service: ${SHOP_IMAGE}"
