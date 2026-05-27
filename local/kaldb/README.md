# OpenTelemetry Demo With KalDB

This local setup runs the OpenTelemetry Demo while sending telemetry to a local
KalDB checkout.

All KalDB-specific OpenTelemetry Demo files live in `local/kaldb/`. The root
`Makefile` only exposes convenience targets.

## Start

```bash
make start-kaldb
```

By default the target expects KalDB at:

```text
/Users/suman/code/kaldb-kaldb
```

Override it when needed:

```bash
make start-kaldb KALDB_HOME=/path/to/kaldb
```

Use a clean KalDB rebuild:

```bash
make start-kaldb KALDB_CLEAN=true
```

## What It Provisions

The helper provisions two KalDB datasets:

```text
otel-demo-logs    serviceNamePattern: otel-demo-logs
otel-demo-traces  serviceNamePattern: otel-demo-traces
```

It also ensures local KalDB partitions `0` and `1` exist, then assigns one
partition to each dataset:

```text
otel-demo-logs    -> partition 0
otel-demo-traces  -> partition 1
```

Override them with `KALDB_LOG_PARTITION_IDS` and `KALDB_TRACE_PARTITION_IDS`.
The helper starts KalDB Manager with
`ASTRA_MANAGER_API_MIN_NUMBER_OF_PARTITIONS=1` for this demo so single-partition
dataset assignments are accepted.

The demo also runs one indexer per partition and raises indexer rollover
thresholds so chunks should not roll over during a normal demo:

```text
INDEXER_MAX_BYTES_PER_CHUNK=10000000000
INDEXER_MAX_TIME_PER_CHUNK_SECONDS=3600
INDEXER_MAX_MESSAGES_PER_CHUNK=10000000
```

Override them with `KALDB_INDEXER_MAX_BYTES_PER_CHUNK`,
`KALDB_INDEXER_MAX_TIME_PER_CHUNK_SECONDS`, and
`KALDB_INDEXER_MAX_MESSAGES_PER_CHUNK`.

The OTel Collector exports:

```text
logs   -> KalDB _bulk ingest, index otel-demo-logs
traces -> KalDB OTLP/HTTP /v1/traces, dataset otel-demo-traces
```

KalDB's S3Mock dependency keeps container port `9090` but binds host port
`19090` by default, so an existing Prometheus on host `9090` can keep running.
The KalDB compose layer also caps the OTel load generator to one Locust user
and disables browser traffic so the local KalDB/ZooKeeper stack stays stable.

## URLs

```text
OpenTelemetry Demo: http://localhost:18080
KalDB Grafana:      http://localhost:3000/d/kaldb-otel-demo/kaldb-otel-demo
KalDB Dashboards:   http://localhost:5601/app/discover
KalDB Query API:    http://localhost:8081
KalDB Ingest API:   http://localhost:8086
```

Grafana provisions three KalDB demo datasources:

```text
otel-demo-logs              OpenSearch datasource, dataset otel-demo-logs
otel-demo-traces            OpenSearch datasource, dataset otel-demo-traces
otel-demo-traces-waterfall  Zipkin datasource, trace-by-ID waterfall rendering
```

The `KalDB OTel Demo` dashboard shows recent logs and trace spans with Grafana
logs panels backed by KalDB-compatible `_msearch` requests. Use
`otel-demo-logs` in Explore for log search, and `otel-demo-traces` to find
recent `trace_id` values. Use `otel-demo-traces-waterfall` in Explore with a
trace ID to render the
Zipkin/Jaeger-style waterfall. KalDB's current Zipkin compatibility exposes
trace-by-ID rendering; service/span discovery and trace search return empty
lists, so the trace workflow starts from a known trace ID.

## Verify

```bash
make verify-kaldb
```

Generate traffic in the shop, then open the `KalDB OTel Demo` dashboard. Use
`otel-demo-logs` for log search, `otel-demo-traces` to find trace IDs, and
`otel-demo-traces-waterfall` for trace-by-ID waterfall rendering in Grafana
Explore.
