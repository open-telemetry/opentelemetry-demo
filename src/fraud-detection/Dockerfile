# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM --platform=${BUILDPLATFORM} gradle:8-jdk17 AS builder

WORKDIR /usr/src/app/

COPY ./src/fraud-detection/ ./
COPY ./pb/ ./src/main/proto/

RUN gradle shadowJar

# -----------------------------------------------------------------------------

FROM gcr.io/distroless/java17-debian12:nonroot

ARG OTEL_JAVA_AGENT_VERSION
ARG PYROSCOPE_AGENT_VERSION=2.9.2
WORKDIR /usr/src/app/

ADD --chmod=644 https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v$OTEL_JAVA_AGENT_VERSION/opentelemetry-javaagent.jar /usr/src/app/opentelemetry-javaagent.jar
ADD --chmod=644 https://repo1.maven.org/maven2/io/pyroscope/agent/$PYROSCOPE_AGENT_VERSION/agent-$PYROSCOPE_AGENT_VERSION.jar /usr/src/app/pyroscope-javaagent.jar
# Continuous profiling pushes to the estate Pyroscope when PYROSCOPE_SERVER_ADDRESS is
# set (deploy/telemetry-env-patches.yaml); without it the agent idles harmlessly.
# Note: JAVA_TOOL_OPTIONS only applies because the entrypoint is `java` (distroless
# provides no shell expansion for it in _JAVA_OPTIONS form).
ENV JAVA_TOOL_OPTIONS="-javaagent:/usr/src/app/opentelemetry-javaagent.jar -javaagent:/usr/src/app/pyroscope-javaagent.jar"

COPY --from=builder /usr/src/app/build/libs/fraud-detection-1.0-all.jar fraud-detection-1.0-all.jar

ENTRYPOINT [ "java", "-jar", "fraud-detection-1.0-all.jar" ]
