# ONCALL_SPEC — Build an AI On-Call Engineer on the OpenTelemetry Demo

> **How to use this file:** save it in the repo root as `ONCALL_SPEC.md`, then tell Anti Gravity:
> *"Read ONCALL_SPEC.md fully. Implement it phase by phase (Section 12). After each phase run the verification commands, fix failures, and only then move on. Ask me before deviating from any rule in Section 2."*

---

## 1. Mission

Build an **AI On-Call Engineer** for this repo (a fork of `open-telemetry/opentelemetry-demo`, "Astronomy Shop", running via Docker Compose). When production degrades, the agent must, **fully automatically after an alert**:

1. **Detect** the incident from telemetry thresholds.
2. **Investigate** with real tools (traces, metrics, logs, container health, deployment history), choosing the next tool based on what it has found so far.
3. **Diagnose**: name the failing component and cause, with a confidence level and exact evidence (trace IDs, log lines, metric values) that really exists in the data.
4. **Propose** a fix chosen only from an allowlisted runbook, with a short reason.
5. **Ask a human for approval.** Nothing changes without an explicit yes. Provide dry-run mode and a kill switch.
6. **Act and verify** via the Action API, confirm recovery from health metrics; if not recovered, roll back and escalate.
7. **Report**: JSON (own schema) + readable Markdown: timeline, root cause, evidence, action taken, what would prevent a repeat.

Stretch goals to implement: **(A) Incident memory** and **(B) Prevention**.

**A good agent is not one that always acts.** When evidence is weak it must say "I am not sure, here is what I found" and escalate to a human. A correct escalation scores better than a confident wrong fix.

This is a solo hackathon project. Ignore any notion of teams, checkpoints or timelines. The final evaluation runs **unseen incidents, including infrastructure faults and combinations of faults**, so the agent must reason from telemetry, never from knowledge of which fault was injected.

---

## 2. HARD RULES (never violate; ask the human before deviating)

