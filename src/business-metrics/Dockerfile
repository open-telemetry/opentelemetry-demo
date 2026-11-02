# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM --platform=${BUILDPLATFORM} docker.io/library/gradle:9.8.1-jdk17@sha256:47f780b3062115192d991c37276702c515a1349be5c288fd5ee422b408503fa9 AS builder
WORKDIR /workspace
COPY ./src/business-metrics/build.gradle ./src/business-metrics/settings.gradle ./src/business-metrics/
COPY ./src/business-metrics/src/ ./src/business-metrics/src/
COPY ./pb/ ./pb/
WORKDIR /workspace/src/business-metrics
RUN gradle --no-daemon test installDist

FROM gcr.io/distroless/java17-debian12:nonroot@sha256:06484c2a9dcc9070aeafbc0fe752cb9f73bc0cea5c311f6a516e9010061998ad
WORKDIR /app
COPY --from=builder /workspace/src/business-metrics/build/install/business-metrics/lib/ ./lib/
ENV JAVA_TOOL_OPTIONS="-Xmx128m"
ENTRYPOINT ["java", "-cp", "/app/lib/*", "oteldemo.businessmetrics.BusinessMetricsApplication"]
