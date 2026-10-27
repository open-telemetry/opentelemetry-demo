# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM --platform=${BUILDPLATFORM} docker.io/library/rust:1.99.1@sha256:931c2c0531a8b143e044f0f3914dfe802f15bb3d1955f0b657e9359327ac2ffc AS builder
ARG TARGETARCH
ARG TARGETPLATFORM
ARG BUILDPLATFORM

RUN echo Building on ${BUILDPLATFORM} for ${TARGETPLATFORM}

# Install dependencies - cross-compilation setup for ARM64, native otherwise
RUN apt-get update && \
    if [ "${TARGETPLATFORM}" = "linux/arm64" ] && [ "${BUILDPLATFORM}" != "linux/arm64" ] ; then \
        apt-get install --no-install-recommends -y g++-aarch64-linux-gnu libc6-dev-arm64-cross libprotobuf-dev protobuf-compiler ca-certificates && \
        rustup target add aarch64-unknown-linux-gnu; \
    else \
        apt-get install --no-install-recommends -y g++ libc6-dev libprotobuf-dev protobuf-compiler ca-certificates; \
    fi

WORKDIR /app/

COPY /src/shipping/ /app/

# Build - cross-compile for ARM64 or native build
RUN if [ "${TARGETPLATFORM}" = "linux/arm64" ] && [ "${BUILDPLATFORM}" != "linux/arm64" ] ; then \
        env CARGO_TARGET_AARCH64_UNKNOWN_LINUX_GNU_LINKER=aarch64-linux-gnu-gcc \
            CC_aarch64_unknown_linux_gnu=aarch64-linux-gnu-gcc \
            CXX_aarch64_unknown_linux_gnu=aarch64-linux-gnu-g++ \
        cargo build -r --target aarch64-unknown-linux-gnu && \
        cp /app/target/aarch64-unknown-linux-gnu/release/shipping /app/target/release/shipping && \
        cp /app/target/aarch64-unknown-linux-gnu/release/healthcheck /app/target/release/healthcheck; \
    else \
        cargo build -r; \
    fi


FROM gcr.io/distroless/cc-debian13:nonroot@sha256:3ee00291cf386ec52a552e6a858d555debd74776eb4bfa53fa3df2cd6677515e

WORKDIR /app

COPY --from=builder /app/target/release/shipping shipping
COPY --from=builder /app/target/release/healthcheck healthcheck

ARG SHIPPING_PORT=50050
EXPOSE ${SHIPPING_PORT}

CMD ["./shipping"]
