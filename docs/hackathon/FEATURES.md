# Feature backlog (Incident Zero)

Feature specs F01-F09 (Wave 0 Foundation + Wave 1 Eyes), F11-F17 (Wave 2
Brain) and F18-F19 (faultctl + Action API). The issue board, with NN numbers
and status, is [ISSUES.md](ISSUES.md). Rules: [RULES.md](RULES.md).

Each feature = one ISSUES.md entry = one branch = one PR. Branch:
`<type>/<NN>-<slug>`, NN = the two-digit number from ISSUES.md. The setup work
is F00 (`chore/00-ci-and-workflow-setup`).

=====================================================================
INSTRUCTIONS FOR THE CODING AGENT
---------------------------------
- Features are tracked in docs/hackathon/ISSUES.md. GitHub Issues is disabled
  on the fork.
- When asked to work on a feature: check its "Depends on" are merged into
  main; warn about anything in "Collides with" that is in progress; touch
  ONLY its "Files"; meet every acceptance criterion; run the tests; do one
  real run (live demo or offline fixture); open the PR with the template.
- If anything here disagrees with the real system (metric names, Jaeger
  URLs, log index names, starter-kit APIs), the REAL SYSTEM WINS: verify it,
  use the real value, and note the difference in the PR.

VERIFIED FACTS ABOUT OUR ENVIRONMENT (do not re-derive, but do verify live)
--------------------------------------------------------------------------
- Repo = fork of upstream OTel Demo 3.1.0. Our code lives ONLY in oncall/
  (top-level package). Never edit anything under src/ (demo code).
- Python 3.11 (organiser baseline). Package deps in oncall/requirements.txt,
  pinned. Dev deps in oncall/requirements-dev.txt.
- Demo must run with the observability overlay or logs/metrics only go to
  the collector's debug exporter:
     docker compose -f compose.yaml -f compose.observability.yaml up -d
  (or compose.full.yaml). Images: from the organisers' USB drive if ghcr.io
  is blocked.
- Prometheus: http://127.0.0.1:9090 (stable). VERIFIED LIVE:
  traces_span_metrics_calls_total and
  traces_span_metrics_duration_milliseconds_{bucket,count,sum}; labels
  service_name, span_name, span_kind, status_code (STATUS_CODE_ERROR /
  _OK / _UNSET), plus error_type, error_message, rpc_grpc_status_code,
  http_response_status_code on error series (not seen yet in a healthy
  demo). Metrics arrive via OTLP push: rate() windows must be >= 5m (a 1m
  window returns nothing).
- Jaeger, OpenSearch, Grafana have RANDOM host ports. Resolve with
  discover_endpoints() (Jaeger 16686, OpenSearch 9200). Never hardcode.
