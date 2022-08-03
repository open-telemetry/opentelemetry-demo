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

FROM openjdk:18-slim AS builder

WORKDIR /usr/src/app/

COPY ./src/adservice/ ./
COPY ./pb/ ./src/main/proto/
RUN chmod +x ./gradlew
RUN ./gradlew downloadRepos
RUN ./gradlew installDist

# -----------------------------------------------------------------------------

FROM openjdk:18-slim

ARG version=1.16.0
WORKDIR /usr/src/app/

COPY --from=builder /usr/src/app/ ./
ADD https://github.com/open-telemetry/opentelemetry-java-instrumentation/releases/download/v$version/opentelemetry-javaagent.jar /app/opentelemetry-javaagent.jar
ENV JAVA_TOOL_OPTIONS=-javaagent:/app/opentelemetry-javaagent.jar

EXPOSE ${AD_SERVICE_PORT}
ENTRYPOINT [ "./build/install/hipstershop/bin/AdService" ]
