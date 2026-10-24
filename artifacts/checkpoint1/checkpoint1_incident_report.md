# Checkpoint 1 incident observation report

**Status: INCOMPLETE — no practice incident was executed by this run.**

Incident/attempt identifier: `eyes-20261023T094107764041Z`
Observation window (UTC): 2026-10-23T09:36:07.764041+00:00 to 2026-10-23T09:41:07.764041+00:00
Collection started: 2026-10-23T09:41:07.764041+00:00; completed: 2026-10-23T09:41:50.739494+00:00

## Executive summary

This is a real environment-observation attempt, not a completed practice-incident demonstration. The external observer made the requests referenced below without modifying application files. No application root cause or recovery is established.

## Observed symptoms and affected components

- **E001 — container_inventory:** Read operation completed; this does not establish application health.
- **E002 — lifecycle_history:** Read operation completed; this does not establish application health.
- **E003 — metrics:** URLError: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **E004 — metrics:** URLError: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **E005 — metrics:** URLError: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **E006 — trace_services:** URLError: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **E007 — traces:** URLError: <urlopen error [WinError 10061] No connection could be made because the target machine actively refused it>
- **E008 — logs:** No published OpenSearch port discovered
- **E009 — practice_execution:** Read operation completed; this does not establish application health.
- **E010 — local_model_inventory:** Read operation completed; this does not establish application health.
- **E011 — llm_summary:** Read operation completed; this does not establish application health.

## Timeline and evidence references

| UTC observation time | Evidence | Source / result |
| --- | --- | --- |
| 2026-10-23T09:41:08.000987+00:00 | [E001](runs/eyes-20261023T094107764041Z/E001.json) | local command: ok |
| 2026-10-23T09:41:08.248281+00:00 | [E002](runs/eyes-20261023T094107764041Z/E002.json) | local command: ok |
| 2026-10-23T09:41:10.293677+00:00 | [E003](runs/eyes-20261023T094107764041Z/E003.json) | http://127.0.0.1:9090/api/v1/query_range?query=target_info&start=1792748167.764041&end=1792748467.764041&step=15: error |
| 2026-10-23T09:41:12.344075+00:00 | [E004](runs/eyes-20261023T094107764041Z/E004.json) | http://127.0.0.1:9090/api/v1/query_range?query=sum+by+%28service_name%29+%28rate%28traces_span_metrics_calls_total%7Bstatus_code%3D%22STATUS_CODE_ERROR%22%2Cspan_kind%3D%22SPAN_KIND_SERVER%22%7D%5B5m%5D%29%29&start=1792748167.764041&end=1792748467.764041&step=15: error |
| 2026-10-23T09:41:14.394940+00:00 | [E005](runs/eyes-20261023T094107764041Z/E005.json) | http://127.0.0.1:9090/api/v1/query_range?query=histogram_quantile%280.95%2Csum+by+%28le%2Cservice_name%29%28rate%28traces_span_metrics_duration_milliseconds_bucket%7Bspan_kind%3D%22SPAN_KIND_SERVER%22%7D%5B5m%5D%29%29%29%2F1000&start=1792748167.764041&end=1792748467.764041&step=15: error |
| 2026-10-23T09:41:16.440519+00:00 | [E006](runs/eyes-20261023T094107764041Z/E006.json) | http://127.0.0.1:8080/jaeger/ui/api/v3/services: error |
| 2026-10-23T09:41:18.496077+00:00 | [E007](runs/eyes-20261023T094107764041Z/E007.json) | http://127.0.0.1:8080/jaeger/ui/api/v3/traces?query.service_name=frontend&query.num_traces=5&query.start_time_min=2026-10-23T09%3A36%3A07.764041%2B00%3A00&query.start_time_max=2026-10-23T09%3A41%3A07.764041%2B00%3A00: error |
| 2026-10-23T09:41:18.498423+00:00 | [E008](runs/eyes-20261023T094107764041Z/E008.json) | OpenSearch: error |
| 2026-10-23T09:41:18.499423+00:00 | [E009](runs/eyes-20261023T094107764041Z/E009.json) | operator boundary: ok |
| 2026-10-23T09:41:18.545044+00:00 | [E010](runs/eyes-20261023T094107764041Z/E010.json) | http://127.0.0.1:11434/api/tags: ok |
| 2026-10-23T09:41:50.736878+00:00 | [E011](runs/eyes-20261023T094107764041Z/E011.json) | inference: ok |

