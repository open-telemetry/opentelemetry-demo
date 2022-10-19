#Copyright 2022, OpenTelemetry Authors
#
#Licensed under the Apache License, Version 2.0 (the "License");
#you may not use this file except in compliance with the License.
#You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
#Unless required by applicable law or agreed to in writing, software
#distributed under the License is distributed on an "AS IS" BASIS,
#WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#See the License for the specific language governing permissions and
#limitations under the License.

# build context will only work from ../../docker-compose.yml
FROM rust:1.61-alpine as builder
RUN apk update
RUN apk add --no-cache ca-certificates git protoc cmake clang clang-dev make gcc g++ libc-dev linux-headers
WORKDIR /app/

# build app
COPY ./src/shippingservice/ /app/
COPY ./pb/ /app/proto/
RUN cargo build -r --features="dockerproto"

FROM alpine as release
RUN apk add --no-cache ca-certificates
RUN GRPC_HEALTH_PROBE_VERSION=v0.4.7 && \
    wget -qO/bin/grpc_health_probe https://github.com/grpc-ecosystem/grpc-health-probe/releases/download/${GRPC_HEALTH_PROBE_VERSION}/grpc_health_probe-linux-amd64 && \
    chmod +x /bin/grpc_health_probe
WORKDIR /app
COPY --from=builder /app/target/release/shippingservice /app/shippingservice

EXPOSE ${SHIPPING_SERVICE_PORT}
ENTRYPOINT ["/app/shippingservice"]
