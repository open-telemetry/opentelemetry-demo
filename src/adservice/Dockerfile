# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0


FROM eclipse-temurin:21-jdk as builder

WORKDIR /usr/src/app/

COPY ./src/adservice/gradlew* ./src/adservice/settings.gradle* ./src/adservice/build.gradle ./
COPY ./src/adservice/gradle ./gradle

RUN ./gradlew
RUN ./gradlew downloadRepos

COPY ./src/adservice/ ./
COPY ./pb/ ./proto
RUN ./gradlew installDist -PprotoSourceDir=./proto

# -----------------------------------------------------------------------------

FROM eclipse-temurin:21-jre

ARG version=2.6.0
WORKDIR /usr/src/app/

COPY --from=builder /usr/src/app/ ./

EXPOSE ${AD_SERVICE_PORT}
ENTRYPOINT [ "./build/install/opentelemetry-demo-ad-service/bin/AdService" ]
