# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM eclipse-temurin:21-jdk AS builder

ARG _JAVA_OPTIONS

WORKDIR /usr/src/app/

COPY ./src/ad/gradle/ gradle/

COPY ./src/ad/gradlew gradlew
COPY ./src/ad/gradlew.bat gradlew.bat
COPY ./src/ad/settings.gradle settings.gradle
COPY ./src/ad/build.gradle build.gradle

RUN chmod +x gradlew
RUN ./gradlew
RUN ./gradlew downloadRepos

COPY ./src/ad/ ad/
COPY ./pb/ proto/

RUN ./gradlew installDist -PprotoSourceDir=./proto

# -----------------------------------------------------------------------------

FROM gcr.io/distroless/java21-debian12:nonroot

ARG OTEL_JAVA_AGENT_VERSION
ARG _JAVA_OPTIONS

ENV JAVA_TOOL_OPTIONS=-javaagent:/app/opentelemetry-javaagent.jar

ADD --chmod=644 https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v$OTEL_JAVA_AGENT_VERSION/opentelemetry-javaagent.jar /app/opentelemetry-javaagent.jar

WORKDIR /usr/src/app/

COPY --from=builder /usr/src/app/build/ build/

EXPOSE ${AD_PORT}
ENTRYPOINT [ "./build/install/opentelemetry-demo-ad/bin/Ad" ]
