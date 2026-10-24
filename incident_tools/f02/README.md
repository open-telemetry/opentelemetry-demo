# F02: read-only observability tools

Status: implemented as an external Python package; offline contract tests pass. **Live integration validation is pending.** These tools have not observed a real demo incident in this implementation session. This does not complete Checkpoint 1 or F02's live acceptance criterion.

No existing application, shopping-agent, fault controller, Compose, dependency, or build file is changed. No extra service or Python package dependency is added. Python **3.11 or newer** is required for the standard-library TOML reader. Docker CLI access is needed only for container tools. No LLM, API key, or provider installation is needed to run F02.

## Where this fits

One future diagnostic investigator can choose among these deterministic tools. The package constructs queries, validates service/time scope, parses telemetry, and returns selected evidence; it does not ask an LLM to interpret raw log files. F01 will detect alerts and initiate investigations. F03 will implement evidence-dependent tool selection. Neither is implemented here, and the existing shopping assistant is not repurposed or connected to these tools.

The runtime interface is an in-process Python API or a newline-delimited JSON stdin/stdout adapter. Function schemas are exported for future agent integration. This is not an MCP server or a deployed HTTP service. Keep the operator configuration and evidence directory outside model control.

## Tools and inspected dependencies

| Callable tool | Existing source/interface | Returned evidence |
| --- | --- | --- |
| query_metrics | Prometheus GET /api/v1/query_range | Exact numeric strings and parsed finite values, UTC evaluation times, labels, generated PromQL, units, query hash and series identifier |
| search_logs | OpenSearch POST /otel-logs-*/_search (read-only search) | Selected body/severity, UTC observed timestamp, service, index/document ID and optional trace/span IDs |
| search_traces | Jaeger GET /jaeger/ui/api/v3/traces | OTLP span IDs, parent ID, trace ID, status code, duration, nanosecond timestamps, selected attributes |
| container_health | Docker ps + selected-field inspect, restricted to Compose project/service | Container ID, current state, health status when defined, exit code and observation time |
| container_events | Docker events with project/service/type filters and finite past window | Event time, action and container ID; explicitly lifecycle evidence |
| deployment_history | Optional operator-selected existing JSONL deployment audit feed | Deployment ID, time, service, revision, original source reference, line number and file SHA-256; unavailable by default |

Repository contracts used: compose.yaml, compose.full.yaml, compose.observability.yaml, src/jaeger/config.yml, src/otel-collector/otelcol-config-observability.yml, src/prometheus/prometheus-config.yaml, src/grafana/provisioning/datasources/opensearch.yaml, src/grafana/provisioning/dashboards/demo/demo-dashboard.json, and test/telemetry/{conftest.py,test_logs.py,test_traces_edges.py}. Existing tests were inspected, not executed: their warmup probes generate checkout traffic.

