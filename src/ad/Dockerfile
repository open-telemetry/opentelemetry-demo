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

# Grab the latest Splunk OpenTelemetry Java agent (because “latest” is apparently a lifestyle)
ADD --chmod=644 https://github.com/signalfx/splunk-otel-java/releases/latest/download/splunk-otel-javaagent.jar /usr/src/app/splunk-otel-javaagent.jar

WORKDIR /usr/src/app/
COPY --from=builder /usr/src/app/ ./

# Auto-instrumentation: Splunk agent handled in the k8s manifest 
#ENV JAVA_TOOL_OPTIONS="-javaagent:/usr/src/app/splunk-otel-javaagent.jar"

EXPOSE ${AD_PORT}
ENTRYPOINT [ "./build/install/opentelemetry-demo-ad/bin/Ad" ]
