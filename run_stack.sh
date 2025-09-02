#!/bin/bash

docker kill tempo pyroscope grafana 2>/dev/null || true
docker rm tempo pyroscope grafana 2>/dev/null || true

docker run --rm \
        -p 4040:4040 \
        grafana/pyroscope:main-f6178fd \
        -distributor.ring.store=inmemory \
        -ring.store=inmemory \
        -query-scheduler.ring.store=inmemory \
        -store-gateway.sharding-ring.store=inmemory \
        -overrides-exporter.ring.store=inmemory \
        -compactor.ring.store=inmemory &> pyroscope.out &

docker run --rm -d --name tempo --network host \
  -v $(pwd)/src/tempo/tempo.yaml:/etc/tempo.yaml \
  grafana/tempo:2.3.0 \
  -config.file=/etc/tempo.yaml

docker run --rm -d --name grafana --network host \
  -e "GF_SECURITY_ADMIN_USER=admin" \
  -e "GF_SECURITY_ADMIN_PASSWORD=admin" \
  -e "GF_AUTH_ANONYMOUS_ENABLED=true" \
  -e "GF_AUTH_ANONYMOUS_ORG_ROLE=Admin" \
  -e "GF_FEATURE_TOGGLES_ENABLE=traceToProfiles,correlations" \
  grafana/grafana:10.4.0
