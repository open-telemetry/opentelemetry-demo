# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM --platform=${BUILDPLATFORM} gradle:8-jdk17 AS builder
ARG TARGETARCH

WORKDIR /usr/src/app/

COPY ./src/fraud-detection/ ./
COPY ./pb/ ./src/main/proto/

# Download architecture-specific FusionReactor native library based on target architecture
RUN if [ "$TARGETARCH" = "amd64" ]; then \
        curl -L https://download.fusionreactor.io/FR/Latest/libfrjvmti_x64.so -o /usr/src/app/libfrjvmti.so; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
        curl -L https://download.fusionreactor.io/FR/Latest/libfrjvmti_aarch64.so -o /usr/src/app/libfrjvmti.so; \
    else \
        echo "Unsupported architecture: $TARGETARCH" && exit 1; \
    fi

RUN gradle shadowJar

# -----------------------------------------------------------------------------

FROM gcr.io/distroless/java17-debian12:nonroot

ARG OTEL_JAVA_AGENT_VERSION
WORKDIR /usr/src/app/

#ADD --chmod=644 https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v$OTEL_JAVA_AGENT_VERSION/opentelemetry-javaagent.jar /usr/src/app/opentelemetry-javaagent.jar
#ENV JAVA_TOOL_OPTIONS=-javaagent:/usr/src/app/opentelemetry-javaagent.jar

# Download FusionReactor jar (architecture-independent)
ADD --chmod=644 https://download.fusionreactor.io/FR/Latest/fusionreactor.jar /usr/src/app/fusionreactor.jar

# Copy FusionReactor native library from builder stage
COPY --from=builder /usr/src/app/libfrjvmti.so /usr/src/app/libfrjvmti.so

# Set FusionReactor Java options
ENV JAVA_TOOL_OPTIONS="-javaagent:/usr/src/app/fusionreactor.jar=name=otlp-fraud-detection-fr,address=8089 -agentpath:/usr/src/app/libfrjvmti.so"

COPY --from=builder /usr/src/app/build/libs/fraud-detection-1.0-all.jar fraud-detection-1.0-all.jar

ENTRYPOINT [ "java", "-jar", "fraud-detection-1.0-all.jar" ]
