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
.venv/bin/python -m tools.snapshot           # container_health + query_metrics once, as a table
.venv/bin/python -m pytest                   # unit tests (no live demo needed)
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

Logs (checked read-only 2026-10-23, OpenSearch):
- Index `otel-logs-YYYY-MM-DD` (pattern `otel-logs-*`); one daily index.
- Message field `body` (text). Time fields `observedTimestamp` and `@timestamp` (both dates).
- Level field `severity.text` (text, with a `.keyword` sub-field). Values are NOT normalised: seen `INFO`, `info`,
  `Information`, `error`, `ERROR`, `Error`, `warn`, `WARN`. Level filters must be case-insensitive.
- Service field `resource.service.name` (with `.keyword`). Trace and span ids are `traceId` / `spanId`.
- `severity` is an empty object on proxy access logs, so not every line has a level.

Span metrics and `query_metrics` (checked live, 2026-10-23):
- Prometheus scrapes once a minute, so a `rate()` window under 2 minutes has too few samples and returns nothing.
  `query_metrics` therefore requires `window_minutes >= 2` (default 5).
- Span kinds present: SERVER, CLIENT, INTERNAL, CONSUMER, PRODUCER. Service-level rates use SERVER + CONSUMER only;
  the per-span drill-down uses all kinds. See the comment at the top of `tools/metrics.py`.
- Container metrics exist (`container_memory_percent_ratio`, `container_cpu_utilization_ratio`, keyed by `container_name`).
  Memory % agrees with `docker stats` within about a point and is included. CPU does NOT agree: Prometheus showed ~10-15 %
  for `payment` while `docker stats` showed ~0.7 %, so CPU is left out of `query_metrics`; `container_health` reports CPU
  from `docker stats`. A stopped container's last sample lingers for a few minutes, so memory is filtered to samples under 2 minutes old.
- Kafka lag exists: `kafka_consumer_group_lag_sum_ratio` (labels `group`, `topic`; the value is a message count despite the name).
  The `accounting` group sits at roughly 130-150 messages even when healthy, so only a change matters.
- With `cache-unavailable` injected the cart service's own error rate does NOT rise: its spans stay `STATUS_CODE_UNSET`
  (the gRPC failure is not marked as a span error) and its request rate drops instead. The failure shows as errors on
  `frontend-proxy` SERVER spans and `load-generator` CLIENT spans, plus `valkey-cart` exited in Docker.
- With `payment-failure` at 100 %, `payment` and `checkout` both show 100 % error rate within ~90 s.

Traces (Jaeger v3, checked live 2026-10-23; details in the header of `tools/traces.py`):
- `GET <jaeger>/api/v3/traces` with `query.start_time_min` and `query.start_time_max` (both required, RFC 3339),
  `query.search_depth` (number of traces, newest first), optional `query.service_name` and
  `query.attributes={"error":"true"}` (matches status ERROR only). `GET .../api/v3/traces/<id>` fetches one trace.
- The answer is OTLP JSON. Span kind is an int, an UNSET status is `{}`, ERROR is `{"code": 2, "message": ...}`.
  "Nothing matched" is HTTP 404 with `{"error": {"message": "No traces found"}}`, which is not a failure.
- Flag-evaluation spans: client spans named `<flag service>.evaluation.v2.Service/...` in cart, payment and fraud-detection,
  plus their HTTP leg (a `POST` client span in cart whose `server.address` / `url.full` name the flag service), plus
  `feature_flag.evaluation` / `feature_flag` events on server spans (checkout, product-catalog, cart, recommendation) and a
  `demo.feature_flag.*` span attribute in recommendation. All are removed in `tools/sanitize.py`.
- Clock skew: the quote service's spans can sit ~12 minutes later than the rest of their trace, so a trace's duration is the
  longest single span, not last end minus first start.
- The load generator calls an `agent` service that is not running; its `user_ask_agent` traces show a ConnectionError
  all the time. That is background noise in this environment, not an incident.

Logs: the payment failure is logged at level `warn` ("Payment request failed. Invalid token. ..."), and cart logs
"Connection failed. Disposing the object" at level `Information`, so `query_logs` also keeps lines whose text is clearly
an error whatever their level.

## Tools (P3)

All tools return a `ToolResult` (`tools/result.py`) with `state` = `data` / `no_data` / `backend_error`, the exact
queries or commands, the time window, capped items and any error. Results go through `tools/sanitize.py` and into the
evidence ledger (`tools/ledger.py`, IDs like `M1`, `C2`).

## Tools (P4)

`query_traces` (IDs `T1`..), `query_logs` (`L1`..) and `deploy_history` (`D1`..) follow the same rules as the P3 tools.
Every one reports "N items removed by sanitiser" in its notes (the count only, never the content).
`python -m tools.snapshot --save-ledger PATH` runs all five tools and saves the ledger; `tests/test_leak.py` scans the saved ledgers
in `tests/fixtures/ledgers/` and, when the backends are up, fresh output.

## Known limitations

- LLM provider, model and key are not configured yet; `oncall.llm --check` fails with "no key configured" until they are.
- The LLM adapter's Anthropic and OpenAI code paths have not been run against a real API yet.
- The sanitiser holds no flag key names (by design). A log line that mentions only a key name and none of the flag-system
  words (the flag service, `feature_flag`, `feature flag`, `openfeature`) is not removed; `tests/test_leak.py` is what would catch it.
- `query_traces` ranks within a sample of the newest 40-100 traces, so a rare failure can be missed; `error_groups` summarises the whole sample.
- `deploy_history` cannot tell a real deploy from a restart, and `make start --force-recreate` makes everything look new.
