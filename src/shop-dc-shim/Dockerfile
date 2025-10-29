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

# Download OpenTelemetry Java agent for Splunk Observability andlatest AppDynamics Java agent
ADD --chown=shopdc:shopdc https://github.com/signalfx/splunk-otel-java/releases/latest/download/splunk-otel-javaagent.jar $OPENTELEMETRY_AGENT_DIR/opentelemetry-javaagent.jar

RUN cd /tmp && \
    echo "Fetching latest AppDynamics Java agent..." && \
    DOWNLOAD_BASE_PATH="https://download-files.appdynamics.com/" && \
    echo "Getting latest version info from AppDynamics API..." && \
    FILE_PATH=$(curl -s https://download.appdynamics.com/download/downloadfilelatest/ | jq -r '.[].s3_path' | grep java-jdk8 | head -n1) && \
    DOWNLOAD_URL="${DOWNLOAD_BASE_PATH}${FILE_PATH}" && \
    echo "Downloading AppDynamics agent from: $DOWNLOAD_URL" && \
    curl -L -f "$DOWNLOAD_URL" -o JavaAgent.zip && \
    echo "Downloaded file info:" && \
    ls -la JavaAgent.zip && \
    echo "Extracting AppDynamics agent to $APPDYNAMICS_AGENT_BASE_DIR..." && \
    unzip -q JavaAgent.zip -d $APPDYNAMICS_AGENT_BASE_DIR && \
    echo "AppDynamics agent extracted successfully" && \
    ls -la $APPDYNAMICS_AGENT_BASE_DIR/ && \
    chown -R shopdc:shopdc $APPDYNAMICS_AGENT_BASE_DIR && \
    rm -f JavaAgent.zip

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
