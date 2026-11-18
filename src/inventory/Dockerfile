# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM --platform=${BUILDPLATFORM} docker.io/library/alpine:3.24.1@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b AS builder

ARG TARGETARCH
ARG ZIG_VERSION=0.16.0

RUN apk add --no-cache curl tar xz

RUN set -eux; \
    case "$(uname -m)" in \
      x86_64) \
        ZIG_HOST=x86_64-linux; \
        ZIG_SHA=70e49664a74374b48b51e6f3fdfbf437f6395d42509050588bd49abe52ba3d00 ;; \
      aarch64) \
        ZIG_HOST=aarch64-linux; \
        ZIG_SHA=ea4b09bfb22ec6f6c6ceac57ab63efb6b46e17ab08d21f69f3a48b38e1534f17 ;; \
      *) echo "unsupported build architecture: $(uname -m)" >&2; exit 1 ;; \
    esac; \
    curl -fsSL -o /tmp/zig.tar.xz \
      "https://ziglang.org/download/${ZIG_VERSION}/zig-${ZIG_HOST}-${ZIG_VERSION}.tar.xz"; \
    echo "${ZIG_SHA}  /tmp/zig.tar.xz" | sha256sum -c -; \
    mkdir -p /opt/zig; \
    tar -xJf /tmp/zig.tar.xz -C /opt/zig --strip-components=1; \
    rm /tmp/zig.tar.xz

ENV PATH="/opt/zig:${PATH}"

WORKDIR /app

COPY ./src/inventory/ /app/

RUN set -eux; \
    case "${TARGETARCH}" in \
      amd64) ZIG_TARGET=x86_64-linux-musl ;; \
      arm64) ZIG_TARGET=aarch64-linux-musl ;; \
      *) echo "unsupported target architecture: ${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    zig build -Dtarget="${ZIG_TARGET}" -Doptimize=ReleaseSafe --prefix /out


FROM docker.io/library/alpine:3.24.1@sha256:28bd5fe8b56d1bd048e5babf5b10710ebe0bae67db86916198a6eec434943f8b

COPY --from=builder /out/bin/inventory /usr/local/bin/inventory

EXPOSE ${INVENTORY_PORT}

ENTRYPOINT ["/usr/local/bin/inventory"]
