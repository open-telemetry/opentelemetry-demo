# Eyes acceptance runner

This additive package connects the existing F01 detector, F02 read tools and one F03 diagnostic investigator into a reproducible practice workflow. Existing application sources, configuration, dependencies, faultctl and Eyes/F02 implementations are unchanged. No Docker builds are involved.

## What this implements

1. Operator-owned configuration with stable filenames, OpenAI environment-key provision, provider validation and optional connectivity probe.
2. Read-only F02 readiness checks for current metrics, logs, traces, health and available deployment history.
3. A fresh incident store and a baseline gate: two qualified normal metric observations after warmup, sufficient traffic and fresh source samples.
4. An explicitly authorized, bounded pause of the existing shipping container. Container identity, Compose project and service labels are checked. A separate reset watchdog must be ready before pausing. This is an operator practice control, never an agent tool.
5. Existing deterministic F01 thresholds create an incident without a supplied cause. Two further breach polls check deduplication.
6. Reset is attempted and verified before inference. The existing F03 investigator chooses read tools; subsequent choices must cite specific observations already returned to it. Its input is the detected incident, F02 schemas and telemetry, never the operator injection journal.
7. Evidence, model identity, symptom report, architecture SVG and an acceptance assessment are saved.

Pausing shipping is a dependency-unavailability practice case. It may produce checkout latency/timeouts, depending on traffic and service timeouts. A breach is not guaranteed. The runner fails honestly if the baseline is already unhealthy, telemetry is insufficient, or no sustained breach occurs. It never fabricates an alert or lowers a threshold automatically.

This implements Eyes orchestration, not remediation features F07/F09, diagnosis/ranking, or proof of root cause. Reset checks running/unpaused container state; it does not prove application recovery. The live demonstration remains pending until run against real telemetry and a real model.

## Set up in Ubuntu WSL

Run from the repository root with Python 3.11+ and the existing native Ubuntu Docker engine. Keep the demo and load generator running. Do not run another practice injector or Eyes watcher concurrently.

Inspect the actual bindings and project:

```bash
docker port prometheus
docker port frontend-proxy
docker port opensearch
docker inspect checkout --format '{{index .Config.Labels "com.docker.compose.project"}}'
```

Create one new operator directory. Replace the endpoint ports below with the host ports printed above; Jaeger uses the frontend-proxy endpoint for this repository's v3 API. These are examples, not assertions about your laptop:

```bash
python3 -B -m incident_tools.eyes_acceptance init \
  --directory /tmp/eyes-operator \
  --project opentelemetry-demo \
  --prometheus http://localhost:9090 \
  --jaeger http://localhost:8080 \
  --opensearch http://localhost:YOUR_OPENSEARCH_HOST_PORT
```

Edit `/tmp/eyes-operator/f02.toml` for your working endpoints/project. The generated Eyes configuration selects OpenAI's `gpt-4.1-mini`; check that your API project can access it. Initialization refuses to overwrite an existing directory; reuse and edit the same files.

The generated defaults monitor checkout latency p95 above 1000 ms, require two fresh breaches and at least approximately 10 requests over the metric's two-minute rate window. Warmup is 120 seconds. Validate that these thresholds suit your healthy baseline. Investigations use up to eight read calls, one returned item per call and a 120-second investigation budget.

### OpenAI key provision

