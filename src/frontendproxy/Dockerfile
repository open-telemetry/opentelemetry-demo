# Copyright The OpenTelemetry Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

FROM envoyproxy/envoy-dev:8c202194ac6a2cb781eb6ce27d924b379b1e787f
RUN apt-get update && apt-get install -y gettext-base wget ca-certificates && apt-get clean && rm -rf /var/lib/apt/lists/*

USER envoy
WORKDIR /home/envoy
COPY ./src/frontendproxy/envoy.tmpl.yaml envoy.tmpl.yaml

# Instana tracing
ARG ARTI_PATH='https://artifact-public.instana.io/artifactory/shared/com/instana/libinstana_sensor/'
ARG INSTANA_AGENT_KEY
ARG INSTANA_DOWNLOAD_KEY
RUN access_key=$([ ! -z "${INSTANA_DOWNLOAD_KEY}" ] && echo "${INSTANA_DOWNLOAD_KEY}" || echo "${INSTANA_AGENT_KEY}") \
    && wget --user _ --password ${access_key} --output-document=./list.html ${ARTI_PATH} \
    && sensor_version=$(grep -o "href=\"[0-9]\+\.[0-9]\+\.[0-9]\+/\"" ./list.html | tail -n1 | cut -d'"' -f2) \
    && echo "Using sensor version ${sensor_version}" \
    && wget --user _ --password ${access_key} --output-document=/home/envoy/libcxx-libinstana_sensor.so ${ARTI_PATH}${sensor_version}linux-amd64-libcxx-libinstana_sensor.so

ENTRYPOINT ["/bin/sh", "-c", "envsubst < envoy.tmpl.yaml > envoy.yaml && envoy -c envoy.yaml;"]