1. **No reading feature-flag state to find the answer.** The agent's tools must NOT read `src/flagd/demo.flagd.json`, call flagd/flagd-ui `read` endpoints, query the flagd OFREP/gRPC API, or use `feature_flag.*` span attributes/events or flagd service logs as evidence. Diagnosis comes from traces, metrics, logs, container health and deployment history only. Document this in the README.
2. **The LLM never changes the system.** The LLM's tool list is read-only. Only the executor code, after a human approval, calls the Action API.
3. **Action API is the only write path.** No code path in `oncall-agent` may mutate Docker, flags, or the load generator directly. Every action call is logged.
4. **Nothing changes without an explicit human yes.** No auto-approve in production mode. The only exception is `EVAL_AUTO_APPROVE=true`, allowed solely for the local evaluation harness, loudly logged and stamped into the report.
5. **Evidence must exist.** Every evidence item in a diagnosis must be traceable to a stored tool result. Invented evidence is rejected by the validator (Section 7.4).
6. **Do not modify upstream files** except `compose.extras.yaml` (the fork's designated seam) and `.gitignore` (append only). Do not edit `.env` or `.env.override` (put defaults in compose with `${VAR:-default}` and ship `.env.oncall.example`). Do not edit existing services under `src/`.
   `src/flagd/demo.flagd.json` is modified at runtime by fault injection and remediation. It must never be committed in a modified state: `faultctl.py reset` must restore it to the committed content (`git checkout -- src/flagd/demo.flagd.json` semantics or a stored pristine copy).
7. **Do not enable or modify the built-in demo `agent`/`mcp`/`chatbot` services** (`compose.agent.yaml`). They are the Astronomy Shop assistant and unrelated.
8. **Never open a PR or post anything to upstream `open-telemetry/*` repos.** Work stays in the fork.
9. **Never fabricate results.** Evaluation notes and sample reports must come from real runs.
10. Follow `AGENTS.md`: comments only when essential (regexes, linked workarounds); commit trailers use `Assisted-by: <tool>`, **never** `Co-authored-by:`.

---

## 3. Verified facts about this repo (do not re-guess; re-verify with the stated command if anything fails)

| Fact | Detail |
|---|---|
| Repo | Demo v3.1.0, Compose files: `compose.yaml` (core), `compose.full.yaml` (+Kafka, accounting, fraud-detection), `compose.observability.yaml` (+Jaeger, Prometheus, OpenSearch, Grafana, OpAMP), `compose.extras.yaml` (empty, loaded last: **our seam**) |
| Start command | `make start` = compose with `compose.yaml + full + observability + extras`, env files `--env-file .env --env-file .env.override` |
| Network | Compose network named `opentelemetry-demo`. Containers have `container_name` equal to the service name (e.g. `payment`, `cart`, `valkey-cart`, `astronomy-db`) |
| Host ports | Only **8080** (Envoy frontend-proxy), **10000** (Envoy admin) and **9090** (Prometheus) are fixed host ports. Other services publish random host ports, so **our services must run inside the compose network** and use service DNS names |
| Envoy routes | `localhost:8080/jaeger/ui`, `/grafana/`, `/loadgen/` (Locust), `/feature` (flagd-ui), `/chatbot/` |
| Prometheus | `http://prometheus:9090`. Telemetry arrives via OTLP (`/api/v1/otlp`). **Scrape/export interval is ~60s**, so metrics lag. Use rate windows of at least 2m and allow 60-90s after an action before judging recovery |
| Span metrics (confirmed in Grafana dashboards) | `traces_span_metrics_calls_total{service_name, span_name, status_code}` (errors: `status_code="STATUS_CODE_ERROR"`), `traces_span_metrics_duration_milliseconds_{bucket,count,sum}` |
| Container metrics | Collector `docker_stats` receiver. Names after OTLP→Prometheus conversion are NOT verified: discover with `curl -s prometheus:9090/api/v1/label/__name__/values` and filter for `container` |
| Jaeger v2 | `http://jaeger:16686`, base path `/jaeger/ui`, so the API is expected at `http://jaeger:16686/jaeger/ui/api/services`, `/jaeger/ui/api/traces?service=...`. In-memory storage, so traces are lost on restart. **Verify with curl** |
| Logs | Collector → OpenSearch index `otel-logs-YYYY-MM-DD`, no security plugin, `http://opensearch:9200`. Grafana queries use `eventName` and `attributes.*`. **Field names for service/severity/body are not verified: fetch one document first and adapt** (`docker exec opensearch curl -s localhost:9200/otel-logs-*/_search?size=1`) |
| Flag write path | flagd-ui exposes `GET /api/read-file` and `POST /api/write-to-file` with body `{"data": <entire flags json>}` (writes **replace the whole file**), at `http://flagd-ui:4000`. **Only the Action API may use these**, and it must never return flag values to the agent |
| Load generator | Locust web UI at `http://load-generator:8089` (`POST /swarm` with `user_count`, `spawn_rate`; `GET /stats/requests`). Default `LOCUST_USERS=5` |
| Services | ad (Java), cart (.NET), checkout (Go), currency (C++), email (Ruby), frontend (Next.js), frontend-proxy (Envoy), image-provider (nginx), payment (Node), product-catalog (Go, uses `astronomy-db` Postgres), quote (PHP), recommendation (Java), shipping (Rust), accounting (.NET), fraud-detection (Kotlin), kafka, valkey-cart, flagd, flagd-ui, load-generator |
| Built-in failure flags (for **test injection only**) | `paymentFailure`, `paymentUnreachable`, `cartFailure`, `productCatalogFailure`, `productCatalogLockContention`, `recommendationCacheFailure` (runaway cache, memory leak), `adFailure`, `adHighCpu`, `adManualGc`, `emailMemoryLeak`, `loadGeneratorFloodHomepage`, `kafkaQueueProblems`, `kafkaConsumerDead`, `imageSlowLoad`, `intlShippingSlowdown`, `failedReadinessProbe`. Names already used for env vars: `LLM_BASE_URL`, `LLM_MODEL`, `API_KEY`, `AGENT_*`, `MCP_*` are taken by the built-in agent, so **use the `ONCALL_` prefix for everything of ours** |

---

## 4. Architecture

```
                      ┌────────────────────────── opentelemetry-demo network ──────────────────────────┐
 Locust load ──► demo services ──OTLP──► otel-collector ──► Jaeger (traces) / Prometheus (metrics) / OpenSearch (logs)
                                                                   ▲            ▲                ▲
                                                                   │ read-only  │                │
   ┌───────────────────── oncall-agent (FastAPI, :8200) ───────────┴────────────┴────────────────┘
   │  Detector → Investigator(LLM tool loop) → Validator → Proposer → Approval Gate(UI/API) → Executor/Verifier → Reporter
   │         ▲ memory(SQLite)                                                    │ (HMAC approval token)         └► Prevention
   └──────────────────────────────────────────────────────────────────────────┬──┘
                                                                              ▼
                                      action-api (FastAPI, :8201)  ← only component with docker.sock
                                      allowlist · dry-run · kill switch · audit log · read-only inspector
                                              │            │               │
                                       docker restart   flag write    Locust /swarm
   LLM: Ollama on the HOST (http://host.docker.internal:11434/v1) via OpenAI-compatible API
```

Why `docker.sock` is only in `action-api`: a read-only mount of the socket still allows write calls to the Docker API, so the agent container must not have it. The agent reads container health through `action-api`'s read-only inspector endpoints.

### Directory layout to create

```
src/oncall-agent/
  Dockerfile  requirements.txt  README.md
  app/
    main.py            # FastAPI app, startup (detector loop), routes
    config.py          # env-driven settings (ONCALL_* vars)
    detector.py        # threshold detection + dedup/cooldown
    llm.py             # OpenAI-compatible client, tool-call loop, JSON-fallback mode
    tools/             # read-only tools exposed to the LLM
      registry.py  prometheus.py  jaeger.py  logs.py  containers.py  deployments.py  memory.py
    investigator.py    # system prompt, bounded loop, evidence ledger
    evidence.py        # ledger + validator
    diagnosis.py       # schema, confidence calibration
    runbook.py  runbook.yaml
    proposer.py
    approval.py        # state machine, HMAC token issuing
    executor.py        # calls Action API, verification, rollback
    reporter.py        # JSON + Markdown reports
    memory.py          # incident memory (stretch A)
    prevention.py      # stretch B
    schemas/incident_report.schema.json
    static/index.html  # approval dashboard (single page, no build step)
  tests/
src/action-api/
  Dockerfile  requirements.txt  README.md  app/main.py  app/allowlist.py  app/docker_ops.py  app/flags.py  app/audit.py
tools/
  faultctl.py          # OUR test-only fault injector (flags + infra faults + reset)
  run_eval.py          # runs the incident matrix, produces docs/EVALUATION.md data
docs/ARCHITECTURE.md  docs/EVALUATION.md  docs/DESIGN_DECISIONS.md
deliverables/incident-reports/   # curated real reports (committed)
oncall-data/                     # runtime volume (gitignored): reports, memory.sqlite, audit.jsonl
.env.oncall.example
```

Add to `.gitignore` (append): `oncall-data/`, `__pycache__/`, `.venv/`.

---

## 5. Configuration (all with defaults in `compose.extras.yaml`)

| Variable | Default | Purpose |
|---|---|---|
| `ONCALL_LLM_BASE_URL` | `http://host.docker.internal:11434/v1` | Ollama OpenAI-compatible endpoint |
| `ONCALL_LLM_MODEL` | `qwen2.5:7b-instruct` | exact name from `ollama list` |
| `ONCALL_LLM_API_KEY` | `ollama` | dummy for Ollama |
| `ONCALL_LLM_NUM_CTX` | `8192` | pass via `extra_body={"options":{"num_ctx":...}}` (Ollama) |
| `ONCALL_LLM_TIMEOUT_S` | `180` | per call |
| `ONCALL_MAX_STEPS` | `12` | tool calls per investigation round |
| `ONCALL_MAX_ROUNDS` | `3` | investigate→fix→verify rounds (handles combined faults) |
| `ONCALL_CONFIDENCE_THRESHOLD` | `0.70` | below this, escalate instead of propose |
| `ONCALL_POLL_INTERVAL_S` | `30` | detector loop |
| `ONCALL_SETTLE_S` | `120` | wait after action before verifying (metrics lag) |
| `ONCALL_APPROVAL_TTL_S` | `900` | approval token lifetime |
| `ACTION_API_SECRET` | `change-me-locally` | HMAC key shared by the two services |
| `ONCALL_DRY_RUN_DEFAULT` | `true` | executor does a dry run first and shows it in the UI |
| `EVAL_AUTO_APPROVE` | `false` | evaluation harness only |

The compose file must add `extra_hosts: ["host.docker.internal:host-gateway"]` to `oncall-agent` so Ollama is reachable on macOS, Windows and Linux.

Compose services (`compose.extras.yaml`): `action-api` (mounts `/var/run/docker.sock`, `./oncall-data/action-api:/data`, publishes `8201:8201`) and `oncall-agent` (mounts `./oncall-data/agent:/data`, publishes `8200:8200`, `depends_on` prometheus, jaeger, opensearch, action-api). Set memory limits (agent 400M, action-api 150M) and `logging` like other services. Do not touch other services' definitions.

---

## 6. Action API (`src/action-api`) — the only write path

**Read-only inspector (used by agent tools):**
- `GET /containers`: all containers in the compose project: name, state, `Status`, health, `RestartCount`, `OOMKilled`, exit code, `StartedAt`, image id/created, CPU% and memory usage/limit snapshot.
- `GET /containers/{name}`: one container, same fields.
- `GET /events?since_minutes=N`: ring buffer of Docker events (`start`, `die`, `oom`, `restart`, `kill`, `stop`) collected by a background watcher, plus every action this API performed. This is the **deployment/change history** source.

Also: `GET /health` (liveness) and `GET /audit?limit=N` (tail of the audit log). `oncall-agent` also exposes `GET /health`.

**Mutating actions** (`POST /actions`, body `{action, params, incident_id, approval_token, dry_run}`):

| action | params | Behaviour |
|---|---|---|
| `restart_service` | `service` ∈ allowlist | `docker restart`. Allowlist: ad, cart, checkout, currency, email, frontend, image-provider, payment, product-catalog, quote, recommendation, shipping, accounting, fraud-detection, kafka, valkey-cart, astronomy-db. **Never** otel-collector, prometheus, jaeger, opensearch, flagd, flagd-ui, action-api, oncall-agent |
| `set_feature_flag` | `flag` ∈ runbook flag list, `variant` = that flag's off/default variant only | Read-modify-write the whole flags JSON through flagd-ui. Store the **previous** value in the audit log for rollback. **Do not return the previous value to the caller** |
| `throttle_load_generator` | `users` (1..current), `spawn_rate` | Locust `/swarm` |
| `scale_service` | any | Return `{"status":"unsupported","reason":"Kubernetes only; this deployment is Docker Compose"}` |
| `rollback` | `action_id` | Restore previous flag variant / previous Locust user count. `restart_service` is reported as not reversible |

Enforcement (all inside Action API, independent of the agent):
- **Kill switch:** `POST /killswitch {engaged:true|false}`, `GET /killswitch`. When engaged, every mutating call returns 423 Locked. Persist state in `/data`.
- **Approval token:** mutating non-dry-run calls require an HMAC-SHA256 token (key `ACTION_API_SECRET`) over `{incident_id, action, params, exp}`. Reject expired, mismatched or missing tokens (403). The token is only ever minted by `oncall-agent` when a human approves in the UI/API.
- **Dry run:** `dry_run:true` validates allowlist and state and returns what *would* happen (e.g. "would restart payment, currently running, uptime 14m"). No token needed. Must not change anything or leak flag values.
- **Audit log:** every call (including rejected) appended to `/data/audit.jsonl` with timestamp, incident, action, params, mode, result, caller.
- Rate limit: max 1 mutating action per service per 60 s.

---

## 7. Agent design (`src/oncall-agent`)

### 7.1 Detector (step 1)
Every `ONCALL_POLL_INTERVAL_S`, evaluate and emit an **Alert** containing symptoms only (never a cause):
- Per-service error ratio over 5m from span metrics. Trigger when > 5% for 2 consecutive polls and ≥ N requests.
- Per-service p95 latency > max(1s, 2× its trailing 30-minute baseline).
- Container state from the inspector: not running, restarts ≥ 3 in 5 min, `OOMKilled`, memory > 90% of limit and rising, CPU at its limit for 3 polls.
- Frontend-level symptom (error ratio / latency at `frontend` or `frontend-proxy`).

Dedup: one open incident per fingerprint (sorted anomalous services + symptom types); cooldown after resolution (5 min). Also expose `POST /incidents/investigate` for manual start (used by the eval harness). **Negative control:** a healthy system must not produce alerts.

### 7.2 Investigator (steps 2–3)
Bounded tool-calling loop (`ONCALL_MAX_STEPS`). Use the `openai` Python client against Ollama. Implement **native tool calling** and a **JSON-ReAct fallback** (model replies with `{"tool":..., "args":...}`) for models that lack tool support; select via a startup probe. Keep tool outputs **compact** (≤ ~2000 chars each, ranked, deduped) so a 7-8B model can reason; never paste whole datasets into the prompt.

System prompt (SRE method): start from the symptom → rank suspect services → follow failing traces to the **deepest failing dependency** (the leaf error span, not the caller that merely propagates it) → read that service's error logs → check container health/restarts/OOM → check recent changes → write competing hypotheses and try to refute them → only then submit a diagnosis. Instruct: "If evidence is insufficient, submit a diagnosis with low confidence and category `unknown` rather than guessing."

**Read-only tools exposed to the LLM** (JSON-schema function definitions):

| Tool | Source | Returns |
|---|---|---|
| `get_health_overview(lookback_min)` | Prometheus span metrics | table ranked by anomaly: service, req rate, error %, p95 ms, vs baseline |
| `query_prometheus(promql, lookback_min)` | Prometheus | truncated series summary (min/max/last/slope) |
| `search_traces(service, error_only, min_duration_ms, lookback_min, limit)` | Jaeger API | compact list: trace_id, root op, duration, error span service/op/status message |
| `get_trace(trace_id)` | Jaeger API | compact span tree with status, durations, error/exception/rpc/http/db attributes. **Strip `feature_flag.*`** |
| `search_logs(service, severity, text, lookback_min, limit)` | OpenSearch | deduped log lines with count, first/last seen, trace_id |
| `get_container_health(service?)` | Action API inspector | state, restarts, OOM, exit code, CPU/mem vs limit |
| `get_recent_changes(lookback_min)` | Action API `/events` | container starts/stops/restarts and actions taken |
| `search_incident_memory(symptom_summary)` | local SQLite | similar past incidents + outcome (stretch A) |
| `submit_diagnosis(...)` | terminal tool | structured diagnosis (schema below) |

No tool may reveal flag state (rule 1).

### 7.3 Evidence ledger
Every tool result is stored raw in `/data/incidents/<id>/evidence.jsonl` and assigned an ID (`E1`, `E2`, ...), each with type (`metric|trace|log|container|change|memory`), timestamp and a compact rendering. The LLM cites IDs plus the specific value/line/trace_id.

### 7.4 Diagnosis + validator + calibrated confidence
`submit_diagnosis` schema: `{component, cause_category, cause_description, confidence (0..1), evidence:[{evidence_id, type, ref (trace_id | log line | metric+value), why_it_matters}], alternatives_considered:[...], recommended_runbook_ids:[...]}` with `cause_category` ∈ `service_fault_injected_errors | dependency_unavailable | container_down_or_crashloop | resource_exhaustion_memory | resource_exhaustion_cpu | traffic_overload | latency_degradation | data_store_unavailable | unknown`.

**Validator (deterministic code):**
1. Every cited `evidence_id` exists.
2. Every `ref` (trace id, quoted log fragment, metric value ±5%) actually appears in the stored raw evidence for that ID. Failures count as *invented evidence*.
3. On failure: send the specific failures back to the model for **one** repair attempt; if still failing, drop the invalid items.
4. **Calibrated confidence** = `min(model_confidence, evidence_score)` where `evidence_score` combines: share of valid evidence, number of independent evidence types corroborating (trace + log + metric/container), whether a single root-cause component is identified, and a penalty for unrefuted alternatives. Record both values in the report.
5. `confidence < ONCALL_CONFIDENCE_THRESHOLD` or category `unknown` → **escalate** (state ESCALATED) with findings; no fix is proposed.

### 7.5 Runbook + Proposer (step 4)
`runbook.yaml` is the allowlist: each entry has `id`, `applies_to` (cause_category + component hints), `action` (one of the Action API actions), `params`, `risk` (low/med), `reason_template`, `expected_recovery_signal`. Seed it from the failure classes below. Example mapping (symptom-derived, not read from flags):

| Diagnosed situation | Runbook action |
|---|---|
| payment charge errors / payment unreachable | `set_feature_flag paymentFailure/paymentUnreachable → off`, else `restart_service payment` |
| cart intermittent errors | `set_feature_flag cartFailure → off`, else `restart_service cart` |
| product-catalog failing for one product | `set_feature_flag productCatalogFailure → off` |
| recommendation memory growth / OOM restarts | `set_feature_flag recommendationCacheFailure → off` then `restart_service recommendation` |
| ad high CPU / GC pressure | `set_feature_flag adHighCpu/adManualGc → off` |
| email memory growth | `set_feature_flag emailMemoryLeak → off`, `restart_service email` |
| homepage traffic flood | `throttle_load_generator` (+ `set_feature_flag loadGeneratorFloodHomepage → off`) |
| container stopped / crash-looping | `restart_service <svc>` |
| cache or DB down | `restart_service valkey-cart` / `astronomy-db` |
| starved CPU/memory with no fault signature | `restart_service` is **not** a fix, so escalate with findings |

The proposer asks the LLM to choose **only among runbook entries that match the diagnosis**, outputs `{runbook_id, params, reason, expected_recovery_signal, rollback_plan}`, and the code rejects anything not in the runbook. Prefer least-invasive first (flag-off/throttle before restart). The proposal is a *plan* (possibly several ordered actions for combined faults).

### 7.6 Approval gate (step 5)
State machine: `DETECTED → INVESTIGATING → DIAGNOSED → AWAITING_APPROVAL → APPROVED | REJECTED → EXECUTING → VERIFYING → RESOLVED | ROLLED_BACK | ESCALATED`.
- `static/index.html`: incident list, live status, diagnosis + confidence + evidence table (links to Jaeger trace URLs on `localhost:8080/jaeger/ui/trace/<id>`), the proposed plan, **Dry-run**, **Approve**, **Reject**, and a global **Kill switch** toggle (calls Action API). Poll `GET /incidents` every 2s; no build step, no external CDN.
- API: `POST /incidents/{id}/dry-run`, `/approve`, `/reject`, `GET /incidents`, `GET /incidents/{id}`, `POST /killswitch`.
- On approve, mint the HMAC token bound to the exact plan. **No auto-approve and no timeout-approve**; pending incidents stay pending (report shows `approval: pending`).

### 7.7 Act & verify (step 6)
Execute each approved action via Action API (optionally dry-run first). Wait `ONCALL_SETTLE_S`, then verify with **fresh telemetry**: error ratio < 2%, p95 within 1.3× baseline, container running and stable, and no new error traces in the last minute (Jaeger responds faster than Prometheus). If recovered → `RESOLVED`. If not → `rollback` reversible actions, mark `ROLLED_BACK`, and escalate. For multi-fault situations, re-run detection and investigation for the remaining symptoms, up to `ONCALL_MAX_ROUNDS`, each round needing its own approval.

### 7.8 Reporter (step 7)
Write `/data/reports/INC-<id>.json` (validated against `schemas/incident_report.schema.json`, draft 2020-12) and `INC-<id>.md`. Fields: `schema_version, incident_id, status (resolved|escalated|rejected|rolled_back|pending_approval), detected_at, resolved_at, timeline[{ts, event, detail}], symptoms, root_cause{component, category, description, confidence{model, evidence_score, final}}, evidence[{id, type, ref, why}], alternatives_considered, actions[{runbook_id, action, params, dry_run_result, approved_by, approved_at, result}], verification{passed, before, after}, escalation{reason, findings}, prevention[], memory_assist{matched_incident, similarity, steps_saved}, model{name, base_url_host}, auto_approve_used`. Add a validator test that every produced report passes the schema.

---

## 8. Stretch A — Incident memory
- SQLite at `/data/memory.sqlite`: for each closed incident store fingerprint (services, symptom types, category, component), diagnosis summary, runbook used, **outcome** (`fixed` | `not_fixed` | `escalated`), and a text blob.
- Retrieval: fingerprint match first, then lexical similarity (TF-IDF/BM25 implemented with the standard library or `scikit-learn`; no extra model required). Optional upgrade: Ollama embeddings (`nomic-embed-text`) behind a flag.
- `search_incident_memory` returns top-3 with similarity and what worked/failed.
- **Memory is a hint, not evidence.** It may reorder hypotheses and shorten the investigation ("check hypothesis X first"), but the diagnosis must still cite live evidence; the validator ignores `memory` evidence for confidence. Fixes that previously failed are deprioritized.
- Record `memory_assist` in the report, including the number of tool calls used vs the earlier occurrence.
- Add `POST /memory/reindex` and a script option to run the same incident twice to demonstrate faster repeat diagnosis.

## 9. Stretch B — Prevention
After resolution (and also after escalation when a root cause is known), generate concrete, **non-applied** suggestions into the report and `/data/prevention/INC-<id>.md`:
- type `alerting`: a ready Prometheus alert rule YAML for the observed signal (e.g. error ratio on the component). **Validate the PromQL by running it against Prometheus** (`/api/v1/query`) and record the validation result.
- type `config`: e.g. resource limit / healthcheck / restart policy / retry-timeout change, naming the exact compose key or file.
- type `code`: e.g. circuit breaker, bounded cache with eviction, retry with backoff, input validation, naming the service and function area.
Each item: `{type, target, change, rationale, risk, validated}`. Combine a small deterministic catalog per `cause_category` with LLM tailoring based on the incident's evidence. Never auto-apply.

---

## 10. Test tooling (OUR stand-ins; the agent never imports these)

`tools/faultctl.py` — test-only fault injector:
- `faultctl.py flag <name> <variant>`: injects an app fault by editing flags through flagd-ui (this is injection, not agent behaviour).
- `faultctl.py stop <service>` / `pause <service>` / `starve-cpu <service> <cpus>` / `starve-mem <service> <MB>` (via `docker update`) / `reset` (all flags default, restart stopped containers, restore recorded limits, reset Locust users).
- `faultctl.py list` prints the practice incident catalog.

**Practice incident matrix** (`tools/run_eval.py --all`, each: reset → inject → wait for alert → agent investigates → approve (auto only if `EVAL_AUTO_APPROVE=true`) → verify → score against expected component/category/action):

| # | Injection | Expected component | Expected fix |
|---|---|---|---|
| 1 | `paymentFailure=100%` | payment | flag-off paymentFailure |
| 2 | `cartFailure=50%` | cart | flag-off cartFailure |
| 3 | `productCatalogFailure=on` | product-catalog | flag-off |
| 4 | `recommendationCacheFailure=on` | recommendation | flag-off + restart |
| 5 | `adHighCpu=on` | ad | flag-off |
| 6 | `adManualGc=on` | ad | flag-off |
| 7 | `loadGeneratorFloodHomepage=on` | frontend | throttle load |
| 8 | `docker stop payment` | payment | restart payment |
| 9 | `docker stop valkey-cart` | cart (dependency valkey-cart) | restart valkey-cart |
| 10 | `docker stop astronomy-db` | product-catalog (dependency astronomy-db) | restart astronomy-db |
| 11 | `starve-cpu ad 0.1` | ad | **escalate** (no approved fix) |
| 12 | `emailMemoryLeak=100x` | email | flag-off + restart |
| 13 | combo `cartFailure=50% + adHighCpu=on` | cart + ad | two actions, two rounds |
| 14 | no fault (negative control) | none | **no alert, no action** |
| 15 | `kafkaQueueProblems=3sec` (unlisted) | fraud-detection/kafka | correct diagnosis or **escalate**, never a confident wrong fix |

`run_eval.py` outputs `docs/EVALUATION.md` from real run data: per incident, right/wrong, confidence, number of tool calls, time to diagnosis, time to recovery, why it failed (honest). Include an **honest limitations** section (e.g. network latency/packet loss faults are not injectable without `tc`; Kubernetes scaling unsupported; Prometheus lag of ~60s).

---

## 11. Documentation to produce
- `src/oncall-agent/README.md` and top-level `ONCALL_README.md`: setup, how to run, how the approval gate and kill switch work, the no-flag-reading policy, known limitations.
- `docs/ARCHITECTURE.md`: one page: components, tools the agent uses, how it decides, safety controls (diagram in Mermaid).
- `docs/DESIGN_DECISIONS.md`: why a hand-rolled tool loop (not a heavy framework), why two services, why HMAC approval, why evidence validator, why memory is a hint only.
- `docs/EVALUATION.md` (generated from real runs, see Section 10).
- `deliverables/incident-reports/`: copy real JSON+MD reports from the eval runs (at least one resolved, one escalated, one rejected, one memory-assisted repeat).

---

## 12. Work order (do in order; verify before moving on)

**Phase 0 — Recon (no code).** Start the stack: `make start`. Confirm and write down in `docs/RECON.md`: Jaeger API path, OpenSearch log field names (one sample doc), Prometheus container metric names, flagd-ui read/write payload (**test the write path on a throwaway copy of the flags file first and restore it**), that Ollama is reachable from a container:
`docker run --rm --add-host host.docker.internal:host-gateway curlimages/curl -s http://host.docker.internal:11434/api/tags`.

**Phase 1 — Action API.** Build and test with curl: inspector, dry-run, token rejection, kill switch (423), allowlist rejection, flag set + rollback (verify via audit log only), Locust throttle, restart. Unit tests for token and allowlist logic.

**Phase 2 — Read-only tools.** Implement every tool, test each against the live stack with `curl`/pytest; confirm compact output size and that `feature_flag.*` is stripped from traces.

**Phase 3 — Detector + Investigator + evidence ledger + validator.** Inject incidents #1, #8, #2 using `faultctl`; confirm alert fires without a cause, the agent picks tools adaptively, and a deliberately fabricated citation is rejected by a unit test.

**Phase 4 — Runbook, proposer, approval gate UI, executor/verifier, rollback, reporter + schema.** End-to-end on #1 and #8 with manual approval in the UI. Test reject, kill switch, dry-run, failed verification (simulate by approving a wrong action in a test) → rollback + escalate.

**Phase 5 — Stretch A (memory) and B (prevention).** Run #1 twice; show the second run uses fewer tool calls and `memory_assist` in the report. Validate generated alert rules against Prometheus.

**Phase 6 — Evaluation + docs.** Run the whole matrix, generate `docs/EVALUATION.md`, copy curated reports into `deliverables/`, write README/architecture/design docs. Fix weaknesses found (especially false confident diagnoses → tune calibration).

**Phase 7 — Clean-room test.** `docker compose down -v`, rebuild from scratch, run `make start`, run one incident end-to-end from a cold start. Report the exact commands used.

**Definition of done:** every Section 1 step works end-to-end on at least incidents #1, #8, #13 and #14; escalation works on #11; rules in Section 2 hold (grep proves no flag-reading code path in `oncall-agent`); fresh clone starts with `make start`; documents exist.

When something is ambiguous, prefer the safer behaviour (escalate, dry-run, refuse) and note the assumption in `docs/DESIGN_DECISIONS.md`.
