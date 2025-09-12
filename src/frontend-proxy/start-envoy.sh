#!/bin/sh

# Configure IPv4 or IPv6 address based on environment variable
if [ "$IPV6_ENABLED" = "true" ] || [ "$IPV6_ENABLED" = "1" ]; then
    export ENVOY_ADDRESS="::"
    echo "DEBUG: IPv6 ENABLED - binding to [::]:${ENVOY_PORT}"
else
    export ENVOY_ADDRESS="0.0.0.0"
    echo "DEBUG: IPv6 DISABLED - binding to 0.0.0.0:${ENVOY_PORT}"
fi

echo "DEBUG: IPV6_ENABLED = ${IPV6_ENABLED:-not set}"

# Process template and start Envoy
envsubst < envoy.tmpl.yaml > envoy.yaml && envoy -c envoy.yaml
