#!/bin/bash
# Build and push payment image from AWS CloudShell
# This script should be run from AWS CloudShell to avoid local network issues with ECR
#
# Usage:
#   1. Open AWS CloudShell: https://console.aws.amazon.com/cloudshell/
#   2. Clone your repo or upload this script + the modified files
#   3. Run: ./build-payment-cloudshell.sh

set -euo pipefail

ECR_REPO="103002841599.dkr.ecr.us-west-2.amazonaws.com/otel-demo-payment"
TAG="${1:-v1}"

echo "=== Building payment image with error logging fix ==="

# Create temp directory
WORK_DIR=$(mktemp -d)
cd "$WORK_DIR"

# Create Dockerfile
cat > Dockerfile << 'DOCKERFILE_EOF'
FROM docker.io/library/node:22-slim AS builder
WORKDIR /usr/src/app/
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

FROM gcr.io/distroless/nodejs22-debian12:nonroot
WORKDIR /usr/src/app/
COPY --from=builder /usr/src/app/node_modules/ node_modules/
COPY demo.proto charge.js index.js logger.js opentelemetry.js ./
EXPOSE 8080
CMD ["--require=./opentelemetry.js", "index.js"]
DOCKERFILE_EOF

# Download files from the official OTel demo as base
echo "Downloading base files..."
BASE_URL="https://raw.githubusercontent.com/open-telemetry/opentelemetry-demo/main"
curl -sL "$BASE_URL/pb/demo.proto" -o demo.proto
curl -sL "$BASE_URL/src/payment/package.json" -o package.json
curl -sL "$BASE_URL/src/payment/package-lock.json" -o package-lock.json
curl -sL "$BASE_URL/src/payment/charge.js" -o charge.js
curl -sL "$BASE_URL/src/payment/logger.js" -o logger.js
curl -sL "$BASE_URL/src/payment/opentelemetry.js" -o opentelemetry.js

# Create the modified index.js with error logging (instead of warn)
cat > index.js << 'INDEXJS_EOF'
// Copyright The OpenTelemetry Authors
// SPDX-License-Identifier: Apache-2.0
const grpc = require('@grpc/grpc-js')
const protoLoader = require('@grpc/proto-loader')
const health = require('grpc-js-health-check')
const opentelemetry = require('@opentelemetry/api')

const charge = require('./charge')
const logger = require('./logger')

async function chargeServiceHandler(call, callback) {
  const span = opentelemetry.trace.getActiveSpan();

  try {
    const amount = call.request.amount
    span?.setAttributes({
      'app.payment.amount': parseFloat(`${amount.units}.${amount.nanos}`).toFixed(2)
    })
    // Log minimal info instead of full request to reduce log volume
    logger.info({ amount: `${call.request.amount?.units}.${call.request.amount?.nanos} ${call.request.amount?.currencyCode}` }, "Charge request received.")

    const response = await charge.charge(call.request)
    callback(null, response)

  } catch (err) {
    logger.error({ err })

    span?.recordException(err)
    span?.setStatus({ code: opentelemetry.SpanStatusCode.ERROR })
    callback(err)
  }
}

async function closeGracefully(signal) {
  server.forceShutdown()
  process.kill(process.pid, signal)
}

const otelDemoPackage = grpc.loadPackageDefinition(protoLoader.loadSync('demo.proto'))
const server = new grpc.Server()

server.addService(health.service, new health.Implementation({
  '': health.servingStatus.SERVING
}))

server.addService(otelDemoPackage.oteldemo.PaymentService.service, { charge: chargeServiceHandler })


let ip = "0.0.0.0";

const ipv6_enabled = process.env.IPV6_ENABLED;

if (ipv6_enabled == "true") {
  ip = "[::]";
  logger.info(`Overwriting Localhost IP: ${ip}`)
}

const address = ip + `:${process.env['PAYMENT_PORT']}`;

server.bindAsync(address, grpc.ServerCredentials.createInsecure(), (err, port) => {
  if (err) {
    return logger.error({ err })
  }

  logger.info(`payment gRPC server started on ${address}`)
})

process.once('SIGINT', closeGracefully)
process.once('SIGTERM', closeGracefully)
INDEXJS_EOF

echo "Files prepared. Building image..."

# Login to ECR
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin "$ECR_REPO"

# Build image
docker build --platform linux/amd64 -t "$ECR_REPO:$TAG" .

# Push image
echo "Pushing image to ECR..."
docker push "$ECR_REPO:$TAG"

echo ""
echo "=== SUCCESS ==="
echo "Image pushed: $ECR_REPO:$TAG"
echo ""
echo "Now update the deployment:"
echo "  kubectl -n otel-demo set image deployment/payment payment=$ECR_REPO:$TAG"
echo "  kubectl -n otel-demo rollout status deployment/payment"

# Cleanup
cd /
rm -rf "$WORK_DIR"
