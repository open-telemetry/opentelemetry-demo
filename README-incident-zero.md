# Incident Zero: an AI on-call engineer

> Stub. Written up properly on Day 2 (setup, how to run, approval gate, kill switch, known limitations).

An agent that investigates an incident in the OpenTelemetry Demo using read-only tools
(metrics, traces, logs, container health), then reports a root cause with evidence and a
confidence level, or escalates to a human when it is not sure.
The demo's own files are not modified; everything of ours is added next to them.
Rules and context: `CONTEXT.md`. Work order: `plan.md`. Declarations: `docs/DECLARATIONS.md`.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-incident.txt
cp .env.incident.example .env.incident   # then fill in the LLM settings; this file is gitignored
```

The demo must already be running (`make start`).

## Checks

```bash
.venv/bin/python -m tools.check_backends     # Prometheus, Jaeger, OpenSearch, containers
.venv/bin/python -m oncall.llm --check       # one completion + one tool-call round trip
```

## Verified facts

Checked read-only on 2026-10-23 against the running demo (compose project `opentelemetry-demo`, 28 containers).

| Backend | How we reach it | Notes |
|---|---|---|
| Prometheus | `http://localhost:9090` (fixed host port) | version 3.13.3 |
| Jaeger | `http://localhost:8080/jaeger/ui/api/v3/...` via the front proxy | Jaeger v2: the classic `/api/services` and `/api/traces` paths return 404 on both the proxy and the direct port; the **v3 API** works. The direct host port (61421 today) changes on every start, so the proxy is preferred. |
| OpenSearch | `http://localhost:<port>`, port found with `docker port opensearch 9200` | 60668 today, not fixed. Cluster status `yellow` (single node, normal). |

Metrics:
- `traces_span_metrics_calls_total` exists.
- `traces_span_metrics_duration_milliseconds_bucket` exists (also `_count` and `_sum`).
- `status_code` values are `STATUS_CODE_ERROR`, `STATUS_CODE_OK`, `STATUS_CODE_UNSET`. Most spans are `UNSET`, so error rate must count `STATUS_CODE_ERROR` against all calls, not against `OK`.
- Other labels on these series include `service_name`, `span_name`, `span_kind`, `service_version`.

Logs:
- OpenSearch has the index `otel-logs-2026-10-23` (a daily `otel-logs-*` index; 882 documents at check time). The field names (`body`, `severity.text`, `observedTimestamp`) are not verified yet.

Not yet verified: log field names, the shape of Jaeger v3 trace results, how to identify flag-evaluation spans.

## Known limitations

- LLM provider, model and key are not configured yet; `oncall.llm --check` fails with "no key configured" until they are.
- The LLM adapter's Anthropic and OpenAI code paths have not been run against a real API yet.