## Logs, metrics, traces, deployment history

Each query/command, timestamp, response or failure is retained in the linked evidence. Metric expressions and trace windows are recorded in request URLs. Empty data means no matching observation, not zero errors. Container lifecycle events are not a deployment audit feed; Git history is not deployment history. No flag settings are queried.

## LLM provider and model

Selected route: `local-only`. Actual provider: `ollama`; actual model: `qwen2.5:3b`. No credential values are recorded.

The model proposal is retained as inference evidence; only the reviewed synthesis below is accepted for this report.

The local model helped organise the returned failures. Its output was reviewed against the actual responses. The accepted synthesis is:

- No containers matched this demo's Compose project in Ubuntu Docker, and no matching lifecycle events were returned in the requested window ([E001](runs/eyes-20261023T094107764041Z/E001.json), [E002](runs/eyes-20261023T094107764041Z/E002.json)). These facts establish neither application health nor deployment history.
- Prometheus returned connection refusals for the three requested queries; there are **no metric samples or measured anomalies** in this run ([E003](runs/eyes-20261023T094107764041Z/E003.json), [E004](runs/eyes-20261023T094107764041Z/E004.json), [E005](runs/eyes-20261023T094107764041Z/E005.json)).
- Jaeger service and trace requests also returned connection refusals; there are **no retrieved traces or error spans** ([E006](runs/eyes-20261023T094107764041Z/E006.json), [E007](runs/eyes-20261023T094107764041Z/E007.json)). The model had grouped these under metrics; that categorisation is corrected here.
- No OpenSearch port was discoverable because there was no matching demo container. No application/system log lines were retrieved ([E008](runs/eyes-20261023T094107764041Z/E008.json)). This is not evidence of a specific application/configuration fault.
- No practice incident was executed ([E009](runs/eyes-20261023T094107764041Z/E009.json)). Inventory/events commands and local inference did succeed; the model's phrase “no successful executions” must not be read as denying those successful read operations.

**Interpretation:** the required demo observability endpoints were unavailable from the collector during this attempt. Their underlying cause is not established. No practice-incident root cause, service recovery, or deployment/configuration change is inferred.

The original scoped model output remains in [E011](runs/eyes-20261023T094107764041Z/E011.json); the review is recorded in [operator_review.json](runs/eyes-20261023T094107764041Z/operator_review.json). An earlier run's invented running-MinIO claim was separately rejected and is excluded from accepted findings.

## Missing evidence and limitations

- No practice incident was injected or reset. The inspected faultctl paths rewrite the existing flag configuration, including through the UI API; that would violate file preservation.
- Application availability, error spans, metric anomalies, and logs require successful live backend responses. Failed requests are infrastructure observations only.
- No deployment/change audit service was found in the existing agent tool registry.
- Existing shopping-agent tools are unchanged; this external observer does not add tools to that agent or demonstrate its autonomous investigation.
- Cloud inference and local/cloud failover require a configured enabled cloud endpoint/key and are not proven by a local-only run.
- A configuration toggle is not used as a diagnostic oracle. No hypothesis is promoted to an established root cause.

## Reproduction

Run `python -B artifacts/checkpoint1/checkpoint1_observe.py` from the repository root. The script collects evidence and optionally calls the selected model; it never injects faults, starts/stops services, reads flags, installs dependencies, or alters source. Each invocation creates a new evidence directory. Review endpoint settings first.

## Acceptance status

**Completed:** source/capability reconnaissance, real local inference, referenced environment observations, external route controls, one-page architecture, and preservation checks.

**Incomplete:** real practice execution, incident log/metric/trace collection, deployment/change correlation, autonomous observability in the existing shopping agent, cloud inference, and real cross-provider fallback. This is not a passed Eyes checkpoint.
