# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM --platform=${BUILDPLATFORM} rust:1.76 AS builder
ARG TARGETARCH
ARG TARGETPLATFORM
ARG BUILDPLATFORM

RUN echo Building on ${BUILDPLATFORM} for ${TARGETPLATFORM}

# Check if we are doing cross-compilation, if so we need to add in some more dependencies and run rustup
RUN if [ "${TARGETPLATFORM}" = "${BUILDPLATFORM}" ] ; then \
        apt-get update && apt-get install --no-install-recommends -y g++ libc6-dev libprotobuf-dev protobuf-compiler ca-certificates; \
    elif [ "${TARGETPLATFORM}" = "linux/arm64" ] ; then \
        apt-get update && apt-get install --no-install-recommends -y g++-aarch64-linux-gnu libc6-dev-arm64-cross libprotobuf-dev protobuf-compiler ca-certificates && \
        rustup target add aarch64-unknown-linux-gnu && \
        rustup toolchain install stable-aarch64-unknown-linux-gnu; \
    elif [ "${TARGETPLATFORM}" = "linux/amd64" ] ; then \
        apt-get update && apt-get install --no-install-recommends -y g++-x86-64-linux-gnu libc6-amd64-cross libprotobuf-dev protobuf-compiler ca-certificates && \
        rustup target add x86_64-unknown-linux-gnu && \
        rustup toolchain install stable-x86_64-unknown-linux-gnu; \
    else \
        echo "${TARGETPLATFORM} is not supported"; \
        exit 1; \
    fi

WORKDIR /app/

COPY /src/shipping/ /app/
COPY /pb/ /app/proto/

# Compile or crosscompile
RUN if [ "${TARGETPLATFORM}" = "${BUILDPLATFORM}" ] ; then \
        cargo build -r --features="dockerproto"; \
    elif [ "${TARGETPLATFORM}" = "linux/arm64" ] ; then \
        env CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER=aarch64-linux-gnu-gcc \
            CC_aarch64_unknown_linux_gnu=aarch64-linux-gnu-gcc \
            CXX_aarch64_unknown_linux_gnu=aarch64-linux-gnu-g++ \
        cargo build -r --features="dockerproto" --target aarch64-unknown-linux-gnu && \
        cp /app/target/aarch64-unknown-linux-gnu/release/shipping /app/target/release/shipping; \
    elif [ "${TARGETPLATFORM}" = "linux/amd64" ] ; then \
        env CARGO_TARGET_X86_64_UNKNOWN_LINUX_GNU_LINKER=x86_64-linux-gnu-gcc \
            CC_x86_64_unknown_linux_gnu=x86_64-linux-gnu-gcc \
            CXX_x86_64_unknown_linux_gnu=x86_64-linux-gnu-g++ \
        cargo build -r --features="dockerproto" --target x86_64-unknown-linux-gnu && \
        cp /app/target/x86_64-unknown-linux-gnu/release/shipping /app/target/release/shipping; \
    else \
        echo "${TARGETPLATFORM} is not supported"; \
        exit 1; \
    fi


ENV GRPC_HEALTH_PROBE_VERSION=v0.4.24
RUN wget -qO/bin/grpc_health_probe https://github.com/grpc-ecosystem/grpc-health-probe/releases/download/${GRPC_HEALTH_PROBE_VERSION}/grpc_health_probe-linux-${TARGETARCH} && \
    chmod +x /bin/grpc_health_probe

FROM debian:bookworm-slim AS release

WORKDIR /app
COPY --from=builder /app/target/release/shipping /app/shipping
COPY --from=builder /bin/grpc_health_probe /bin/grpc_health_probe

EXPOSE ${SHIPPING_PORT}
ENTRYPOINT ["/app/shipping"]
