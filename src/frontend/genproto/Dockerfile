# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM node:22-alpine

WORKDIR /app

RUN apk update && \
    apk add --no-cache libc6-compat protobuf-dev protoc

COPY ./pb/ /build/pb/

COPY ./src/frontend/package.json package.json
COPY ./src/frontend/package-lock.json package-lock.json

RUN npm ci
