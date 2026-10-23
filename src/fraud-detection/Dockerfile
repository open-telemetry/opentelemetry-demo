# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-java:2.31.1@sha256:6f70427eee0ddfaaa861632eadf2d1c9ba03f4daa30e68ae352eac269e9caf7e AS otelagent

# -----------------------------------------------------------------------------

FROM --platform=${BUILDPLATFORM} docker.io/library/gradle:9.8.1-jdk17@sha256:1f5de3a1aae5aeb06d267b9ab5645bfd6fdb6a405a51a2e6af591eb8066de405 AS builder

WORKDIR /usr/src/app/

COPY ./src/fraud-detection/ ./
COPY ./pb/ ./src/main/proto/

RUN gradle shadowJar

# -----------------------------------------------------------------------------

FROM gcr.io/distroless/java17-debian12:nonroot@sha256:06484c2a9dcc9070aeafbc0fe752cb9f73bc0cea5c311f6a516e9010061998ad

WORKDIR /usr/src/app/

# Path and JAVA_TOOL_OPTIONS value match what the OpenTelemetry Operator injects
# for a container named fraud-detection, so a statically built image and an
# operator-injected pod behave identically.
COPY --from=otelagent /javaagent.jar /otel-auto-instrumentation-java-fraud-detection/javaagent.jar
ENV JAVA_TOOL_OPTIONS=" -javaagent:/otel-auto-instrumentation-java-fraud-detection/javaagent.jar"

# Kept out of JAVA_TOOL_OPTIONS, which the Operator sets in the PodSpec. Override
# JDK_JAVA_OPTIONS to tune the heap.
ENV JDK_JAVA_OPTIONS="-Xmx180m"

COPY --from=builder /usr/src/app/build/libs/fraud-detection-1.0-all.jar fraud-detection-1.0-all.jar

ENTRYPOINT [ "java", "-jar", "fraud-detection-1.0-all.jar" ]
