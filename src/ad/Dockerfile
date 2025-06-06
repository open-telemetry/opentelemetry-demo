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
ARG _JAVA_OPTIONS

WORKDIR /usr/src/app/

COPY --from=builder /usr/src/app/ ./
#ADD --chmod=644 https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v$OTEL_JAVA_AGENT_VERSION/opentelemetry-javaagent.jar /usr/src/app/opentelemetry-javaagent.jar
#ENV JAVA_TOOL_OPTIONS=-javaagent:/usr/src/app/opentelemetry-javaagent.jar

# Download FusionReactor files
ADD --chmod=644 https://download.fusionreactor.io/FR/Latest/fusionreactor.jar /usr/src/app/fusionreactor.jar
ADD --chmod=644 https://download.fusionreactor.io/FR/Latest/libfrjvmti_aarch64.so /usr/src/app/libfrjvmti_aarch64.so

# Set FusionReactor Java options
ENV JAVA_TOOL_OPTIONS="-javaagent:/usr/src/app/fusionreactor.jar=name=otlp-ad-fr,address=8088 -agentpath:/usr/src/app/libfrjvmti_aarch64.so"

EXPOSE ${AD_PORT}
ENTRYPOINT [ "./build/install/opentelemetry-demo-ad/bin/Ad" ]
