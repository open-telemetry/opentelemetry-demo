# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM --platform=${BUILDPLATFORM} docker.io/library/gradle:9.9.2-jdk17@sha256:d66c9f700fc22daad6c5f1f03e34c5e46e7ae95f575e8ae26e08a6939963ae04 AS base

WORKDIR /usr/src/app/

COPY ./src/fraud-detection/ ./
COPY ./pb/ ./src/main/proto/

FROM base AS test

RUN gradle test --no-daemon \
  && touch /tmp/fraud-detection-tests-passed

FROM base AS builder

# BuildKit skips unused stages, so depend on the test marker to require tests before building the release.
COPY --from=test /tmp/fraud-detection-tests-passed /tmp/fraud-detection-tests-passed

RUN gradle shadowJar

# -----------------------------------------------------------------------------

FROM gcr.io/distroless/java17-debian12:nonroot@sha256:06484c2a9dcc9070aeafbc0fe752cb9f73bc0cea5c311f6a516e9010061998ad

ARG OTEL_JAVA_AGENT_VERSION
WORKDIR /usr/src/app/

ADD --chmod=644 https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v$OTEL_JAVA_AGENT_VERSION/opentelemetry-javaagent.jar /usr/src/app/opentelemetry-javaagent.jar
ENV JAVA_TOOL_OPTIONS="-javaagent:/usr/src/app/opentelemetry-javaagent.jar -Xmx180m"
ENV OTEL_INSTRUMENTATION_LOG4J_APPENDER_EXPERIMENTAL_MDC_ATTRIBUTES_INCLUDED="messaging.destination.name,messaging.consumer.group.name"

COPY --from=builder /usr/src/app/build/libs/fraud-detection-1.0-all.jar fraud-detection-1.0-all.jar

ENTRYPOINT [ "java", "-jar", "fraud-detection-1.0-all.jar" ]
