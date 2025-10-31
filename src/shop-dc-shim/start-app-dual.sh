#!/bin/bash
# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Shop Datacenter Shim Service Startup Script
# Dual instrumentation (AppDynamics + Splunk Observability)

set -e

echo "Starting Shop Datacenter Shim Service with dual instrumentation..."

# AppDynamics Configuration (with fallback defaults)
# We should pull APPDYNAMICS_AGENT_ACCOUNT_ACCESS_KEY from swipe
export APPDYNAMICS_AGENT_ACCOUNT_ACCESS_KEY=${APPDYNAMICS_AGENT_ACCOUNT_ACCESS_KEY:-replace-appd-token}
export APPDYNAMICS_AGENT_ACCOUNT_NAME=${APPDYNAMICS_AGENT_ACCOUNT_NAME:-se-lab}
export APPDYNAMICS_CONTROLLER_HOST_NAME=${APPDYNAMICS_CONTROLLER_HOST_NAME:-se-lab.saas.appdynamics.com}
export APPDYNAMICS_JAVA_AGENT_REUSE_NODE_NAME_PREFIX="shop-dc-shim-node"
export APPDYNAMICS_AGENT_APPLICATION_NAME=shop-dc-shim-service
export APPDYNAMICS_AGENT_TIER_NAME=shop-dc-shim
export APPDYNAMICS_CONTROLLER_PORT=443
export APPDYNAMICS_CONTROLLER_SSL_ENABLED=true
export APPDYNAMICS_AGENT_NODE_NAME="reuse"
export APPDYNAMICS_JAVA_AGENT_REUSE_NODE_NAME="true"

# OpenTelemetry Configuration
export OTEL_EXPORTER_OTLP_ENDPOINT=http://splunk-otel-collector-agent:4318
export OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
export OTEL_SERVICE_NAME=shop-dc-shim-service
export OTEL_RESOURCE_ATTRIBUTES=service.name=shop-dc-shim-service,deployment.environment=datacenter-b01,service.version=2.1.3,service.namespace=shop-dc-shim
export OTEL_INSTRUMENTATION_SPLUNK_JDBC_ENABLED=true

# Dual instrumentation mode
export AGENT_DEPLOYMENT_MODE=dual

echo "Configuration:"
echo "  Service: shop-dc-shim-service"
echo "  Environment: datacenter-b01"
echo "  AppDynamics Application: ${APPDYNAMICS_AGENT_APPLICATION_NAME}"
echo "  AppDynamics Controller: ${APPDYNAMICS_CONTROLLER_HOST_NAME}"
echo "  OpenTelemetry Endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT}"

# Start the application
java -javaagent:/opt/appdynamics/javaagent.jar \
     -Dagent.deployment.mode=dual \
     -Dotel.instrumentation.jdbc.enabled=true \
     -Dsplunk.profiler.enabled=true \
     -Dsplunk.profiler.memory.enabled=true \
     -Dsplunk.snapshot.profiler.enabled=true \
     -Dsplunk.snapshot.selection.probability=0.2 \
     -Dotel.exporter.otlp.endpoint=http://splunk-otel-collector-agent:4318 \
     -Dappdynamics.sim.enabled=true \
     -jar /app/*.jar