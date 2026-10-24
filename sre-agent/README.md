# Incident Zero — AI On-Call Engineer for the OpenTelemetry Astronomy Shop

An agent that **detects** an incident from telemetry, **investigates** it by choosing tools one step at a
time, **diagnoses** the root cause with checked evidence and a calibrated confidence, **proposes** one
allowlisted fix, **asks a human**, **acts** only through the Action API, **verifies** recovery (rolls back
and escalates if not), and writes an **incident report**. When it is not confident it escalates with its
findings instead of guessing.

See [ARCHITECTURE.md](ARCHITECTURE.md) · [EVALUATION.md](EVALUATION.md) · [TEAM_FORM.md](TEAM_FORM.md) ·
reports in [incident_reports/](incident_reports/).

## Input → output

| | |
|---|---|
| **Input** | an **alert** (our watcher: error rate / p95 / traffic drop vs. a 30-min-ago baseline, or a container stopped / restarting / OOM), plus **live telemetry** read through tools: Prometheus span metrics, Jaeger traces, OpenSearch logs (fallback `docker logs`), Docker state. A **human** answers the approval prompt. |
| **Output** (per incident, `runs/<incident_id>/`) | `output.json` — diagnosis in the required JSON schema (root-cause service + component, fault type, confidence, evidence with exact trace IDs / log lines / metric values, status `diagnosed` / `escalated` / `no_incident`, proposed action, outcome) · `report.md` — readable report: timeline, root cause, evidence, action, verification, prevention · `tool_calls.jsonl`, `actions.jsonl`, `approval.json`, `verification.json` — the full audit trail |

## Setup

```bash
# demo running:  cd opentelemetry-demo && make start   (or docker compose up -d)
cd sre-agent
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # LLM key/model, Action API URL
python -m agent.main check         # every line [OK]  (LLM optional - rule-based fallback works without it)
python -m agent.main baseline      # while the shop is HEALTHY: snapshot normal CPU/memory per container
```
### Action API (the agent's "hands")

The agent changes the system only through the Action API. We run our own small one,
`action_api/server.py` (stdlib HTTP, no extra deps). It is the only process that touches Docker, flagd
or Locust:

```bash
python -m action_api                 # terminal 1 - listens on http://127.0.0.1:8000, keep it running
python -m agent.main check           # "action api: ... HTTP 200"
python -m agent.main action restart_service service=ad --dry-run
```

| Endpoint | Allowlisted action | What it really does |
|---|---|---|
| `POST /actions/restart {service}` | `restart_service` | `docker restart <container>` (also starts a stopped / unpauses a paused one), waits until running/healthy |
| `POST /actions/flag {flag, variant}` | `toggle_flag` | sets the flag's `defaultVariant` through the flagd-ui API, which updates the UI, the file and flagd together. If flagd-ui isn't running (minimal mode), it edits the flagd file directly and flagd hot-reloads it |
| `POST /actions/load {users}` | `throttle_load` | Locust `/swarm` via `http://localhost:8080/loadgen` |
| `POST /actions/scale {service, replicas}` | `scale_service` | `kubectl scale` (Kubernetes only; refused with 409 on Docker) |
| `GET /actions/log` | | every accepted/refused call (`runs/action_api_server.jsonl`) |

The server enforces the same safety rules again: it refuses any call without an `approved` approval
record naming a human (403), refuses everything while the kill switch `runs/KILL` exists (423), never
restarts observability/infra tooling, allows at most 3 restarts of one service per 10 minutes, and never
returns flag values (so it cannot be used for diagnosis). Flags are changed through flagd-ui when it runs,
because flagd-ui keeps its own copy of the flags in memory and writes it back on every save; editing the file
behind its back would leave the UI stale and could undo the fix. Without flagd-ui the flag file is found from
the `flagd` container's mount (or set `OTEL_DEMO_DIR` / `FLAGD_FILE` in `.env`).

**End-to-end with a human in the loop** (inject a practice incident with `faultctl` first, wait 2–3 min):
```bash
python -m agent.main respond                 # diagnose -> shows ROOT CAUSE, EVIDENCE, PROPOSED ACTION,
                                             # WHAT HAPPENS -> type "yes" -> Action API executes ->
                                             # verifies recovery -> report.md (outcome=resolved)
python -m agent.main respond --approve web   # same, approve from http://localhost:8765
```

If the organisers' output schema / Action API differ from the defaults:
* copy their JSON schema to `config/output_schema.json` and adjust `to_official()` in `agent/schema.py`;
  `python -m agent.main schema-check runs/latest/output.json` must print `VALID`.
* if the organisers provide their own Action API, point `ACTION_API_URL` at it and edit paths/bodies in
  `config/action_api.yaml`; test with
  `python -m agent.main action restart_service service=ad --dry-run`.

## How to run

