# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM gradle:7-jdk17 AS builder

WORKDIR /usr/src/app/

COPY ./src/frauddetectionservice/ ./
COPY ./pb/ ./src/main/proto/
RUN gradle shadowJar

# -----------------------------------------------------------------------------

FROM gcr.io/distroless/java17-debian11

ARG version=1.23.0
WORKDIR /usr/src/app/

COPY --from=builder /usr/src/app/build/libs/frauddetectionservice-1.0-all.jar ./
ADD https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v$version/opentelemetry-javaagent.jar /app/opentelemetry-javaagent.jar
# RUN chmod 644 /app/opentelemetry-javaagent.jar
ENV JAVA_TOOL_OPTIONS=-javaagent:/app/opentelemetry-javaagent.jar

ENTRYPOINT [ "java", "-jar", "frauddetectionservice-1.0-all.jar" ]
