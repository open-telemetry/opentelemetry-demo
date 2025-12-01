# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Multi-stage build for Java Spring Boot application (Enterprise N-Tier)
FROM eclipse-temurin:21-jdk AS builder

WORKDIR /app
COPY ./build.gradle build.gradle
COPY ./settings.gradle settings.gradle
COPY ./gradle gradle
COPY ./gradlew gradlew
COPY ./src src

# Build the application
RUN chmod +x ./gradlew
RUN ./gradlew build -x test

# Production image with enterprise monitoring agents
FROM eclipse-temurin:21-jre

# Install enterprise tooling
RUN apt-get update && apt-get install -y curl bash jq net-tools unzip dumb-init && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create application user
RUN groupadd -g 1001 shopdc && \
    useradd -r -u 1001 -g shopdc shopdc

# Create directories for monitoring agents
ENV APPDYNAMICS_AGENT_BASE_DIR=/opt/appdynamics
ENV OPENTELEMETRY_AGENT_DIR=/opt/opentelemetry

RUN mkdir -p $APPDYNAMICS_AGENT_BASE_DIR $OPENTELEMETRY_AGENT_DIR && \
    chown -R shopdc:shopdc $APPDYNAMICS_AGENT_BASE_DIR $OPENTELEMETRY_AGENT_DIR

RUN cd /tmp && \
    echo "Downloading specific AppDynamics Java agent..." && \
    APPD_DOWNLOAD_URL="https://download-files.appdynamics.com/download-file/java-jdk8/25.10.0.37406/AppServerAgent-1.8-25.10.0.37406.zip" && \
    curl -L -f "$APPD_DOWNLOAD_URL" -o JavaAgent.zip && \
    echo "Downloaded file info:" && \
    ls -la JavaAgent.zip && \
    echo "Extracting AppDynamics agent to $APPDYNAMICS_AGENT_BASE_DIR..." && \
    unzip -q JavaAgent.zip -d $APPDYNAMICS_AGENT_BASE_DIR && \
    echo "AppDynamics agent extracted successfully" && \
    ls -la $APPDYNAMICS_AGENT_BASE_DIR/ && \
    chown -R shopdc:shopdc $APPDYNAMICS_AGENT_BASE_DIR && \
    rm -f JavaAgent.zip

# Download the specific Splunk OpenTelemetry Java agent CSA version and replace it within the AppDynamics directory
RUN cd /tmp && \
    SPLUNK_OTEL_CSA_URL="https://repo1.maven.org/maven2/com/splunk/splunk-otel-javaagent-csa/2.21.1/splunk-otel-javaagent-csa-2.21.1.jar" && \
    SPLUNK_OTEL_CSA_FILENAME="splunk-otel-javaagent-csa-2.21.1.jar" && \
    curl -L -f "$SPLUNK_OTEL_CSA_URL" -o "$SPLUNK_OTEL_CSA_FILENAME" && \
    echo "Downloaded Splunk OpenTelemetry CSA agent." && \
    ls -la "$SPLUNK_OTEL_CSA_FILENAME" && \
    \
    # Define the target path and ensure the directory exists
    TARGET_SPLUNK_AGENT_PATH="$APPDYNAMICS_AGENT_BASE_DIR/otel/splunk-otel-javaagent-2.21.0.jar" && \
    TARGET_SPLUNK_AGENT_DIR=$(dirname "$TARGET_SPLUNK_AGENT_PATH") && \
    TARGET_SPLUNK_AGENT_NAME=$(basename "$TARGET_SPLUNK_AGENT_PATH") && \
    \
    echo "Checking if target directory $TARGET_SPLUNK_AGENT_DIR exists..." && \
    mkdir -p "$TARGET_SPLUNK_AGENT_DIR" && \
    \
    echo "Replacing $TARGET_SPLUNK_AGENT_PATH with the new Splunk OpenTelemetry CSA agent..." && \
    mv "$SPLUNK_OTEL_CSA_FILENAME" "$TARGET_SPLUNK_AGENT_DIR/$TARGET_SPLUNK_AGENT_NAME" && \
    chown shopdc:shopdc "$TARGET_SPLUNK_AGENT_DIR/$TARGET_SPLUNK_AGENT_NAME" && \
    echo "Splunk OpenTelemetry CSA agent replaced successfully at $TARGET_SPLUNK_AGENT_DIR/$TARGET_SPLUNK_AGENT_NAME" && \
    rm -f "$SPLUNK_OTEL_CSA_FILENAME"

# Copy application JAR and startup script
COPY --from=builder --chown=shopdc:shopdc /app/build/libs/*.jar app.jar
COPY --chown=shopdc:shopdc ./start-app-dual.sh start-app-dual.sh

RUN chmod +x start-app-dual.sh

# Switch to non-root user
USER shopdc

# Environment variables for enterprise deployment
ENV JAVA_OPTS="-Xms512m -Xmx1024m -XX:+UseG1GC -XX:MaxGCPauseMillis=200 -XX:+HeapDumpOnOutOfMemoryError" \
    OTEL_JAVAAGENT_ENABLED=true \
    APPDYNAMICS_JAVAAGENT_ENABLED=false \
    APPDYNAMICS_CONTROLLER_HOST_NAME=se-lab.saas.appdynamics.com \
    APPDYNAMICS_CONTROLLER_PORT=443 \
    APPDYNAMICS_AGENT_APPLICATION_NAME=shop-dc-shim-service \
    APPDYNAMICS_AGENT_TIER_NAME=shop-dc-shim \
    APPDYNAMICS_AGENT_NODE_NAME=reuse \
    OTEL_SERVICE_NAME=shop-dc-shim \
    OTEL_RESOURCE_ATTRIBUTES="service.name=shop-dc-shim,deployment.environment=datacenter-b01,service.namespace=datacenter,service.version=2.1.3" \
    AGENT_DEPLOYMENT_MODE=dual \
    SPLUNK_PROFILER_ENABLED=true \
    SPLUNK_PROFILER_MEMORY_ENABLED=true \
    SPLUNK_SNAPSHOT_PROFILER_ENABLED=true \
    SPLUNK_SNAPSHOT_SELECTION_PROBABILITY=0.2

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:${SHOP_DC_SHIM_PORT:-8070}/actuator/health || exit 1

EXPOSE 8070

# Use dumb-init for proper signal handling in containers
ENTRYPOINT ["dumb-init", "--"]
CMD ["./start-app-dual.sh"]
