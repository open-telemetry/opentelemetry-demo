# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM --platform=${BUILDPLATFORM} eclipse-temurin:21-jdk AS builder
ARG _JAVA_OPTIONS
WORKDIR /usr/src/app/

COPY ./src/ad/gradlew* ./src/ad/settings.gradle* ./src/ad/build.gradle ./
COPY ./src/ad/gradle ./gradle

RUN chmod +x ./gradlew
RUN ./gradlew
RUN ./gradlew downloadRepos

COPY ./src/ad/ ./
COPY ./pb/ ./proto
RUN chmod +x ./gradlew
RUN ./gradlew installDist -PprotoSourceDir=./proto

# -----------------------------------------------------------------------------

FROM eclipse-temurin:21-jre

ARG OTEL_JAVA_AGENT_VERSION
ARG PYROSCOPE_AGENT_VERSION=2.9.2
ARG _JAVA_OPTIONS

WORKDIR /usr/src/app/

COPY --from=builder /usr/src/app/ ./
ADD --chmod=644 https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v$OTEL_JAVA_AGENT_VERSION/opentelemetry-javaagent.jar /usr/src/app/opentelemetry-javaagent.jar
ADD --chmod=644 https://repo1.maven.org/maven2/io/pyroscope/agent/$PYROSCOPE_AGENT_VERSION/agent-$PYROSCOPE_AGENT_VERSION.jar /usr/src/app/pyroscope-javaagent.jar
# Continuous profiling pushes to the estate Pyroscope when PYROSCOPE_SERVER_ADDRESS is
# set (deploy/telemetry-env-patches.yaml); without it the agent idles harmlessly.
ENV JAVA_TOOL_OPTIONS="-javaagent:/usr/src/app/opentelemetry-javaagent.jar -javaagent:/usr/src/app/pyroscope-javaagent.jar"

EXPOSE ${AD_PORT}
ENTRYPOINT [ "./build/install/opentelemetry-demo-ad/bin/Ad" ]