Jaeger uses the existing proxy base path /jaeger/ui. The pinned 2.21.0 [query parser](https://github.com/jaegertracing/jaeger/blob/v2.21.0/cmd/jaeger/internal/extension/jaegerquery/internal/apiv3/query_parser.go) retains the repository's snake_case query parameters and num_traces alias; the [official API definition](https://github.com/jaegertracing/jaeger-idl/blob/main/proto/api_v3/query_service.proto) defines wrapped streaming trace results. Its in-memory storage is bounded. OpenSearch index and field defaults come from the collector and Grafana configuration; the live index mapping remains to be confirmed. Docker project name must match the real Compose project label, not just its network name. Service names must match actual telemetry resource service.name / Prometheus service_name and Compose service labels; adapt the explicit allowlist if your deployment uses different names. No cross-source service aliases are inferred.

## Configuration

Copy operator.example.toml to a new operator-owned file, then configure endpoints, service allowlist, limits, and Docker transport. Never edit existing demo configuration for these tools. Relative deployment audit paths resolve relative to the new TOML file.

Run Python inside Ubuntu WSL with Docker available and transport = "native". Windows Python can instead use transport = "wsl" and distro = "Ubuntu"; that argument/transport path is fixture-tested, but actual WSL CLI quoting and engine access still require live validation. No Docker Desktop requirement is introduced.

Prometheus defaults to localhost:9090. Jaeger defaults to the existing localhost:8080 proxy. OpenSearch is intentionally unconfigured until its dynamic host port is discovered. Do not use an assumed localhost:9200: the Compose file publishes a dynamic port. You can use Docker-internal service DNS only when Python actually runs on the corresponding network.

Optional per-backend bearer_token_env points to an environment variable. Tokens are loaded from the environment, require HTTPS, and are never placed in configuration/output. TLS verification is enabled; URL credentials, query strings, fragments, redirects, and implicit proxy configuration are rejected/disabled. This implements bearer authentication only; no installed cloud/LLM provider is assumed. An authenticated backend requiring a different scheme needs a supported read-only gateway or a later extension to this external package.

service_field selects the OpenSearch _source field to validate. If live mappings require a keyword subfield, set service_query_field separately, for example resource.service.name.keyword, while keeping service_field = "resource.service.name". The optional setting must match a real mapping. There is no arbitrary search DSL, PromQL, endpoint, shell command, file path, or header argument in the agent-callable schema.

Defaults: 1-hour maximum window, 100 maximum result items, 2,000 total metric samples, 15-second minimum metric step, 2 MiB backend response limit, 10-second socket/subprocess timeout and one retry for connection failures or HTTP 429/502/503/504. Retries are bounded to two by configuration. A socket timeout is an I/O inactivity timeout, not a guaranteed total query deadline. Docker stdout/stderr go to temporary files until the process ends or times out; returned stdout is byte-limited. Resource constraints should also be applied by the operator if running against an untrusted daemon. Model-visible text fields are capped at 4,096 characters.

## Result contract

Every tool result has schema_version, status, origin (backend or fixture), collected_at, observations, warnings, and an evidence_id derived from the complete result before adding the ID. Valid requests also identify tool, service and the UTC requested window. Successful/empty observations include provenance (backend, endpoint or scope, and query/command description); HTTP observations include a canonical query SHA-256. Preserve the whole JSON result for reproducibility. Evidence IDs identify the saved selected result, not a persistent backend object; rows retain separate backend source IDs.

| status | Meaning |
| --- | --- |
| ok | Valid selected observations returned without reported limitations |
| partial | Observations returned with a reported bound, incomplete coverage, snapshot/history qualification, or backend warning |
| no_data | No usable matching observations; never equivalent to zero errors, health, or absence of an incident |
| unavailable | Missing configuration/audit feed, connectivity/authentication/HTTP failure or unavailable Docker transport |
| invalid_request | Unsupported tool/argument, service, malformed time window or excessive bounds; no backend request issued |
| error | Malformed, oversized, out-of-scope, or otherwise unsupported backend data |

Metric templates:

- request_rate: server-span calls per second, from traces_span_metrics_calls_total over 2 minutes.
- error_rate: fraction of errored server-span calls divided by all server-span calls over 2 minutes. Missing error series or undefined denominators remain no_data; they are never filled with zero.
- latency_p95_ms: p95 server-span duration from traces_span_metrics_duration_milliseconds_bucket over 2 minutes, in milliseconds.
- service_presence: target_info metadata for the requested service. Presence is not proof of application health.

The first three constrain span_kind="SPAN_KIND_SERVER". These are service server-span metrics, not a guaranteed count of user transactions. The inspected dashboard contains these metric families, but actual availability, labels, units, and sufficient samples must be checked live. Warm up for more than two minutes. Prometheus range timestamps are evaluation times; source sample freshness is not independently established. A series ending well before the requested end is flagged. NaN/infinities are omitted with a warning, not converted to numbers or zeros.

Prometheus range-query bounds are normalized inward to whole milliseconds: start rounds upward and end rounds downward. The result retains the original UTC requested window; provenance records requested_window, effective_window, timestamp_precision and request_sent alongside the actual query and its hash. Response samples must remain inside both the requested and effective windows. If the requested window contains no millisecond evaluation timestamp, the tool returns no_data with a warning and sends no backend query; effective_window and query are null. This normalization does not change log or trace timestamp handling.

Traces are selected by span start time (start inclusive, end exclusive) and the exact resource service. The reader handles one JSON envelope, newline-delimited streamed envelopes, and an empty successful stream. A late stream error rejects the response rather than treating earlier chunks as complete evidence. Other services in a returned trace are excluded; query them separately for cross-service correlation. Optional trace_id filters this bounded search locally. It does not fetch an unbounded full trace, and a miss does not prove the trace is absent. Both hex and base64 OTLP IDs are normalized to hex; original nanosecond timestamps are retained. Events and arbitrary span attributes/status messages are excluded to avoid dumping PII, credentials, or flag-resolution metadata.

Logs use observedTimestamp by default, which can differ from event time. The tool returns selected fields and checks service/time scope again after the query. Feature-flag resolution messages matching the documented policy are omitted, as are non-allowlisted attributes. This is a best-effort text policy, not a proof that arbitrary application prose cannot disclose an injected fault. Existing flag files and faultctl state are never read. Message text is untrusted evidence, never instructions. Common credential assignments, structured secret keys, bearer/basic authorization, URL credentials, configured token values and email addresses are redacted. This is not a general PII/secret classifier; operators must review unexpected text before sharing evidence. Long log bodies have body_truncated=true and a warning.

Health is always a current collection-time snapshot; it does not reconstruct the requested historical window. No healthcheck means health=null, not healthy. A container can disappear between ps and inspect; that produces an explicit failure. Lifecycle history is subject to Docker's recent-event retention and is always qualified. Git commits and container starts are never presented as proof of deployment.

An optional deployment audit JSONL record must contain nonempty id, service, timestamp (timezone-aware), revision and source fields. For example, an existing deployment pipeline may export a real run ID, deployed revision, and pipeline URL. Extra fields are omitted. No sample deployment file is installed as real evidence. The operator is responsible for provenance/authenticity/completeness of this feed; without it, deployment_history returns unavailable.

## Local offline verification

From the repository root:

~~~sh
python3 -B -m unittest discover -s incident_tools/f02/tests -v
python3 -B -m incident_tools.f02 --config incident_tools/f02/operator.example.toml schemas
python3 -B -m incident_tools.f02.verify --output-dir artifacts/f02/verification-new
~~~

On Windows use python instead of python3. The verify output directory must not exist. It records the test output and compares all 677 pre-existing tracked/nonignored files against artifacts/f02/baseline.json, taken before implementation. Re-running creates a new directory; it does not overwrite prior evidence. Fixture tests use a temporary loopback HTTP server, mocked Docker, and a temporary synthetic audit feed. They never start Docker containers, invoke faultctl, change flags, or call a real LLM.

## Live handoff (Ubuntu WSL, when the unchanged demo is available)

First run the demo and load generator using the existing setup instructions. Ensure the observability Compose layer is included. This sequence only reads the running environment; it does not start a fault or alter the application.

~~~sh
cd /path/to/opentelemetry-demo
python3 --version  # Must be 3.11+.
docker ps --format '{{.Names}} {{.Label "com.docker.compose.project"}} {{.Label "com.docker.compose.service"}}'
docker compose -f compose.yaml -f compose.full.yaml -f compose.observability.yaml port opensearch 9200
curl -fsS http://localhost:8080/jaeger/ui/api/v3/services
cp -n incident_tools/f02/operator.example.toml /tmp/f02-operator.toml
~~~

Edit only /tmp/f02-operator.toml: configure the discovered OpenSearch port, actual Compose project label, allowlisted service names and any endpoint differences. Confirm OpenSearch fields/index using the existing Grafana datasource or its read-only mapping API. Wait for representative traffic and sufficient span metrics. The example below uses checkout for metrics/traces and email for logs because existing telemetry tests explicitly expect email logs; substitute services actually emitting the required signals.

~~~sh
config=/tmp/f02-operator.toml
run_dir="$(mktemp -d artifacts/f02/live-XXXXXX)"
end="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
start="$(date -u -d '5 minutes ago' +%Y-%m-%dT%H:%M:%SZ)"
python3 -B -m incident_tools.f02 --config "$config" call query_metrics --service checkout --start "$start" --end "$end" --metric service_presence --output "$run_dir/01-presence.json"
python3 -B -m incident_tools.f02 --config "$config" call query_metrics --service checkout --start "$start" --end "$end" --metric request_rate --output "$run_dir/02-rate.json"
python3 -B -m incident_tools.f02 --config "$config" call query_metrics --service checkout --start "$start" --end "$end" --metric error_rate --output "$run_dir/03-errors.json"
python3 -B -m incident_tools.f02 --config "$config" call query_metrics --service checkout --start "$start" --end "$end" --metric latency_p95_ms --output "$run_dir/04-latency.json"
python3 -B -m incident_tools.f02 --config "$config" call search_logs --service email --start "$start" --end "$end" --limit 20 --output "$run_dir/05-logs.json"
python3 -B -m incident_tools.f02 --config "$config" call search_traces --service checkout --start "$start" --end "$end" --limit 20 --output "$run_dir/06-traces.json"
python3 -B -m incident_tools.f02 --config "$config" call container_health --service checkout --start "$start" --end "$end" --output "$run_dir/07-health.json"
python3 -B -m incident_tools.f02 --config "$config" call container_events --service checkout --start "$start" --end "$end" --output "$run_dir/08-lifecycle.json"
python3 -B -m incident_tools.f02 --config "$config" call deployment_history --service checkout --start "$start" --end "$end" --output "$run_dir/09-deployments.json"
printf '%s\n' "$run_dir"
~~~

Outputs are created exclusively: existing evidence files are never overwritten. Exit 0 means a result of ok, partial or no_data; it does not mean healthy or live acceptance passed. Exit 1 indicates unavailable/error/invalid_request; exit 2 indicates configuration or output failure. The default deployment call deliberately exits 1 and saves unavailable unless a real audit feed is configured.

Before calling live validation complete, inspect actual values, source IDs and times: finite metric samples with verified units/labels; nonempty logs and spans from emitting services; scoped container IDs/health; verified log/trace correlation when a shared trace ID exists. Compare selected evidence to the backend query/view. Resolve partial/error responses or record their limits. If there are no error samples during a healthy baseline, record that limitation and validate error telemetry during the later approved practice incident. Lack of lifecycle events in a short window is acceptable; lack of a deployment feed must remain unavailable. Never substitute fixture outputs for missing live evidence.

## Agent interface

Python:

~~~python
from incident_tools.f02 import ObservabilityTools

tools = ObservabilityTools('/tmp/f02-operator.toml')
function_schemas = tools.schemas()
result = tools.call('search_logs', {
    'service': 'email',
    'start': '2026-10-23T09:00:00Z',
    'end': '2026-10-23T09:05:00Z',
    'limit': 20,
})  # Use a current incident window; the dates above are syntax examples.
~~~

Or launch a fixed operator command:

~~~sh
python3 -B -m incident_tools.f02 --config /tmp/f02-operator.toml serve
~~~

Send one JSON object per line with exactly tool and arguments. Each call yields one JSON result per stdout line. Invalid envelopes are rejected; valid requests are checked against the actual runtime allowlist and bounds, not just advertised schemas. Do not expose configuration paths or the process command line as model arguments. Grant an agent only this dispatcher, not arbitrary Python execution or Docker access. The tool API restricts operations; it is not a sandbox around a caller already holding the Docker socket or host privileges.

## Remaining work

- Run the live handoff and verify backend shapes, configured endpoints, scopes, and metric semantics against actual telemetry.
- Supply real deployment audit evidence if that capability is available; otherwise retain the explicit limitation.
- Connect these schemas/results to the future diagnostic investigator in F03. The current package has no autonomous reasoning loop.
- Implement F01 alert intake/deduplication and investigate a real sustained threshold breach. No detection or incident success is claimed here.