- Jaeger API: base path /jaeger/ui, v3 only. VERIFIED LIVE:
  /jaeger/ui/api/v3/services -> 200 (direct port and via
  http://127.0.0.1:8080). /api/services, /api/v3/services and
  /jaeger/ui/api/services -> 404.
- Logs: OpenSearch index pattern otel-logs-* (daily indices, never a fixed
  name). Fields resource.service.name, severity.text, severity.number,
  body, @timestamp, attributes.*. severity.text case varies, so filter on
  severity.number: error >= 17, warn >= 13.
- FLAG DATA IS IN THE TELEMETRY (RULES.md hard rule 7): Prometheus
  feature_flag_evaluation_* metrics with feature_flag_key,
  feature_flag_result_variant, feature_flag_result_reason,
  feature_flag_provider_name labels; span attributes feature_flag.* and
  demo.feature_flag.*; log fields attributes.feature_flag_*. Using any of
  it = reading flag settings = disqualification risk. scrub_flags() (F01)
  removes it from every ToolResult.
- Upstream src/agent is the demo's own LangGraph service; it reads flags.
  We never touch, import or imitate it.
- FORBIDDEN (disqualification): reading flagd files, flag UI, flag API, or
  any flag value to diagnose; hard-coding practice-incident answers into
  agent code or prompts; changing the system outside the Action API.
- BUILT BY OUR TEAM (not provided by organisers): faultctl (F18), Action
  API (F19), offline bundles (F03 recorder + F11 fixtures), template and
  report schema (F16: oncall/report/schema.json IS the schema).

SHARED CONTRACT (created in F01; changes need an interface-change entry)
-----------------------------------------------------------------------
Evidence   = {"id": str, "text": str, "ts": str | None}
  id formats: "metric:<promql>@<iso_ts>"
              "trace:<trace_id>/span:<span_name>"
              "log:<service>@<iso_ts>"
              "container:<name>"
              "deploy:<id>"
ToolResult = {"tool": str, "query": dict, "summary": str,
              "evidence": list[Evidence], "ok": bool, "error": str | None}
  summary <= 1500 chars, evidence <= 20 items, no raw dumps.
  Tools NEVER raise to the caller: on failure return ok=False + error.
Alert      = {"id": str, "ts": str, "service": str | None,
              "signal": "error_rate" | "latency" | "container" | "manual",
              "value": float | None, "threshold": float | None,
              "description": str, "source": "detector" | "manual"}


=====================================================================
F01  Package skeleton, contracts, config, tool registry
=====================================================================
Module: brain (agent)    Priority: P0    Checkpoint: CP1    Size: S
Goal: everyone can start coding against stable types and a registry
within 30 minutes. MERGE THIS FIRST.

Files:
  oncall/__init__.py
  oncall/models.py              TypedDicts: Evidence, ToolResult, Alert
                                + helpers make_result(), make_error()
  oncall/config.py              Settings loaded from env / .env (pydantic-
                                settings or plain os.environ + dataclass)
  oncall/endpoints.py           discover_endpoints()
  oncall/tools/__init__.py      TOOLS dict + "# --- tool imports ---"
                                section (empty; F04-F08 append one line each)
  oncall/tools/registry.py      @register_tool decorator
  oncall/requirements.txt, oncall/requirements-dev.txt
  oncall/.env.example           (the root .env is upstream demo config; never edit it)
  oncall/tests/test_models.py, oncall/tests/test_registry.py,
  oncall/tests/test_endpoints.py
  .github/workflows/oncall-ci.yml  rules job: fail on /feature[_.]flag/i in
                                oncall/ outside oncall/safety/, allowlisting
                                only oncall/models.py and
                                oncall/tests/test_models.py

Interfaces:
  def make_result(tool: str, query: dict, summary: str,
                  evidence: list[Evidence]) -> ToolResult
  def make_error(tool: str, query: dict, error: str) -> ToolResult
  def register_tool(name: str, description: str, params: dict)
      # params = JSON-schema "properties"+"required" for the LLM.
      # Registers fn in TOOLS[name] and its schema in TOOL_SCHEMAS[name].
      # Wraps fn so any exception becomes make_error(...).
      # Applies scrub_flags() to every ToolResult before returning it.
  def scrub_flags(obj: object) -> object
      # Recursively removes any dict key matching /feature[_.]flag/i, drops
      # OTLP/Jaeger attribute items {"key": <match>, "value": ...}, and
      # replaces any line of a string that matches it (label name and
      # value) with "[feature-flag data removed]" (RULES.md hard rule 7).
      # Lives in oncall/models.py.
  def discover_endpoints() -> dict[str, str]
      # Returns {"prometheus":..., "jaeger":..., "opensearch":...}.
      # Order: env var if set -> `docker compose port` -> None.
      # Never raises; missing ones are None + a warning.

Config keys (declare ALL now so nobody else edits config.py):
  PROM_URL, JAEGER_URL, OPENSEARCH_URL, OPENSEARCH_LOG_INDEX,
  COMPOSE_FILES (default "compose.yaml,compose.observability.yaml"),
  TELEMETRY_BACKEND (live|offline), OFFLINE_DIR,
  LLM_PROVIDER, LLM_MODEL, LLM_API_KEY, LLM_BASE_URL, LLM_MAX_TOKENS,
  MAX_STEPS (12), CONFIDENCE_MIN (0.7), RUNS_DIR ("runs"),
  ACTION_API_URL, DRY_RUN (true), KILL_SWITCH_FILE (".killswitch"),
  VERIFY_WINDOW_S (120), ALERT_ERROR_RATE (0.05), ALERT_P95_MS (1000),
  ALERT_POLL_S (15)

Acceptance:
  [ ] `python -c "import oncall, oncall.models, oncall.config, oncall.tools"`
  [ ] A test registers a dummy tool; it appears in TOOLS and TOOL_SCHEMAS
      with a valid schema; an exception inside it returns ok=False.
  [ ] A test: a ToolResult containing feature_flag_key in evidence text and
      in nested dicts comes back scrubbed.
  [ ] CI rules job fails on /feature[_.]flag/i outside oncall/safety/ and
      the two allowlisted files.
  [ ] discover_endpoints() returns a dict without raising when Docker is
      not running (test with subprocess mocked).
  [ ] oncall/.env.example lists every key with a comment; oncall/.env is
      gitignored.
  [ ] ruff + pytest pass in CI.
Depends on: F00 (setup: CI, AGENTS.md override) merged.
Collides with: EVERYTHING (owns the contracts). Others rebase on it.
Out of scope: any real tool logic, LLM calls.


=====================================================================
F02  Run log
=====================================================================
Module: brain    Priority: P0    Checkpoint: CP1    Size: S
Goal: every LLM call, tool call and decision is recorded; this powers the
evidence check (F13), report timeline and the demo.

Files: oncall/agent/__init__.py, oncall/agent/runlog.py,
       oncall/tests/agent/test_runlog.py
Interfaces:
  class RunLog:
      def __init__(self, run_id: str | None = None, runs_dir: str = ...)
      run_id: str; path: Path            # runs/<run_id>.jsonl
      def log(self, event: str, **data) -> None
          # event in {"alert","llm_call","tool_call","tool_result",
          #           "decision","action","error","finish"}; adds ts.
      def events(self, event: str | None = None) -> list[dict]
      def evidence_index(self) -> dict[str, Evidence]
          # every Evidence from every tool_result, keyed by id
      def token_usage(self) -> dict
Notes: JSONL, append-only, flush each write. runs/ is gitignored.
Acceptance:
  [ ] log -> events round-trips; evidence_index finds ids from 2 results.
  [ ] Concurrent-safe enough for one process (simple file append).
Depends on: F01        Collides with: F09 (uses it), later F13/F23.


=====================================================================
F03  Telemetry backends: live + offline (record & replay)
=====================================================================
Module: tools    Priority: P0    Checkpoint: CP1    Size: M
Goal: one raw-data layer for Prometheus, Jaeger and OpenSearch that works
live and from recorded fixtures, so people without a running demo can
still build and test F04-F06 and F09.

Files: oncall/tools/backends.py, oncall/tools/record.py (CLI),
       oncall/tests/tools/test_backends.py,
       oncall/tests/fixtures/<scenario>/ (recorded JSON)
Interfaces:
  class TelemetryBackend(Protocol):
      def prom_query(self, promql: str, at: str | None = None) -> dict
      def prom_range(self, promql: str, start: str, end: str,
                     step: str = "30s") -> dict
      def jaeger_services(self) -> list[str]
      def jaeger_traces(self, service: str, lookback: str = "15m",
                        limit: int = 20, tags: dict | None = None) -> list[dict]
      def logs_search(self, service: str | None, level: str | None,
                      since_min: int, limit: int) -> list[dict]
  class LiveBackend(TelemetryBackend)    # httpx, timeouts 10s, URLs from
                                         # config/discover_endpoints()
  class RecordingBackend(LiveBackend)    # also saves every response to
                                         # fixtures/<scenario>/<hash>.json
  class OfflineBackend(TelemetryBackend) # replays fixtures by request hash;
                                         # unknown request -> empty result
  def get_backend() -> TelemetryBackend  # from TELEMETRY_BACKEND
  CLI: python -m oncall.tools.record --scenario <name>  (records a fixed
       sweep of queries for all services while an incident is active)
Notes:
  - Jaeger API: GET {JAEGER_URL}/api/traces?service=..&lookback=..&limit=..
    &tags={"error":"true"}  and /api/services  (verify path, incl. proxy).
  - OpenSearch: POST {OPENSEARCH_URL}/{index}/_search; discover index via
    _cat/indices; map service + severity fields by inspecting one doc.
  - When organisers' offline bundles arrive, add a BundleBackend adapter
    in a separate issue; keep the same Protocol.
  - Recording with the demo healthy -> fixtures/baseline/; record one
    scenario per practice incident once faultctl is available.
Acceptance:
  [ ] Live: prom_query("up") returns data; jaeger_services() lists demo
      services; logs_search returns >=1 doc (paste real output in PR).
  [ ] Record a "baseline" scenario; OfflineBackend replays it and returns
      identical data for the same calls (test).
  [ ] Unreachable backend -> clear exception message (tools convert it).
Depends on: F01        Collides with: F04, F05, F06 (they call it; agree
method names in this PR before they finish), F14 later.


=====================================================================
F04  Tool: get_metrics
=====================================================================
Module: tools    Priority: P0    Checkpoint: CP1    Size: M
Goal: the agent can ask "is service X erroring / slow / saturated, and
how does that compare to before?"

Files: oncall/tools/metrics.py, +1 import line in oncall/tools/__init__.py,
       oncall/tests/tools/test_metrics.py
Interfaces:
  @register_tool("get_metrics", ...)
  def get_metrics(service: str | None = None,
                  metric: Literal["error_rate","latency_p95","rps",
                                  "top_errors"] = "error_rate",
                  window_min: int = 5,
                  baseline_offset_min: int = 30) -> ToolResult
  - service=None -> rank ALL services (top 5) for that metric. This is the
    agent's usual first call.
  - Each value reported as now vs baseline (same window, offset back) with
    delta and ratio.
  - window_min minimum is 5 (metrics arrive by OTLP push; shorter rate()
    windows return nothing). Reject or clamp smaller values.
  - Never group by or filter on feature_flag_* labels, and never query the
    feature_flag_evaluation_* metrics (RULES.md hard rule 7).
PromQL templates (names verified live; see VERIFIED FACTS above):
  error_rate: sum by (service_name) (rate(traces_span_metrics_calls_total
              {status_code="STATUS_CODE_ERROR"}[W])) / sum by (service_name)
              (rate(traces_span_metrics_calls_total[W]))
  latency_p95: histogram_quantile(0.95, sum by (le, service_name)
              (rate(traces_span_metrics_duration_milliseconds_bucket[W])))
  rps:        sum by (service_name)(rate(traces_span_metrics_calls_total[W]))
  top_errors: topk(5, sum by (service_name, span_name)(rate(
              traces_span_metrics_calls_total{status_code="STATUS_CODE_ERROR"}[W])))
  (CPU/memory come from container_health F07, not here.)
Evidence: one item per notable series, id "metric:<promql>@<ts>",
  text "checkout error_rate 0.31 (baseline 0.00)".
Acceptance:
  [ ] Live, healthy demo: all services near-zero error rate (paste output).
  [ ] With an incident active (faultctl, or ask a teammate to trigger one
      via the demo's own UI - a human action, not the agent), the affected
      service ranks #1 with a clear delta.
  [ ] Works on OfflineBackend fixtures; unit tests for parsing + ranking +
      empty data + backend error.
Depends on: F01, F03    Collides with: F05-F08 (__init__.py line), F14
(alert detector reuses the same PromQL - put templates in a module-level
dict PROMQL that F14 can import; F14 has the same >= 5m window minimum and
the same feature_flag_* ban).


=====================================================================
F05  Tool: search_traces
=====================================================================
Module: tools    Priority: P0    Checkpoint: CP1    Size: M
Goal: find WHERE in the call chain errors/latency originate.

Files: oncall/tools/traces.py, +1 import line in __init__.py,
       oncall/tests/tools/test_traces.py
Interfaces:
  @register_tool("search_traces", ...)
  def search_traces(service: str, errors_only: bool = True,
                    min_duration_ms: int | None = None,
                    lookback_min: int = 15, limit: int = 20) -> ToolResult
Logic:
  - Fetch traces; for each, find error spans (status code error /
    error=true tag) and the DEEPEST error span (root-cause candidate).
  - Group by (service, span_name, error message); count occurrences.
  - Summary: top 5 patterns, e.g. "12/20 traces: checkout -> payment
    'charge' failed: <msg>; deepest error in payment".
  - Report downstream service of each failing span (child spans' service).
  - Drop every feature_flag.* and demo.feature_flag.* span attribute before
    grouping or building evidence (RULES.md hard rule 7). Use the API at
    /jaeger/ui/api/v3/ (see VERIFIED FACTS).
Evidence: id "trace:<trace_id>/span:<span_name>", text = service + status
  + error message (truncated 200 chars), ts = span start.
Acceptance:
  [ ] Live: returns real trace ids that open in Jaeger UI (paste one).
  [ ] Deepest-error logic unit-tested on a hand-built 3-level trace.
  [ ] Empty result is ok=True with summary "no error traces found".
Depends on: F01, F03    Collides with: F04, F06-F08 (__init__.py line)


=====================================================================
F06  Tool: search_logs
=====================================================================
Module: tools    Priority: P0    Checkpoint: CP1    Size: M
Goal: surface the actual error messages a service is printing.

Files: oncall/tools/logs.py, +1 import line in __init__.py,
       oncall/tests/tools/test_logs.py
Interfaces:
  @register_tool("search_logs", ...)
  def search_logs(service: str | None = None,
                  level: Literal["error","warn","info"] = "error",
                  since_min: int = 15, contains: str | None = None,
                  limit: int = 200) -> ToolResult
Logic:
  - Query OpenSearch; normalise each message (strip uuids, hex, numbers,
    timestamps) -> group, count, keep first exact line + ts.
  - Summary: top 10 groups "x47 [cart] Can't access cart storage ..."
  - level is a minimum (error includes fatal; warn includes error). Filter
    on severity.number (error >= 17, warn >= 13), not severity.text.
  - Query the index pattern otel-logs-*, never a fixed index name.
  - Drop every attributes.feature_flag_* field from log docs before
    grouping or building evidence (RULES.md hard rule 7).
Evidence: id "log:<service>@<iso_ts>", text = exact original line
  (truncated 300 chars).
Acceptance:
  [ ] Live: returns real lines (paste trimmed output).
  [ ] Normalisation unit test: 3 lines differing only by ids -> 1 group.
  [ ] Unknown index / no OpenSearch -> ok=False with a helpful error.
Depends on: F01, F03    Collides with: F04, F05, F07, F08 (__init__.py)


=====================================================================
F07  Tool: container_health (read-only Docker)
=====================================================================
Module: platform    Priority: P0    Checkpoint: CP1    Size: S
Goal: detect infrastructure faults: stopped, restarting, OOM-killed or
CPU/memory-starved containers.

Files: oncall/platform/__init__.py, oncall/platform/containers.py,
       +1 import line in oncall/tools/__init__.py,
       oncall/tests/platform/test_containers.py
Interfaces:
  @register_tool("container_health", ...)
  def container_health(service: str | None = None) -> ToolResult
Logic:
  - READ-ONLY: docker SDK (docker.from_env()) or subprocess
    `docker ps -a --format json`, `docker inspect`, `docker stats
    --no-stream --format json`. Only containers of this compose project.
  - Per container: state, health, restart_count, oom_killed, exit_code,
    started_at, cpu_pct, mem_pct of limit.
  - Flag unhealthy: not running | restart_count increased | oom_killed |
    mem_pct > 90 | cpu_pct > 90 (thresholds as constants).
  - Summary lists flagged containers first; "all N healthy" otherwise.
  - Offline: read fixtures if present else ok=False "not available offline".
Evidence: id "container:<name>", text e.g. "cart: restarting, restarts=7,
  exit_code=137, oom_killed=true".
Acceptance:
  [ ] Live: lists all demo containers healthy (paste).
  [ ] Unit tests with mocked docker output: stopped, OOM, high CPU cases.
  [ ] grep proves no write calls (stop/start/restart/kill/rm/update) in
      the module; a test asserts this by scanning the source.
  [ ] Manual check: a teammate stops one container BY HAND; tool flags it.
Depends on: F01        Collides with: F04-F06, F08 (__init__.py); F14.


=====================================================================
F08  Tool: deploy_history
=====================================================================
Module: platform    Priority: P1    Checkpoint: CP1    Size: S
Goal: answer "did something change recently?" (the brief lists deploy
history as one of the four signals).

Files: oncall/platform/deploys.py, +1 import line in __init__.py,
       oncall/tests/platform/test_deploys.py
Interfaces:
  @register_tool("deploy_history", ...)
  def deploy_history(window_min: int = 60) -> ToolResult
Logic (until the starter kit gives a real source):
  - From Docker: containers whose StartedAt / Created is within window,
    with image + tag; containers whose image id changed (compare with a
    snapshot file runs/deploy_snapshot.json taken at agent start).
  - Clearly label the source in summary ("derived from container start
    times; no deploy system available").
  - Empty list is a valid, ok=True answer.
Evidence: id "deploy:<container>@<started_at>".
Acceptance:
  [ ] Live: restarting a container by hand shows up within the window.
  [ ] Unit test on mocked inspect output.
Depends on: F01 (F07 helpful - reuse its docker helper; don't duplicate)
Collides with: F07 (shared docker helper - F07 owns it, F08 imports it),
  F04-F06 (__init__.py line)


=====================================================================
F09  Investigation loop (Eyes) + LLM client + CLI
=====================================================================
Module: brain    Priority: P0    Checkpoint: CP1    Size: L
Goal: CP1 demo: given an alert, the agent picks tools ONE AT A TIME based
on results, then writes a symptom summary. Build against stub tools so you
never wait for F04-F08.

Files: oncall/agent/llm.py, oncall/agent/prompts.py (SYSTEM and
       INVESTIGATE constants only), oncall/agent/loop.py,
       oncall/main.py, oncall/tests/agent/test_loop.py,
       oncall/tests/agent/stub_tools.py
Interfaces:
  # llm.py - thin provider wrapper, tool-calling, temperature 0
  class LLM:
      def chat(self, messages: list[dict], tools: list[dict]) -> LLMReply
      # LLMReply: text, tool_calls=[{"id","name","args"}], usage
      # Provider from LLM_PROVIDER (whatever key organisers gave us);
      # implement ONE provider first, keep the interface provider-neutral.
  # loop.py
  def investigate(alert: Alert, tools: dict = TOOLS,
                  llm: LLM | None = None, max_steps: int = MAX_STEPS,
                  runlog: RunLog | None = None) -> dict
      # returns {"run_id", "summary", "steps": n, "tools_used": [...],
      #          "stopped": "finish"|"max_steps"|"error"}
  # main.py
  python -m oncall.main investigate --service checkout \
         --description "error rate high"  [--offline <scenario>]
Loop:
  1. messages = [SYSTEM, alert as user message]; tool schemas from
     TOOL_SCHEMAS + a pseudo-tool `finish(summary: str)`.
  2. Each turn: LLM returns tool calls -> run via TOOLS[name](**args) ->
     append ToolResult JSON (compact) -> log tool_call/tool_result.
  3. Stop on finish, max_steps, or 2 consecutive tool errors.
  4. Never pass all telemetry at once; only the agent's chosen results.
  5. Reject unknown tool names / bad args with an error message back to
     the LLM (don't crash).
Prompt rules (SYSTEM):
  - Role: on-call SRE for the Astronomy Shop; investigate step by step;
    start broad (get_metrics with no service), then narrow.
  - Always ground claims in tool output; cite evidence ids.
  - Never claim a cause without evidence; say what's unknown.
  - NO practice-incident answers, NO mention of feature flags or flag
    names, NO hints like "payment failures are usually X" tied to
    specific practice incidents. General SRE reasoning only.
Acceptance:
  [ ] With stub tools: test shows >=3 tool calls where call 2 depends on
      call 1's result (stub returns different data per args), then finish.
  [ ] Stops at max_steps; unknown tool name handled; LLM error handled.
  [ ] Live or offline run on one incident prints the tool sequence and a
      symptom summary citing evidence ids; run log written (paste it).
  [ ] Token usage per run printed.
Depends on: F01, F02 (F04-F08 optional - stubs until merged)
Collides with: prompts.py (F12 DIAGNOSE, F21 PROPOSE later - edit only
  your named constants), main.py (F14 watch, F19 dry-run/killswitch,
  F21 run - each adds its own subcommand), loop.py (F12 adds a hook).


=====================================================================
MERGE ORDER, OWNERS, AND THE CP1 PLAN
=====================================================================
Order:  F00 -> F01 -> (F02, F03) -> (F04, F05, F06, F07, F08, F09)
Parallel start allowed: F02/F03/F07/F09 can begin on F01's branch spec
  immediately (code to the contract), rebase when F01 merges.

Suggested owners:
  Brain    : F01, F02, F09
  Tools    : F03, F04, F05, F06   (F06 to Eval person if Tools is behind)
  Platform : F07, F08  + get the demo running (USB images) + record
             fixtures with F03's recorder
  Safety   : help F03/F05 now; start reading Action API docs when the
             starter kit arrives (F18+)
  Eval/Docs: 1-page architecture sketch for CP1 (not a code issue - a
             docs/hackathon/architecture.png PR), then F06 or test help

CP1 minimum (if time runs out): F01 + F03(live only) + F04 + F05 + F09
on ONE incident, plus the sketch.

Reality check: it's ~14:50; CP1 is 15:30. Aim to show the loop + 2-3
tools live at CP1 even if F06-F08 aren't merged. Honest partial demo >
broken full demo.


=====================================================================
WAVE 2 - BRAIN (F11-F17)  -> Checkpoint 2 at 18:30
=====================================================================
F10 is unused (the old sketch number, now D01). Same rules as F01-F09.

CHECKPOINT 2 REQUIREMENT (what the mentor will test at 18:30)
------------------------------------------------------------
"Root cause with evidence and confidence; output in the JSON schema.
Correct diagnosis on at least 3 practice incidents chosen by the mentor."
Critical path: F09 -> F12 -> F16. F11 provides the incidents to test on.
F13 + F15 make it safe/honest (judges + hidden test). F14 makes it
automatic. F17 proves it.

VERIFIED TELEMETRY FACTS (use exactly; see TEAM_CONTEXT "Verified repo facts")
-----------------------------------------------------------------------------
- Prometheus http://127.0.0.1:9090. traces_span_metrics_calls_total,
  traces_span_metrics_duration_milliseconds_bucket. Labels service_name,
  span_name, span_kind, status_code (STATUS_CODE_UNSET|OK|ERROR),
  error_type, error_message, rpc_grpc_status_code,
  http_response_status_code. rate() windows >= 5m (OTLP push).
- Healthy baseline has NON-ZERO errors: load-generator ~0.05/s,
  frontend-proxy ~0.015/s. Always compare to baseline.
- Jaeger v3 via http://127.0.0.1:8080/jaeger/ui/api/v3/..., OTLP JSON,
  hex ids, typed attributes.
- Logs: OpenSearch otel-logs-*, resource.service.name, severity.number
  (error>=17, warn>=13), body, @timestamp.
- HARD RULES: scrub /feature[_.]flag/i everywhere; exclude service flagd;
  load-generator is a CLIENT (symptom, never root cause). Never put
  practice-incident answers in oncall/ code or prompts (eval/ only).
- The demo also contains an LLM "agent" service and "chatbot"; they can
  be incident targets like any other service.


=====================================================================
F11  Scenario library: record practice incidents as fixtures
=====================================================================
Module: platform/eval  Owner: integration-box person (has the demo)
Priority: P0   Needed by: 17:15   Size: S (mostly human work + script)
Goal: give everyone real incident data to develop and test the Brain on,
before the organisers' bundles/faultctl arrive.

Files: scripts/record_scenario.ps1 (+ .sh), eval/scenarios.md,
       eval/expected.yaml, oncall/tests/fixtures/<scenario>/ (output of
       F03 recorder)
Procedure (HUMAN injects - the agent never touches flags):
  1. Demo healthy 10 min -> record "baseline".
  2. For each scenario: inject by hand (flag UI http://127.0.0.1:8080/feature
     for app faults; `docker stop <svc>` / `docker update --cpus 0.1 <svc>`
     by hand for infra faults), wait 3 min, record, undo, wait 3 min.
  3. Neutral names only: scenario-01, scenario-02, ...
Target set (covers app + infra + client-symptom cases):
  scenario-01 payment fails on charge         (app error, deep in chain)
  scenario-02 cart fails intermittently       (app error, partial rate)
  scenario-03 ad service high CPU / GC         (resource/latency)
  scenario-04 recommendation memory leak       (resource growth)
  scenario-05 homepage traffic flood           (load surge, not a bug)
  scenario-06 cart cache (valkey) stopped      (infra: dependency down)
  scenario-07 a service container stopped      (infra: container down)
eval/expected.yaml (ONLY place answers live):
  scenario-01: {component: payment, category: app_error, action: ...}
  ...  (written by the human who injected it)
Acceptance:
  [ ] baseline + >=4 scenarios recorded and committed (fixtures small:
      cap recorder output, no raw dumps > 2 MB per scenario).
  [ ] eval/expected.yaml filled; CI rule: nothing under oncall/ reads
      eval/expected.yaml (add grep to rules job).
Depends on: F03 (recorder)   Collides with: F17 (expected.yaml format -
  F17 owner defines the schema of expected.yaml; agree first).


=====================================================================
F12  Diagnosis step
=====================================================================
Module: brain   Owner: P1   Priority: P0   Needed by: 17:45   Size: L
Goal: turn the investigation into a structured, evidence-backed
diagnosis that generalises to unseen and combined faults.

Files: oncall/agent/diagnosis.py, oncall/agent/taxonomy.py,
       oncall/agent/prompts.py (INVESTIGATE update + DIAGNOSE constant),
       oncall/agent/loop.py (hook: after finish -> diagnose),
       oncall/models.py (ADD Diagnosis TypedDict only - coordinate w/ P1
       as F01 owner = same person), oncall/tests/agent/test_diagnosis.py
Interfaces:
  Diagnosis = {
    "component": str | None,          # root-cause service/container
    "category": Category,             # enum from taxonomy.py
    "cause": str,                     # one-sentence specific cause
    "confidence": float,              # 0..1 (LLM estimate; F15 adjusts)
    "evidence_ids": list[str],        # must exist in run log (F13)
    "affected_services": list[str],   # symptoms/blast radius
    "alternatives": [{"hypothesis": str, "rejected_because": str}],
    "decision": "act" | "escalate",
    "reasoning": str                  # <= 800 chars, cites evidence ids
  }
  def diagnose(run: RunLog, alert: Alert, llm: LLM) -> Diagnosis
    # LLM must answer via a forced tool call submit_diagnosis(schema)
    # (structured output), never free text. One retry on invalid output,
    # else return an escalate Diagnosis with category "unknown".
taxonomy.py - GENERAL fault categories + the signals that indicate them
(reasoning aids, NOT practice answers; no service names tied to causes):
  app_error             ERROR spans originating in one service (deepest
                        error span), error_type/error_message present,
                        error logs in that service; container healthy
  dependency_unavailable connection refused/timeout errors to a backing
                        store or downstream; that dependency's container
                        down/unhealthy or absent from traces
  container_down        container not running / restarting / OOMKilled;
                        callers show connection errors
  resource_cpu          latency up, CPU high in container_health, GC
                        logs/metrics up; error rate may be ~normal
  resource_memory       memory % rising toward limit, restarts/OOM,
                        latency degrading over time
  network_degradation   latency/timeouts between two specific services,
                        both containers healthy, no app exceptions
  traffic_surge         RPS sharply up at entry (frontend/proxy),
                        latency up broadly, few app exceptions
  upstream_propagation  service shows errors only because a downstream
                        it calls is failing (never the final answer -
                        follow it down)
  unknown               evidence insufficient/contradictory
Investigation strategy (put in INVESTIGATE prompt):
  1 TRIAGE   get_metrics(no service) for error_rate AND latency_p95 AND
             rps; container_health(all).
  2 LOCALISE follow the worst service down the call chain with
             search_traces; the deepest ERROR span's service is the
             candidate. Ignore load-generator/frontend-proxy as causes.
  3 CHARACTERISE search_logs on the candidate; container_health on it;
             deploy_history.
  4 FALSIFY  name the best alternative hypothesis and run ONE tool call
             that would distinguish them; record why it was rejected.
  5 FINISH   only when the candidate has >=2 evidence items from >=2
             different tools, or MAX_STEPS reached.
Combined faults: if two candidates are independent (no parent/child in
traces), list both in affected_services, set component to the one with
earliest onset / strongest evidence, and decision=escalate unless one is
clearly upstream of the other.
Acceptance:
  [ ] On fixtures scenario-01..04: correct component + category on >=3
      (paste the Diagnosis JSONs).
  [ ] Unit tests: invalid LLM output -> retry -> escalate fallback;
      load-generator never returned as component (post-check in code).
  [ ] grep: taxonomy/prompts contain no flag names and no
      scenario->answer mappings.
Depends on: F09 (merged), F02. Fixtures from F11 for the real test.
Collides with: prompts.py/loop.py (F09 owner = same person), F13, F15,
  F16 consume Diagnosis (contract defined HERE - freeze it early, push
  the TypedDict in the first commit and tell the team).


=====================================================================
F13  Evidence validator
=====================================================================
Module: brain   Owner: P2 (after F04)   Priority: P0   Needed by: 18:00
Size: S
Goal: make "invented evidence is penalised" impossible.

Files: oncall/agent/evidence.py, oncall/tests/agent/test_evidence.py
Interfaces:
  def validate(d: Diagnosis, run: RunLog) -> tuple[Diagnosis, list[str]]
    # returns cleaned diagnosis + list of problems found
Rules:
  - Drop evidence_ids not in run.evidence_index().
  - Any evidence id quoted in d.reasoning but not in the index -> remove
    that sentence or flag it in problems.
  - Numbers: if reasoning claims a metric value for an id, check it is
    within 5% of the recorded value; else flag.
  - If the remaining evidence for component < 2 items or comes from only
    one tool -> lower confidence (multiply 0.6) and add problem.
  - If zero valid evidence -> decision=escalate, category=unknown.
Acceptance:
  [ ] Fabricated trace id removed; wrong metric value flagged; zero
      evidence -> escalate (unit tests with a synthetic RunLog).
Depends on: F02, F12 contract (can start from the TypedDict).
Collides with: F15 (run order: validate -> confidence).


=====================================================================
F14  Alert detector
=====================================================================
Module: platform   Owner: P3 (after F07)   Priority: P1 for CP2 (P0 for
CP3)   Needed by: 18:15   Size: M
Goal: incidents start the agent automatically ("Detect" step).

Files: oncall/platform/alert.py, oncall/main.py (`watch` subcommand
       only), oncall/tests/platform/test_alert.py
Interfaces:
  def check_once(backend, baseline: dict) -> list[Alert]
  def watch(poll_s: int = ALERT_POLL_S, on_alert=investigate_and_diagnose)
CLI: python -m oncall.main watch [--once] [--offline <scenario>]
Logic:
  - Reuse F04's PROMQL templates (import, don't copy). Windows [5m].
  - Baseline: rolling 30 min median per service, captured at start
    (fallback to config thresholds if no history).
  - Fire when, for a non-client, non-flagd service:
      error_rate > max(ALERT_ERROR_RATE, 3 x baseline) OR
      p95 > max(ALERT_P95_MS, 2 x baseline) OR
      container_health flags it (down/restarting/OOM).
    Also fire on frontend-proxy/load-generator error spikes as a
    user-facing symptom alert (service=None, description says so).
  - Debounce: one alert per incident; suppress repeats for 10 min or
    until signals return to baseline.
  - Log every check result compactly to runs/watch.jsonl.
Acceptance:
  [ ] Healthy demo: 10 min of `watch` with zero alerts (paste log).
  [ ] Injected scenario (by hand): alert within 2 poll cycles, agent
      starts automatically, no duplicate alerts.
  [ ] Unit tests for thresholds, client exclusion, debounce.
Depends on: F03, F04, F07, F09.  Collides with: main.py (own subcommand
  only), F04 (PROMQL dict ownership stays with F04).


=====================================================================
F15  Confidence and escalation rules
=====================================================================
Module: brain   Owner: P1 (or P4 if P1 is behind)   Priority: P0
Needed by: 18:00   Size: S
Goal: calibrated, explainable act/escalate decision ("a confident wrong
fix scores worse than escalating").

Files: oncall/agent/confidence.py, oncall/tests/agent/test_confidence.py
Interfaces:
  def assess(d: Diagnosis, run: RunLog) -> Diagnosis
    # sets final confidence, decision, appends "confidence: ..." reasons
Rules (deterministic, computed from the run log, applied as caps on the
LLM's estimate):
  - evidence from 1 tool only            -> cap 0.55
  - < 2 evidence items for component     -> cap 0.5
  - >1 independent unhealthy service     -> cap 0.5 (combined fault)
  - category unknown / upstream_propagation as final -> cap 0.3
  - component is a CLIENT_SERVICE or None -> decision escalate
  - alternatives empty (not falsified)   -> -0.1
  - container signal + matching trace/log signal agree -> +0.1 (max 0.95)
  decision = act if confidence >= CONFIDENCE_MIN (0.7) else escalate.
  Every adjustment is recorded in reasoning so the report explains it.
Acceptance:
  [ ] Unit tests per rule; a clear single-service case stays "act"; a
      two-independent-services case becomes "escalate".
  [ ] Log confidence + correctness per scenario for F17 calibration.
Depends on: F12, F13.   Collides with: F13 (order), S2 calibration later.


=====================================================================
F16  Report output + JSON schema validation (provisional schema)
=====================================================================
Module: safety/report   Owner: P4 (after F05)   Priority: P0
Needed by: 18:00   Size: M
Goal: every run ends with a schema-valid JSON report - even on errors.
We build the schema ourselves: oncall/report/schema.json IS the schema
(no organiser schema is coming). Keep the adapter as identity so a later
change stays a one-file change.

Files: oncall/report/__init__.py, oncall/report/schema.json,
       oncall/report/output.py, oncall/report/adapter.py,
       oncall/tests/report/test_output.py
Interfaces:
  def build_report(alert, diagnosis, run, actions=None,
                   verification=None) -> dict      # internal format
  def to_official(report: dict) -> dict            # adapter; identity
                                                   # (stays identity)
  def validate(report: dict, schema_path: str) -> list[str]
  def write(report: dict, out_dir="reports") -> tuple[Path, Path]
      # reports/<run_id>.json (validated) + reports/<run_id>.md
  def fallback_report(alert, run, error: str) -> dict
      # minimal VALID escalate report when anything fails
Provisional schema fields: incident_id, detected_at, alert{...},
  root_cause{component, category, description}, confidence, decision,
  evidence[{id, source, text, ts}], affected_services, alternatives,
  timeline[{ts, event}], actions[], verification{}, prevention,
  limitations, agent_version.
  evidence[].text is copied from the run log (never re-generated).
  timeline built from run log events.
Behaviour: validate -> if invalid, one deterministic repair (fill
  required fields, coerce types) -> if still invalid, fallback_report.
  Never crash, never write an invalid file.
  SCHEMA_PATH in config points to oncall/report/schema.json;
  to_official() stays identity.
CLI: `python -m oncall.main investigate ...` writes the report at the
  end (small hook in main.py; coordinate with F09 owner).
Acceptance:
  [ ] 100% of runs (incl. forced LLM failure) produce a valid JSON file
      + readable markdown (tests).
  [ ] Evidence text in report matches run log exactly (test).
Depends on: F02, F12 contract.  Collides with: main.py (hook only),
  F23 later (report writer extends this module - same owner).


=====================================================================
F17  Eval harness
=====================================================================
Module: eval   Owner: P5 (after F06)   Priority: P0   Needed by: 18:15
Size: M
Goal: one command shows how many practice scenarios we get right -
feeds the CP2 rehearsal, the evaluation note and calibration.

Files: eval/run_eval.py, eval/README.md, eval/results/.gitkeep
       (results/*.json gitignored except summary.md)
Interfaces:
  python -m eval.run_eval [--scenarios scenario-01,...] [--live]
  Default: OFFLINE on F11 fixtures (TELEMETRY_BACKEND=offline).
Scoring per scenario (compare to eval/expected.yaml):
  correct   component AND category match           = 1.0
  partial   component match, category wrong        = 0.5
  escalated decision=escalate with right component in affected/alts = 0.5
  wrong     confident (act) and wrong component    = 0 and flagged RED
  invalid   report not schema-valid                = 0 and flagged RED
Output: table (scenario | expected | got | confidence | decision |
  score | steps | tokens | seconds) + totals; save eval/results/summary.md
  and per-run JSON. Also a calibration table: confidence bucket vs
  accuracy.
Rules: eval/ may read expected.yaml; oncall/ must never import eval/.
Acceptance:
  [ ] Runs all recorded scenarios offline in one command (paste table).
  [ ] Deterministic enough: same scenario twice -> same component.
Depends on: F11, F12, F16 (end-to-end); write the harness against stubs
  now.   Collides with: F11 (expected.yaml format - F17 defines it).


=====================================================================
CP2 MINIMUM CUT
=====================================================================
If short on time at 17:45: F12 + F16 working on 3 fixtures, F13 merged.
F15/F14/F17 can slip to Day 2 morning; say so honestly at the checkpoint.


=====================================================================
F18-F19 - OUR OWN faultctl + ACTION API
=====================================================================
CONFIRMED: these are built by OUR team (not provided by organisers).
NUMBERING: the old AGENT_BRIEF Day-2 numbers (F18-F23) are superseded.
Day-2 Hands features will be specced as F20+ later. Older references in
this file to F19/F21/F23 as Day-2 features use the superseded numbers.


=====================================================================
F18  faultctl: inject and reset incidents (human/test tool)
=====================================================================
Module: platform   Owner: P3 (or free teammate)   Reviewer: P4
Priority: P0   Needed by: Day 1 19:00 latest (speeds up F11 + F17)
Branch: feat/18-faultctl   Size: M
Goal: one command to inject a known incident and one to reset everything,
so scenarios are reproducible for recording (F11), testing and the
demo. This is a HUMAN tool: the agent must never call it or import it.

Files: scripts/faultctl/faultctl.py (+ faultctl.ps1 / faultctl.sh thin
       wrappers), scripts/faultctl/scenarios.yaml,
       scripts/faultctl/README.md, scripts/faultctl/test_faultctl.py
       (NOT under oncall/ - keep it out of the agent's package)
CLI:
  faultctl list                       # scenarios with neutral ids only
  faultctl inject <scenario-id>       # e.g. scenario-03
  faultctl inject --combo s-01,s-06   # combined faults
  faultctl status                     # what is currently injected
  faultctl reset                      # undo EVERYTHING, verify healthy
scenarios.yaml: id -> type + params (+ a human description). Types:
  flag        set a demo failure flag on/off (mechanism: flagd UI/API on
              the running demo - VERIFY the real write mechanism first;
              do NOT edit tracked files under src/)
  stop        docker stop <container>
  restart_loop  repeatedly kill a container (bounded duration)
  cpu_limit   docker update --cpus <n> <container>
  mem_limit   docker update --memory <m> <container>
  latency     (P2) network delay between two services, e.g. via a
              netem sidecar (pumba) - only if time permits
State: every inject writes scripts/faultctl/.state.json with the
  ORIGINAL values (limits, flag values, container state) so reset
  restores exactly. reset also restores anything missing from state to
  defaults and then checks container_health shows all healthy.
Safety: only touches containers of this compose project; refuses
  unknown scenario ids; never touches anything outside the laptop.
Separation rules (add to CI rules job):
  - oncall/ must not import or reference scripts/faultctl (grep).
  - scenarios.yaml ids are neutral; the mapping id -> cause also lives
    in eval/expected.yaml for scoring. Nothing in oncall/ reads either.
Acceptance:
  [ ] inject -> effect visible in telemetry within 3 min (paste
      get_metrics / container_health output) -> reset -> healthy again,
      for: one flag scenario, one stop, one cpu_limit.
  [ ] reset is idempotent (run twice, no errors) and restores limits.
  [ ] combo inject + reset works.
  [ ] Unit tests with docker/flag calls mocked.
Depends on: nothing new (demo running; may reuse F07's docker helper
  read-only functions - import, don't copy).
Collides with: F11 (F11 switches from manual injection to faultctl once
  this merges), F17 (live eval mode calls faultctl from eval/, never
  from oncall/).


=====================================================================
F19  Action API: the only way the agent changes the system
=====================================================================
Module: safety   Owner: P4 (or free teammate)   Reviewer: P1
Priority: P0   Needed by: Day 2 09:30 (Hands work starts)
Branch: feat/19-action-api   Size: M
Goal: the single, allowlisted, fully logged interface for changing the
demo. The agent's executor (Day 2) will call ONLY this. Approval is NOT
inside this module - the approval gate (F20+) sits in front of it.

Files: oncall/safety/__init__.py, oncall/safety/action_api.py,
       oncall/safety/allowlist.py, oncall/safety/actionlog.py,
       oncall/tests/safety/test_action_api.py
       (oncall/safety/ is the ONLY place allowed to mention flags - CI
       rule already allows it)
Interfaces:
  ActionRequest = {"action": str, "target": str, "params": dict,
                   "reason": str, "run_id": str, "dry_run": bool}
  ActionResult  = {"request": ActionRequest, "allowed": bool,
                   "executed": bool, "dry_run": bool, "ok": bool,
                   "detail": str, "before": dict, "after": dict,
                   "rollback": ActionRequest | None, "ts": str}
  def execute(req: ActionRequest) -> ActionResult
Actions (allowlist.py - exact names, targets and bounds):
  restart_service   target in DEMO_SERVICES (not flagd, not otel stack,
                    not jaeger/prometheus/opensearch/grafana)
                    -> docker restart <container>
                    rollback: none (idempotent)
  toggle_flag       target = flag key, params {"enabled": false} ONLY
                    (agent may only turn failure flags OFF); key must be
                    in an explicit FLAG_ALLOWLIST - VERIFY write
                    mechanism (same as faultctl)
                    rollback: previous value recorded in "before"
  throttle_load     target = "load-generator", params {"users": int}
                    bounded 0..current; via Locust web API
                    (POST /swarm user_count/spawn_rate; resolve the
                    Locust port with docker compose port) - VERIFY
                    rollback: previous user count
  scale_service     Kubernetes only -> we run Docker Compose: always
                    returns allowed=False, detail "not supported on
                    compose" (documented limitation)
Rules:
  - Anything not in the allowlist -> allowed=False, executed=False,
    logged. Never raises to the caller.
  - dry_run=True -> validate + compute "before" + log, execute nothing.
  - Every call (allowed or not, dry or real) appended to
    runs/actions.jsonl (append-only, one line per call, with run_id).
  - Records "before" state and a ready-made rollback request.
  - The LLM never imports this module: only oncall/safety/executor.py
    (Day 2) may. Add a CI grep: no import of oncall.safety.action_api
    outside oncall/safety/ and oncall/tests/safety/.
Acceptance:
  [ ] Non-allowlisted action/target/params rejected and logged (tests).
  [ ] Dry run executes nothing (test with docker mocked, assert no call).
  [ ] Live: restart_service on a non-critical demo service works and is
      logged; throttle_load reduces Locust users and rollback restores.
  [ ] actions.jsonl lines are complete and append-only.
Depends on: F01 (done). Uses read-only helpers from F07 for "before".
Collides with: nothing now; Day-2 executor/approval/verify build on its
  ActionResult contract (freeze it in the first commit).
