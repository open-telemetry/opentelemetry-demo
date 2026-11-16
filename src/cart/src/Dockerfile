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
FROM --platform=$BUILDPLATFORM mcr.microsoft.com/dotnet/sdk:10.0 AS builder
ARG TARGETARCH

WORKDIR /usr/src/app/

COPY ./src/cart/ ./
COPY ./pb/ ./pb/

RUN dotnet restore ./src/cart.csproj -r linux-musl-$TARGETARCH

RUN dotnet publish ./src/cart.csproj -r linux-musl-$TARGETARCH --no-restore -o /cart

# -----------------------------------------------------------------------------

# https://mcr.microsoft.com/v2/dotnet/runtime-deps/tags/list
FROM mcr.microsoft.com/dotnet/runtime-deps:10.0-alpine3.22

ARG PYROSCOPE_DOTNET_VERSION=1.5.1

WORKDIR /usr/src/app/
COPY --from=builder /cart/ ./

# Pyroscope continuous profiling: native CLR profiler (env-configured; the managed
# Pyroscope NuGet package is optional and only needed for dynamic tags, which we don't
# use). Pushes to the estate Pyroscope when PYROSCOPE_SERVER_ADDRESS is set
# (deploy/telemetry-env-patches.yaml); PYROSCOPE_PROFILING_ENABLED=0 keeps local runs off.
ADD https://github.com/grafana/pyroscope-dotnet/releases/download/pyroscope-$PYROSCOPE_DOTNET_VERSION/pyroscope.$PYROSCOPE_DOTNET_VERSION-musl-x86_64.tar.gz /tmp/pyroscope-profiler.tar.gz
RUN mkdir -p /usr/share/pyroscope \
    && tar xzf /tmp/pyroscope-profiler.tar.gz -C /usr/share/pyroscope \
    && rm /tmp/pyroscope-profiler.tar.gz

ENV PYROSCOPE_PROFILING_ENABLED=0 \
    CORECLR_ENABLE_PROFILING=1 \
    CORECLR_PROFILER={BD1A650D-AC5D-4896-B64F-D6FA25D6B26A} \
    CORECLR_PROFILER_PATH=/usr/share/pyroscope/Pyroscope.Profiler.Native.so \
    LD_PRELOAD=/usr/share/pyroscope/Pyroscope.Linux.ApiWrapper.x64.so \
    LD_LIBRARY_PATH=/usr/share/pyroscope

ENV DOTNET_HOSTBUILDER__RELOADCONFIGONCHANGE=false

EXPOSE ${CART_PORT}
ENTRYPOINT [ "./cart" ]
