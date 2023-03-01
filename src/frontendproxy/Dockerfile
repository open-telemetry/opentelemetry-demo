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

# Custom lua script
COPY ./src/frontendproxy/instana-eum.lua /home/envoy/

ENTRYPOINT ["/bin/sh", "-c", "envsubst < envoy.tmpl.yaml > envoy.yaml && envoy -c envoy.yaml;"]
