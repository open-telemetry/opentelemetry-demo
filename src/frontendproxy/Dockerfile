FROM envoyproxy/envoy-dev:8c202194ac6a2cb781eb6ce27d924b379b1e787f
RUN apt-get update && apt-get install -y gettext-base && apt-get clean && rm -rf /var/lib/apt/lists/*

COPY ./src/frontendproxy/envoy.tmpl.yaml /etc/envoy/envoy.tmpl.yaml

ENTRYPOINT ["/bin/sh", "-c", "envsubst < /etc/envoy/envoy.tmpl.yaml > /etc/envoy/envoy.yaml && envoy -c /etc/envoy/envoy.yaml;"]
