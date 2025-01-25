# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM node:20-alpine

WORKDIR /app

RUN apk add --no-cache libc6-compat protobuf-dev protoc

COPY ./src/frontend/package*.json ./

RUN npm ci

COPY ./pb /build/pb
