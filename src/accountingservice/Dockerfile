# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM --platform=${TARGETPLATFORM} mcr.microsoft.com/dotnet/aspnet:8.0 AS base
USER app
WORKDIR /app

FROM --platform=${BUILDPLATFORM} mcr.microsoft.com/dotnet/sdk:8.0 AS build
ARG TARGETARCH
ARG BUILD_CONFIGURATION=Release
WORKDIR /src
COPY ["/src/accountingservice/", "AccountingService/"]
COPY ["/pb/demo.proto", "AccountingService/proto/"]
RUN dotnet restore "./AccountingService/AccountingService.csproj" -r linux-musl-$TARGETARCH
WORKDIR "/src/AccountingService"

RUN dotnet build "./AccountingService.csproj" -r linux-musl-$TARGETARCH -c $BUILD_CONFIGURATION -o /app/build

FROM build AS publish
ARG BUILD_CONFIGURATION=Release
RUN dotnet publish "./AccountingService.csproj" -r linux-musl-$TARGETARCH -c $BUILD_CONFIGURATION -o /app/publish /p:UseAppHost=false

FROM base AS final
WORKDIR /app
COPY --from=publish /app/publish .

USER root
RUN mkdir -p "/var/log/opentelemetry/dotnet"
RUN chown app "/var/log/opentelemetry/dotnet"
USER app

ENTRYPOINT ["./instrument.sh", "dotnet", "AccountingService.dll"]
