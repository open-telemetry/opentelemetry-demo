# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

# Stage 1: Build environment
FROM mcr.microsoft.com/dotnet/sdk:8.0 AS build
ARG BUILD_CONFIGURATION=Release
WORKDIR /src

# Copy source code and dependencies
COPY ["/src/accountingservice/", "AccountingService/"]
COPY ["/pb/demo.proto", "AccountingService/proto/"]

# Restore dependencies
RUN dotnet restore "./AccountingService/AccountingService.csproj"

# Build application
WORKDIR "/src/AccountingService"
RUN dotnet build "./AccountingService.csproj" -c $BUILD_CONFIGURATION -o /app/build

# Stage 2: Publish environment
FROM build AS publish
ARG BUILD_CONFIGURATION=Release
RUN dotnet publish "./AccountingService.csproj" --use-current-runtime -c $BUILD_CONFIGURATION -o /app/publish /p:UseAppHost=false

# Stage 3: Final environment
FROM mcr.microsoft.com/dotnet/aspnet:8.0 AS final
WORKDIR /app

# Copy published application from build stage
COPY --from=publish /app/publish .

# Create necessary directories and set permissions
USER root
RUN mkdir -p "/var/log/opentelemetry/dotnet"
RUN chown app "/var/log/opentelemetry/dotnet"
USER app

# Define entrypoint command
ENTRYPOINT ["./instrument.sh", "dotnet", "AccountingService.dll"]
