# OpenTelemetry Demo With KalDB

This local setup runs the OpenTelemetry Demo while sending telemetry to a local
KalDB checkout.

All KalDB-specific OpenTelemetry Demo files live in `local/kaldb/`. The root
`Makefile` only exposes convenience targets.

The KalDB build must include OTLP/HTTP trace ingestion at `POST /v1/traces` on
port `8086`. Builds without that endpoint can accept logs, but trace exports
fail with HTTP `404`. Rebuild the KalDB image after changing backend versions;
startup can reuse an existing image.

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
KalDB uses a 30-second ZooKeeper session timeout and a 5-second connection
timeout to tolerate local startup and scheduling delays. Override these with
`KALDB_ZK_SESSION_TIMEOUT_MS` and `KALDB_ZK_CONNECT_TIMEOUT_MS`.

## URLs

The KalDB overlay uses Grafana `13.2.1` to support the installed datasource and
app plugins. Override it with `KALDB_GRAFANA_IMAGE` when needed.

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

## OpenSearch Dashboards

Open `http://localhost:5601/app/discover` and create an index pattern for each
exact dataset name: `otel-demo-logs` and `otel-demo-traces`.

- For logs, select `@timestamp` as the time field.
- For traces, select the option to use no time filter. The current OTLP trace
  documents contain `_timesinceepoch`, not `@timestamp`, and Dashboards does not
  offer `_timesinceepoch` in its time-field selector. An `@timestamp` filter
  would hide the trace documents. Use Grafana for time-filtered span browsing.

Wildcard index patterns are not supported by this local KalDB setup.

Use Discover to search logs and span documents. The provisioned dashboard and
trace-by-ID waterfall are in Grafana.
Span documents use `trace_id`; log documents from the OpenSearch exporter use
`traceId`. The Grafana trace-to-logs link searches the latter field.

## Verify

```bash
make verify-kaldb
```

Generate traffic in the shop, then open the `KalDB OTel Demo` dashboard. Use
`otel-demo-logs` for log search, `otel-demo-traces` to find trace IDs, and
`otel-demo-traces-waterfall` for trace-by-ID waterfall rendering in Grafana
Explore.

## Two-user security demo (OpenSearch 2.11)

The [separate permissions demo](permissions/README.md) uses real Security users,
two native tenants/dashboards, two KalDB datasets, and gateway index/FLS checks.
It has its own Compose project and loopback ports; it does not enable security
in this existing OTel demo profile.

```sh
make start-kaldb-permissions KALDB_HOME=/path/to/kaldb-permissions-checkout
make verify-kaldb-permissions
make showcase-kaldb-permissions
make stop-kaldb-permissions
```
