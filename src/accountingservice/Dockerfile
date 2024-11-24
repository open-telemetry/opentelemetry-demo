# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

FROM --platform=${BUILDPLATFORM} mcr.microsoft.com/dotnet/sdk:8.0 AS builder
ARG TARGETARCH

WORKDIR /usr/src/app/

COPY ./src/accountingservice/ ./
COPY ./pb/ ./proto/

RUN dotnet restore "./AccountingService.csproj" -r linux-musl-$TARGETARCH

RUN dotnet publish "./AccountingService.csproj" -r linux-musl-$TARGETARCH --no-restore -o /accountingservice

# -----------------------------------------------------------------------------

FROM mcr.microsoft.com/dotnet/aspnet:8.0

WORKDIR /usr/src/app/
COPY --from=builder /accountingservice/ ./

ENV DOTNET_HOSTBUILDER__RELOADCONFIGONCHANGE=false

ENTRYPOINT ["./instrument.sh", "dotnet", "AccountingService.dll"]
