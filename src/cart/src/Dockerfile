# Build stage
FROM --platform=$BUILDPLATFORM mcr.microsoft.com/dotnet/sdk:8.0 AS builder
ARG TARGETARCH

WORKDIR /usr/src/app/

COPY ./src/cart/ ./
COPY ./pb/ ./pb/

RUN dotnet restore ./src/cart.csproj -r linux-musl-$TARGETARCH
RUN dotnet publish ./src/cart.csproj -r linux-musl-$TARGETARCH --no-restore -o /cart

# -----------------------------------------------------------------------------
# Runtime stage with Splunk OpenTelemetry .NET Auto-Instrumentation

FROM mcr.microsoft.com/dotnet/runtime-deps:8.0-alpine3.20
ARG TARGETARCH
ARG SPLUNK_VERSION=1.11.0

WORKDIR /usr/src/app/
COPY --from=builder /cart/ ./

# Map Docker's TARGETARCH to Splunk naming
RUN apk add --no-cache curl unzip \
    && case "$TARGETARCH" in \
         amd64) SPLUNK_ARCH="x64" ;; \
         arm64) SPLUNK_ARCH="arm64" ;; \
         *) echo "Unsupported TARGETARCH: $TARGETARCH" && exit 1 ;; \
       esac \
    && curl -sSL -f -o /tmp/splunk-otel-dotnet.zip \
       "https://github.com/signalfx/splunk-otel-dotnet/releases/download/v${SPLUNK_VERSION}/splunk-opentelemetry-dotnet-linux-musl-${SPLUNK_ARCH}.zip" \
    && unzip /tmp/splunk-otel-dotnet.zip -d /opt/splunk-otel-dotnet \
    && rm /tmp/splunk-otel-dotnet.zip
# Enable profiling and Splunk auto-instrumentation handled in k8s manifest
# ENV DOTNET_HOSTBUILDER__RELOADCONFIGONCHANGE=false \
#     CORECLR_ENABLE_PROFILING=1 \
#     CORECLR_PROFILER="{918728DD-259F-4A6A-AC2B-B85E1B658318}" \
#     CORECLR_PROFILER_PATH="/opt/splunk-otel-dotnet/linux-musl-${TARGETARCH}/OpenTelemetry.AutoInstrumentation.Native.so" \
#     DOTNET_ADDITIONAL_DEPS="/opt/splunk-otel-dotnet/additionalDeps" \
#     DOTNET_SHARED_STORE="/opt/splunk-otel-dotnet/store" \
#     DOTNET_STARTUP_HOOKS="/opt/splunk-otel-dotnet/net/OpenTelemetry.AutoInstrumentation.StartupHook.dll" \
#     OTEL_DOTNET_AUTO_HOME="/opt/splunk-otel-dotnet" \
#     SPLUNK_PROFILER_ENABLED=true \
#     SPLUNK_METRICS_ENABLED=true

EXPOSE ${CART_PORT}
ENTRYPOINT ["./cart"]