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
FROM --platform=$BUILDPLATFORM mcr.microsoft.com/dotnet/sdk:10.0.401@sha256:35d40304542c8689331f8cab17c65926cdf48fe711e289321d71924b230a7d29 AS base
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
FROM ghcr.io/grpc-ecosystem/grpc-health-probe:v0.4.57@sha256:f77f1257805ecb57f1f0c36c5825d3c2e47aa81cce87128675e768463ed6487a AS grpc-health-probe

FROM mcr.microsoft.com/dotnet/runtime-deps:10.0.12-alpine3.23@sha256:ec7978b6668931a141e5a6d5b831aea858e4f8fa908ca75900299e40fb17529e

WORKDIR /usr/src/app/
COPY --from=builder /cart/ ./
COPY --from=grpc-health-probe /ko-app/grpc-health-probe /bin/grpc_health_probe

ENV DOTNET_HOSTBUILDER__RELOADCONFIGONCHANGE=false

ARG CART_PORT=7070
EXPOSE ${CART_PORT}
ENTRYPOINT [ "./cart" ]
