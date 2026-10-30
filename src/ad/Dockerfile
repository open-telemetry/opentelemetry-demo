# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM ghcr.io/open-telemetry/opentelemetry-operator/autoinstrumentation-java:2.31.1@sha256:6f70427eee0ddfaaa861632eadf2d1c9ba03f4daa30e68ae352eac269e9caf7e AS otelagent

# -----------------------------------------------------------------------------

FROM --platform=${BUILDPLATFORM} docker.io/library/eclipse-temurin:24.0.2_12-jdk@sha256:7493205ffe6caa8074fa8a06a276bb1c5ac41d3dd0fd43a0db66d7f776e80b3e AS builder
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

FROM docker.io/library/eclipse-temurin:24.0.2_12-jre@sha256:8cb2387a28af84cf0db0948d9c67d4480192f4e567027a3963f145d218e8b4f2

WORKDIR /usr/src/app/

COPY --from=builder /usr/src/app/ ./

# Path and JAVA_TOOL_OPTIONS value match what the OpenTelemetry Operator
# injects into a container named "ad", so a statically built image and an
# operator-injected pod behave identically. Changing either breaks that
# equivalence.
COPY --from=otelagent /javaagent.jar /otel-auto-instrumentation-java-ad/javaagent.jar
ENV JAVA_TOOL_OPTIONS=" -javaagent:/otel-auto-instrumentation-java-ad/javaagent.jar"

# The Operator overwrites JAVA_TOOL_OPTIONS, so the heap cap lives here instead.
ENV JDK_JAVA_OPTIONS="-Xmx200m"

ARG AD_PORT=9555
ARG AD_PROMETHEUS_PORT=9465
EXPOSE ${AD_PORT}
EXPOSE ${AD_PROMETHEUS_PORT}
ENTRYPOINT [ "./build/install/opentelemetry-demo-ad/bin/Ad" ]