```bash
python -m agent.main see                        # Eyes: symptom summary of the last 5 min
python -m agent.main diagnose                   # Brain: investigate now -> output.json + proposed action (changes nothing)
python -m agent.main run                        # Full loop: watch -> alert -> diagnose -> approve -> act -> verify -> report
python -m agent.main run --dry-run              # full loop, but the action is only logged (read-only)
python -m agent.main run --approve web          # approve/reject from a page at http://localhost:8765
python -m agent.main respond                    # full loop immediately (skip waiting for the watcher)
python -m agent.main diagnose --no-llm          # rule-based only (no LLM)
python -m agent.main diagnose --replay runs/<id>/snapshot.json   # re-run on recorded telemetry (offline)
python -m agent.main eval                       # accuracy + confidence calibration on the practice set
python -m agent.main export                     # copy reports into incident_reports/
python -m tests.run                             # offline tests (no demo / LLM needed)
```
Practice loop: `faultctl` inject → wait 2–3 min (load must hit it) → `diagnose --expect <service>[:<fault_type>]`
(or `respond --expect ...`) → `faultctl` reset → repeat. Then `eval` and `export`.

## Safety: approval gate, dry run, kill switch

* **Nothing changes without an explicit yes.** `actions.execute()` refuses any call without an approval
  record whose decision is `approved`. CLI mode requires typing `yes`; anything else (or Ctrl-D) rejects.
  `--approve reject` = unattended mode: diagnose and report, never act.
* **Allowlist.** Only `restart_service`, `toggle_flag`, `throttle_load`, `scale_service`
  (`config/runbook.yaml`), and only through the Action API (`config/action_api.yaml`). The agent never
  runs docker/kubectl commands that change anything — Docker is used read-only (`ps`, `inspect`, `stats`, `logs`).
* **Dry run** (`--dry-run`): shows and logs the exact request it would send; no API call.
* **Kill switch**: `python -m agent.main kill` (from any terminal) creates `runs/KILL`. It is checked
  before every action; while engaged the agent still diagnoses and reports but executes nothing.
  `unkill` releases it; `status` shows it and the last actions.
* **Confidence gate**: below `CONFIDENCE_TO_ACT` (0.6), with fault type `unknown`, or when no cited evidence
  can be found in the telemetry, the agent escalates instead of proposing a fix.
* **Verify + rollback**: after acting it watches the 1-minute metrics up to 4 min; if not recovered it
  rolls back reversible actions (throttle / scale, with approval) and escalates.
* **Rules compliance**: the agent never reads feature-flag settings (flagd files, flag UI or flag API) to
  diagnose, contains no per-incident answers, and does not touch the demo's code/config, faultctl or
  the scoring harness. `tests/` contains a check that no flag-reading code exists.

## Layout

| Path | Role |
|---|---|
| `agent/detect.py` | alert rules + watch loop (step 1) |
| `agent/toolbox.py` | the 14 investigation tools (specs for the LLM), call log, replay |
| `agent/tools/metrics.py · traces.py · logs.py · deploys.py` | Prometheus · Jaeger · OpenSearch/docker logs · Docker state & deploy history |
| `agent/investigate.py` | LLM tool-calling loop, deterministic fallback, finalisation (escalation, calibration) |
| `agent/rules.py` | telemetry-only candidate ranking (fallback + independent reviewer) |
| `agent/evidence_check.py` | verifies every cited evidence item exists in tool results |
| `agent/runbook.py` | picks one allowlisted remedy + rollback |
| `agent/approval.py · actions.py · recovery.py` | approval gate · Action API client, dry run, kill switch · verify recovery |
| `agent/report.py · memory.py · pipeline.py` | report + prevention · incident memory · end-to-end orchestration |
| `agent/schema.py` | output schema + mapping to the official schema |
| `config/*.yaml` | dependency graph, Action API endpoints, runbook |

## Known limitations

* Needs ~2 min of load after a fault before metrics/traces show it; detection fires after 2 bad polls (~40 s more).
* Fault-type classification is heuristic (keywords in span/log messages, container state, metric shape);
  unfamiliar faults may be reported as `unknown` → escalated, by design.
* Network latency/packet loss is inferred from client-span self-time towards a dependency; with low traffic it can be missed.
* For two simultaneous faults the agent reports the dominant one and lists the other under `alternative_hypotheses`; it proposes one action per incident.
* `scale_service` only on Kubernetes; on Docker Compose resource starvation is escalated.
* The Action API is our own (no organiser Action API was available to us). Flag toggles go through the
  demo's flag UI API, so the UI, the flag file and flagd stay in sync.
* A flag toggle only helps when that flag caused the fault. If an infra fault (e.g. CPU starvation)
  looks like an application fault, the toggle changes nothing, verification fails and the agent escalates.
* A restart cannot be rolled back; if it does not help the agent escalates.
* Memory/CPU anomaly detection is only reliable after `baseline` was taken while healthy (the watcher refreshes it while healthy).
* Flag toggles as a *remedy* are configured per service in `config/runbook.yaml` (`enable_flag_remediation`); diagnosis never reads flag state.