The `init` command selects `https://api.openai.com/v1`, `gpt-4.1-mini` and `api_key_env = "OPENAI_API_KEY"` by default. The model is supported by the existing Chat Completions transport; no SDK dependency is added. See the [official OpenAI model documentation](https://developers.openai.com/api/docs/models/gpt-4.1-mini) and [API authentication guidance](https://developers.openai.com/api/reference/overview).

To reuse an existing `/tmp/eyes-operator/eyes.toml`, change only these three values under `[models.cloud]`:

```toml
endpoint = "https://api.openai.com/v1"
model = "gpt-4.1-mini"
api_key_env = "OPENAI_API_KEY"
```

In the same Ubuntu shell where you run Eyes, enter the key without displaying or writing it to a file:

```bash
printf 'OpenAI API key: '
read -rs OPENAI_API_KEY
printf '\n'
export OPENAI_API_KEY
```

Check configuration without inference using `python3 -B -m incident_tools.eyes_acceptance preflight --config /tmp/eyes-operator/eyes.toml`. Then explicitly run `python3 -B -m incident_tools.eyes_acceptance.diagnose --config /tmp/eyes-operator/eyes.toml` for one model request, followed by `preflight --live --probe-model` when ready to query telemetry as well. Do not run the practice command until these checks pass. The diagnostic and probe may incur API usage. Existing operator files are never rewritten by `init`.

Cloud settings include timeout, retries, requests per minute, input context character budget, maximum output tokens and temperature. The context character budget is an application bound, not the provider's token context size.

New operator configurations use a 60-second per-request timeout. Existing operator files are never rewritten; update timeout_seconds under [models.cloud] to 60 if they still contain 30.

The model probe derives its request budget from every selected provider's timeout, retry count and retry rate-limit waits, plus five seconds of scheduling headroom. For cloud-only with timeout_seconds = 60, retries = 1 and requests_per_minute = 12, model_probe_budget_seconds is 130. Diagnostics disable retries and therefore use 65 seconds for one 60-second attempt. Socket timeouts are I/O inactivity limits; these budgets are not an operating-system wall-clock watchdog. The investigation's workflow.max_seconds remains a separate setting.

Existing local Ollama configuration and local-only, cloud-only, local-first and cloud-first routes remain supported through the unchanged Router. Configure only installed/available providers. Both providers selected for a fallback route must pass configuration validation; missing cloud credentials are not silently bypassed. Refer to [existing Eyes configuration](../eyes/operator.example.toml). No local backend is installed by this package.

### Readiness, without injection

Offline validation (no network, Docker command or inference):

```bash
python3 -B -m incident_tools.eyes_acceptance preflight \
  --config /tmp/eyes-operator/eyes.toml
```

Without the key/model, expect `MISSING_CLOUD_ENVIRONMENT_KEY` and/or `SET_CLOUD_MODEL_ID`, exit 2. This is expected and does not block static checks.

Read-only telemetry probes, still no injection:

```bash
python3 -B -m incident_tools.eyes_acceptance preflight \
  --config /tmp/eyes-operator/eyes.toml --live
```

Once the key is available, explicitly test inference:

```bash
python3 -B -m incident_tools.eyes_acceptance preflight \
  --config /tmp/eyes-operator/eyes.toml --live --probe-model
```

Logs/traces with `partial` status and actual observations are usable with limitations. Empty/error responses block the practice run. Deployment history may remain unavailable and is recorded honestly. A trace limit of one reduces payload size but cannot guarantee a small trace.

## Execute the real practice workflow later

This command intentionally pauses shipping. The operator authorizes that bounded practice action by supplying the explicit flag:

```bash
python3 -B -m incident_tools.eyes_acceptance run \
  --config /tmp/eyes-operator/eyes.toml \
  --execute-practice --duration 240 --baseline-seconds 300
```

A successful provider probe and usable telemetry are required before injection. Each execution creates a new timestamped directory under the configured `artifact_dir`. No previous run is overwritten.

Without a key, a real detector-only rehearsal is available:

```bash
python3 -B -m incident_tools.eyes_acceptance run \
  --config /tmp/eyes-operator/eyes.toml \
  --execute-practice --detect-only
```

This still performs a real pause/reset and detector run. It never calls an LLM or claims F03 completion; exit 2 and failed investigation checks are expected.

The reset watchdog is a separate Python process, not a second diagnostic agent. It initiates unpause at the lease deadline even if the parent exits, and retries failures. Normal failures and Ctrl+C also attempt reset. The journal records failures rather than reporting success. WSL shutdown, host power loss, Docker failure, or killing both processes can prevent reset; after restoring the engine, retry using the exact journal printed in the run directory:

```bash
python3 -B -m incident_tools.eyes_acceptance reset \
  --journal /tmp/eyes-operator/runs/YOUR_RUN/operator/practice.json
```

Reset uses the original full container ID and validates its project/service; it never unpauses a replacement or another service. Do not recreate containers during a run. If an operator lock remains after a hard process termination, first reset using the journal, confirm the recorded PID is no longer running, and only then remove that stale lock.

## Evidence and review

Each run contains:

- `readiness.json`: probe observations and actionable readiness issues.
- `poll-*.json`: ordered baseline, detection and deduplication outcomes.
- `evidence/`: SQLite incident state and immutable evidence JSON, including alert freshness and request coverage.
- `operator/practice.json`: separate injection/reset identity, times and state.
- `report/checkpoint1_incident_report.md`: observed facts, model interpretations and gaps.
- `report/checkpoint1_execution_log.json` and `.md`: decisions, explicit dependencies, tool results and model identity.
- `report/checkpoint1_llm_configuration.md`: public provider/model configuration.
- `report/checkpoint1_architecture.svg`: one-page architecture, with later features labelled proposed.
- `acceptance.json` and `.md`: automatic checks and remaining semantic review.

An automated pass requires one automatically created incident, measured/provenanced alert evidence, repeated breach deduplication, a completed investigation, at least two successful queries with an explicit evidence dependency, cited interpretations, model identity, real backend origin and verified reset. Fixture executions cannot pass live acceptance.

An examiner/operator must still inspect the actual observations and rationale: does the second query follow from the first result, and do the cited observations support each interpretation? Reference validation alone cannot establish semantic correctness. Therefore `live_acceptance_complete` stays false and semantic review stays pending in machine-generated assessments. Record the human review alongside the artifacts. Do not present model interpretations as established root cause.

## Static verification

From the repository root:

```bash
python3 -B -m incident_tools.eyes_acceptance.static_check \
  --baseline artifacts/eyes-acceptance/baseline.json \
  --output-dir artifacts/eyes-acceptance/check-01
```

Use a new output directory if repeating intentionally. This parses Python syntax, runs the existing F02/Eyes suites and new acceptance tests, exports an explicitly synthetic workflow report, validates SVG XML and compares every baseline tracked file's SHA-256. Existing transport tests use loopback fixture HTTP servers and local Python CLI processes. The new suite blocks network and external processes except explicitly mocked boundaries. No live incident, real model call, Docker build or Git commit is performed.

Source baseline belongs to this implementation session. For a future modification session, capture a fresh tracked-file hash baseline before editing; do not overwrite historical verification evidence.
