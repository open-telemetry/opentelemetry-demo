# Copyright 2020 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM eclipse-temurin:17-jdk AS builder

WORKDIR /usr/src/app/

COPY ./src/adservice/ ./
COPY ./pb/ ./proto
RUN ./gradlew downloadRepos
RUN ./gradlew installDist -PprotoSourceDir=./proto

# -----------------------------------------------------------------------------

FROM eclipse-temurin:17-jdk

ARG version=1.19.1
WORKDIR /usr/src/app/

COPY --from=builder /usr/src/app/ ./
ADD https://search.maven.org/remotecontent?filepath=io/sentry/sentry-opentelemetry-agent/6.9.1/sentry-opentelemetry-agent-6.9.1.jar /app/opentelemetry-javaagent.jar

ENV JAVA_TOOL_OPTIONS=-javaagent:/app/opentelemetry-javaagent.jar
ENV OTEL_TRACES_EXPORTER=otlp
ENV OTEL_METRICS_EXPORTER=otlp
ENV SENTRY_TRACES_SAMPLE_RATE=1.0
ENV SENTRY_DEBUG=true

#NOTE: The Sentry DSN will be injected into the container at runtime
#ENV SENTRY_DSN=...

EXPOSE ${AD_SERVICE_PORT}
ENTRYPOINT [ "./build/install/hipstershop/bin/AdService" ]
