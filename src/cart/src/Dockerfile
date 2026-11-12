# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0
# Copyright 2021 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# https://mcr.microsoft.com/v2/dotnet/sdk/tags/list
FROM --platform=$BUILDPLATFORM mcr.microsoft.com/dotnet/sdk:11.0.100@sha256:65f3c7c6a25a239ab3e6719f2896147e7b68242ff2d8818dd70498bde6ef8bea AS base
ARG TARGETARCH

WORKDIR /usr/src/app/

COPY ./src/cart/ ./
COPY ./pb/ ./pb/

RUN dotnet restore ./tests/cart.tests.csproj -r linux-musl-$TARGETARCH

FROM base AS test

RUN dotnet test ./tests/cart.tests.csproj --no-restore --configuration Release \
  && touch /tmp/cart-tests-passed

FROM base AS builder

# BuildKit skips unused stages, so depend on the test marker to require tests before building the release.
COPY --from=test /tmp/cart-tests-passed /tmp/cart-tests-passed

RUN dotnet publish ./src/cart.csproj -r linux-musl-$TARGETARCH --no-restore -o /cart

# -----------------------------------------------------------------------------

# https://mcr.microsoft.com/v2/dotnet/runtime-deps/tags/list
FROM ghcr.io/grpc-ecosystem/grpc-health-probe:v0.4.61@sha256:9df7b8dfbaf01d20eaedcd6de084c557074046f87cfc0413b7939ae18087c249 AS grpc-health-probe

FROM mcr.microsoft.com/dotnet/runtime-deps:11.0.0-alpine3.24@sha256:5597d4a0c9ea3fb84fc210333013d761fc350d5925fc9042f62992675e15b58b

WORKDIR /usr/src/app/
COPY --from=builder /cart/ ./
COPY --from=grpc-health-probe /ko-app/grpc-health-probe /bin/grpc_health_probe

ENV DOTNET_HOSTBUILDER__RELOADCONFIGONCHANGE=false

ARG CART_PORT=7070
EXPOSE ${CART_PORT}
ENTRYPOINT [ "./cart" ]
