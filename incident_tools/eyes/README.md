# Eyes: F01 + F03 + Checkpoint 1 artifact workflow

This external standard-library Python 3.11+ package adds a deterministic alert poller, one model-driven diagnostic investigator, durable evidence, and report/SVG exports around F02. Existing demo, F02, shopping agent, faultctl, dependencies and build files are unchanged. No model installation or cloud connection is assumed. The implementation is intended for Ubuntu WSL, using the existing F02 operator configuration and running demo.

## Detection and investigation

F01 polls configured service server-span error fractions and p95 latency through F02. Defaults are proposals: 15-second polling, 5-minute observation range, two fresh consecutive breaches, error fraction > 5%, p95 > 1000 milliseconds, at least 10 estimated server calls in the underlying 120-second rate interval, 120-second startup warmup, and 300-second cooldown. F02 still computes rates/quantiles over its fixed 2-minute rate window; the observation range does not change that expression. Minimum requests are a rate-derived coverage estimate, not a transactional count. Tune thresholds against actual baseline behavior.

Because Prometheus query-range timestamps represent evaluation time, F01 separately queries min(timestamp(traces_span_metrics_calls_total{service_name=...,span_kind="SPAN_KIND_SERVER"})). It requires a source age of 0–90 seconds, advances streaks only on increasing source timestamps, and resets streaks for missing/stale/partial observations, low volume, warmup, or excessive gaps. This conservative minimum freshness check can suppress alerts when one replica/series stops publishing. It does not prove histogram publication freshness separately; validate actual collector publication and histogram/counter alignment during live acceptance. No-data error series stays unknown, not zero.

SQLite stores per-rule streaks, active incidents, cooldowns and an investigation queue. Repeated symptoms join the active service incident; different services queue separate incidents. Qualified normal samples close incidents after two fresh observations for their recorded symptoms. Unknown data never establishes recovery. Closure is detector bookkeeping, not F09 recovery verification. Alert records contain measured values, threshold, times, original query and evidence references, never an injected fault name. One operator process handles queued investigations sequentially. Long investigations delay the next poll; polling is not a real-time scheduling guarantee.

F03 sends incident context and read-only schemas to one model. Each JSON tool decision includes rationale and arguments, is checked against the incident window and F02 service/time bounds, executes through F02, and feeds the result back before the next decision. Identical repeated queries and mutable/unknown tools are rejected. Defaults allow 12 tools, 120 seconds, one selected item per call and bounded context. One-trace requests accommodate large Jaeger responses seen in live F02 testing. Provider I/O timeout is an inactivity limit; overall time budget is checked before/after model calls and between tools, not an operating-system deadline around DNS or streaming responses.

Every model step records provider, model, rationale, prior evidence IDs, arguments and results. Local-only, cloud-only, local-first and cloud-first routing are available over the already-used Ollama /api/chat or OpenAI-compatible /chat/completions interfaces. Native SDKs, MCP or new services are unnecessary. Optional cloud is disabled until explicitly configured with an existing compatible API, HTTPS, model and environment key. Provider retries, request rate, output tokens, context and resource options are bounded in operator configuration. Local model choice/path provisioning happens in the installed runtime; this package does not install models. TLS verification stays enabled and redirects/proxies are disabled. Only the generic compatible chat protocol is supported; provider-specific authentication or generation contracts require an appropriate existing gateway. Every selected fallback provider must be explicitly enabled/configured.

Interpretation citations must reference saved observations with data. Citation validation cannot prove a model claim follows from that evidence, so the report labels interpretations for operator review and does not certify root cause. Telemetry is untrusted text. No action executor, flag reader or approval/remediation tool is exposed. Configured API tokens are included in F02's redaction set before inference. Arbitrary secrets in prose still require the existing F02 text-review policy.

## Run on the live environment later

From the repository root in Ubuntu WSL, with Python 3.11+ and your validated F02 configuration available:

~~~sh
config=$(mktemp /tmp/eyes-operator.XXXXXX)
cp incident_tools/eyes/operator.example.toml "$config"
nano "$config"
~~~

Set f02_config to your actual F02 TOML path. Set artifact_dir to a dedicated writable path (for example an absolute path under artifacts/eyes/live-*). Confirm workflow.services, model endpoint/model, and model availability. The template's qwen2.5:3b matches a previously observed Ollama model; verify your teammate's runtime independently. Do not put credentials in TOML. A cloud provider is not automatically connected because an endpoint format is supported.

~~~sh
# Optional: validate detection/queue behavior without making inference requests.
python3 -B -m incident_tools.eyes --config "$config" watch --detect-only --polls 20

# Normal automatic alert -> queued incident -> adaptive investigation -> exports.
python3 -B -m incident_tools.eyes --config "$config" watch

# Read saved incidents, or explicitly investigate a queued/incomplete incident.
python3 -B -m incident_tools.eyes --config "$config" list
python3 -B -m incident_tools.eyes --config "$config" investigate --id YOUR_INCIDENT_ID

# Export the one-page SVG separately (use a new output path).
python3 -B -m incident_tools.eyes --config "$config" diagram --output /tmp/eyes-architecture.svg
~~~

Stop watch with Ctrl+C. Incidents and queue state persist across restarts. operator.lock prevents multiple writers/investigators. After an abrupt crash, verify the old process is stopped before removing that package-owned lock. A job left running is not silently replayed; retain its evidence and operator-review the interrupted job before recovery. Detection-only mode needs no working inference provider. A normal-mode startup validates provider settings but does not call a provider until an incident is queued.

Each investigation exports to a new incident/attempt directory:

- checkpoint1_incident_report.md: incident/time range, deterministic observed alerts and selected telemetry, affected service, timeline, labelled interpretations and evidence references, limitations and provider/model log.
- checkpoint1_execution_log.json and .md: full decisions, tool inputs/results, timestamps, evidence IDs, provider route and stop reason.
- checkpoint1_llm_configuration.md: safe model/settings audit; no credentials or connection details.
- checkpoint1_architecture.svg: one-page inspected services/telemetry/tool/agent/provider/output flow. Optional providers/audit feeds require operator configuration; later action/approval/recovery components are explicitly proposed.

Full evidence JSON files and detection poll records live beside eyes.sqlite. The report uses internal schemas only; no organiser report schema has been supplied/validated here. Limitations and incomplete investigations are exported rather than represented as success. Evidence text can contain Markdown; review it as untrusted content before external sharing. No generated issue/PR comments are posted.

## Offline validation and remaining live acceptance

~~~sh
python3 -B -m incident_tools.eyes.static_check --output-dir artifacts/eyes/check-new
~~~

Use a NEW output directory. This performs Python AST checks, synthetic offline behavior/contract tests including F02, XML validation of the one-page SVG, and SHA-256 comparison of the 692 pre-existing tracked files captured before this work. It creates a permanently labelled fixture end-to-end run for review. It never starts containers, injects faults or calls a real model. Cross-platform checkout line-ending conversion can change raw hashes; the preservation baseline is for this workspace.

Live acceptance is still required: select a compliant practice fault with a known reset procedure (earlier faultctl review found reset/safety issues), run normal watch, observe one sustained real breach creating one incident, inspect at least two evidence-dependent model tool decisions, verify claims against saved telemetry, and retain the generated report/SVG. Do not provide the fault name/flag state to the investigator. No incident injection is implemented or executed by this package. The static fixture report is not a practice-incident demonstration or completed Checkpoint 1. F04/F05 diagnosis/confidence and F06–F09 action/approval/recovery remain later work.
