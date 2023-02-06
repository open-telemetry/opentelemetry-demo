# Copyright 2023 The OpenTelemetry Authors
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

FROM alpine:edge as builder

WORKDIR /currencyservice

RUN apk update
RUN apk add -X http://dl-cdn.alpinelinux.org/alpine/edge/testing git cmake make g++ grpc-dev re2-dev protobuf-dev c-ares-dev opentelemetry-cpp-dev

COPY . .

RUN mkdir -p build && cd build \
    && cmake .. \
    && make -j$(nproc || sysctl -n hw.ncpu || echo 1) install

FROM alpine:edge

WORKDIR /usr/src/app/

RUN apk update && apk add -X http://dl-cdn.alpinelinux.org/alpine/edge/testing grpc re2 protobuf c-ares opentelemetry-cpp opentelemetry-cpp-exporter-otlp-grpc && rm -rf /var/cache/apk/*

COPY --from=builder /usr/local/bin/currencyservice ./

EXPOSE ${CURRENCY_SERVICE_PORT}
ENTRYPOINT ./currencyservice ${CURRENCY_SERVICE_PORT}



