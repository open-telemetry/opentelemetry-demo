FROM --platform=$BUILDPLATFORM mcr.microsoft.com/dotnet/sdk:8.0 AS builder
ARG TARGETARCH

WORKDIR /usr/src/app/

COPY ./src/cart/ ./
COPY ./pb/ ./pb/

#RUN dotnet add ./src/cart.csproj package Splunk.OpenTelemetry.AutoInstrumentation --prerelease
# Map TARGETARCH -> .NET glibc RID
# amd64 -> linux-x64, arm64 -> linux-arm64
RUN set -e; \
    if [ "$TARGETARCH" = "amd64" ]; then RID=linux-x64; \
    elif [ "$TARGETARCH" = "arm64" ]; then RID=linux-arm64; \
    else echo "Unsupported TARGETARCH: $TARGETARCH" && exit 1; fi; \
    echo "Using : $RID " &&\
    dotnet restore ./src/cart.csproj -r $RID && \
    dotnet publish ./src/cart.csproj -r $RID --no-restore -o /cart
# -----------------------------------------------------------------------------
#FROM mcr.microsoft.com/dotnet/runtime-deps:8.0-alpine3.20
FROM mcr.microsoft.com/dotnet/aspnet:8.0

# Install required dependencies for profiling


# Use apt-get on Debian-based aspnet image
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl unzip ca-certificates \
    && rm -rf /var/lib/apt/lists/*


WORKDIR /usr/src/app/
COPY --from=builder /cart/ ./

# Environment variables for Splunk OpenTelemetry
ENV DOTNET_HOSTBUILDER__RELOADCONFIGONCHANGE=false
#ENV OTEL_LOG_LEVEL=debug
#ENV OTEL_DOTNET_AUTO_LOG_DIRECTORY=/tmp/otel-logs
#ENV OTEL_DOTNET_AUTO_TRACES_CONSOLE_EXPORTER_ENABLED=true
#ENV OTEL_DOTNET_AUTO_METRICS_CONSOLE_EXPORTER_ENABLED=true
#ENV OTEL_DOTNET_AUTO_LOGS_CONSOLE_EXPORTER_ENABLED=true

# Additional diagnostic logging
#ENV SPLUNK_OTEL_AUTO_INSTRUMENTATION_LOG_LEVEL=debug
#ENV CORECLR_PROFILER_LOG_PATH=/tmp/profiler.log
#ENV CORECLR_PROFILER_LOG=1

EXPOSE ${CART_PORT}
ENTRYPOINT [ "./splunk-launch.sh", "./cart" ]
#ENTRYPOINT [ "tail","-f","/dev/null" ]