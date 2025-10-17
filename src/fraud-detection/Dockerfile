# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM --platform=${BUILDPLATFORM} gradle:8-jdk17 AS builder

WORKDIR /usr/src/app/

COPY ./src/fraud-detection/ ./
COPY ./pb/ ./src/main/proto/

RUN gradle shadowJar

# -----------------------------------------------------------------------------

FROM gcr.io/distroless/java17-debian12:nonroot

ARG SPLUNK_OTEL_JAVA_VERSION=2.20.1
WORKDIR /usr/src/app/

ADD --chmod=644 https://github.com/signalfx/splunk-otel-java/releases/download/v${SPLUNK_OTEL_JAVA_VERSION}/splunk-otel-javaagent.jar /usr/src/app/splunk-otel-javaagent.jar
ENV JAVA_TOOL_OPTIONS=-javaagent:/usr/src/app/splunk-otel-javaagent.jar

COPY --from=builder /usr/src/app/build/libs/fraud-detection-1.0-all.jar fraud-detection-1.0-all.jar

ENTRYPOINT [ "java", "-jar", "fraud-detection-1.0-all.jar" ]
