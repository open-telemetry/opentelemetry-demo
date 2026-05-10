# Telemetry Sanity Tests — Design Document

## Problem

The demo previously used Tracetest for trace-based integration testing, but that project went defunct and was removed. There's no holistic replacement that validates telemetry is flowing across all three pillars (traces, metrics, logs) to the observability backends. Services can silently stop emitting telemetry without CI catching it.

## Goals

- Sanity-check that each service sends expected telemetry to the correct backends
- Run on every PR in CI
- Run locally via `make` (same as other demo workflows)
- OS-agnostic (Dockerized test runner)
- Easy to extend: adding a service = adding one line to a config dict
- Does NOT validate semantic conventions or attribute correctness (that's weaver's job)

## Non-Goals

- Full trace-path validation (span parent-child relationships)
- Attribute/semconv correctness (covered by `weaver-check`)
- Performance/load testing

## Approach

Dockerized Python (pytest) container running on the same Docker network as the demo. Queries backend APIs to verify services are producing telemetry.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Docker Compose Network (opentelemetry-demo)            │
│                                                         │
│  ┌──────────┐   OTLP    ┌───────────────┐              │
│  │ Services │ ─────────▶│ OTel Collector │              │
│  └──────────┘            └───────┬───────┘              │
│                                  │                      │
│              ┌───────────────────┼───────────────┐      │
│              ▼                   ▼               ▼      │
│     ┌────────────┐     ┌────────────┐   ┌───────────┐  │
│     │   Jaeger   │     │ Prometheus │   │ OpenSearch │  │
│     │  (traces)  │     │ (metrics)  │   │  (logs)   │  │
│     └─────┬──────┘     └─────┬──────┘   └─────┬─────┘  │
│           │                   │                 │        │
│           ▼                   ▼                 ▼        │
│     ┌─────────────────────────────────────────────────┐ │
│     │         telemetry-tests (pytest container)      │ │
│     │   Queries each backend API to verify telemetry  │ │
│     └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## File Structure

```
test/telemetry/
├── DESIGN.md              # This file
├── Dockerfile             # Lightweight Python container
├── requirements.txt       # pytest + requests
├── conftest.py            # Fixtures, polling helpers, parametrization
├── services.py            # Service-signal matrix (single source of truth)
├── test_collector.py      # OTel Collector health check
├── test_traces.py         # Jaeger trace verification
├── test_metrics.py        # Prometheus metrics verification
└── test_logs.py           # OpenSearch log verification
```

## Service-Signal Matrix

Single source of truth in `services.py`. Each service declares which signals it emits:

| Service | Traces | Metrics | Logs | Scope |
|---------|--------|---------|------|-------|
| ad | yes | yes | yes | minimal |
| cart | yes | yes | no | minimal |
| checkout | yes | no | no | minimal |
| currency | yes | yes | no | minimal |
| email | yes | yes | no | minimal |
| frontend | yes | yes | no | minimal |
| payment | yes | yes | no | minimal |
| product-catalog | yes | no | no | minimal |
| product-reviews | yes | yes | yes | minimal |
| quote | yes | no | no | minimal |
| recommendation | yes | yes | yes | minimal |
| shipping | yes | yes | no | minimal |
| accounting | yes | no | yes | full |
| fraud-detection | yes | no | no | full |
| load-generator | yes | no | yes | minimal |

## Backend API Queries

**Jaeger (traces):**
- List services: `GET http://jaeger:16686/jaeger/ui/api/services`
- Find traces: `GET http://jaeger:16686/jaeger/ui/api/traces?service={name}&limit=1&lookback=1h`

**Prometheus (metrics):**
- Check service presence: `GET http://prometheus:9090/api/v1/query?query=target_info{service_name="{name}"}`

**OpenSearch (logs):**
- Search by service: `POST http://opensearch:9200/otel-logs-*/_search`
  ```json
  {"query": {"match_phrase": {"resource.service.name": "{name}"}}, "size": 1}
  ```

**OTel Collector (health):**
- TCP connect to `otel-collector:4317` (gRPC OTLP port)

## Test Execution Flow

1. Demo starts (all services + backends + load-generator)
2. Load-generator produces traffic for ~90s (configurable `WARMUP_SECONDS`)
3. Test container starts, waits for warmup
4. Tests query each backend with retries (poll every 5s, timeout 60s per check)
5. Each test is parametrized: `test_traces[checkout]`, `test_metrics[payment]`, `test_logs[ad]`
6. pytest exits 0 (pass) or non-zero (per-service/signal failure messages)

## Makefile Targets

```bash
make run-telemetry-tests           # Full scope (all services including Kafka-dependent)
make run-telemetry-tests-minimal   # Minimal scope (excludes Kafka-dependent services)
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `JAEGER_URL` | `http://jaeger:16686` | Jaeger query endpoint |
| `PROMETHEUS_URL` | `http://prometheus:9090` | Prometheus query endpoint |
| `OPENSEARCH_URL` | `http://opensearch:9200` | OpenSearch endpoint |
| `COLLECTOR_URL` | `http://otel-collector:13133` | Collector health endpoint |
| `TEST_SCOPE` | `minimal` | `minimal` or `full` |
| `WARMUP_SECONDS` | `90` | Seconds to wait before testing |

## CI Integration

New job in `.github/workflows/checks.yml`:
- Depends on `build_images` (uses pre-built images)
- Starts demo, waits for warmup
- Runs `make run-telemetry-tests`
- Uploads JUnit XML as artifact

## Extending

- **New service**: Add one entry to `SIGNAL_MATRIX` in `services.py`
- **New backend/signal type**: Add a new `test_*.py` file following the same pattern
- **New check for existing signal**: Add a test function in the appropriate file
- **Adjust timeouts**: Set `WARMUP_SECONDS` or `POLL_TIMEOUT` env vars
- **Run single test**: `pytest test_traces.py -k "checkout" -v`

## Relationship to Weaver

Weaver (`weaver-check` in CI) validates the telemetry schema registry — correct attribute names, types, and semantic conventions. These telemetry sanity tests validate that telemetry *flows* end-to-end. They are complementary:

- **Weaver**: "Are the attribute definitions correct?" (static analysis)
- **Telemetry tests**: "Is each service actually sending data to backends?" (runtime validation)
