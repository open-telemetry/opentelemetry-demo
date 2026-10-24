# Bosch Incident Zero

An incident agent for the OpenTelemetry Astronomy Shop. Given an alert, it investigates with read-only
telemetry tools, names the root cause with cited evidence, and proposes one allowlisted fix. The fix runs
only after a human approves it, only through the organisers' Action API, and is then verified against fresh
telemetry.

- How it works: [docs/ARCHITECTURE_OVERVIEW.md](docs/ARCHITECTURE_OVERVIEW.md) (one page), with more detail in
  [docs/AGENT.md](docs/AGENT.md).
- What has and has not been measured: [docs/EVALUATION_NOTE.md](docs/EVALUATION_NOTE.md).

The project lives in `bosch-incident-zero/`, separate from the upstream demo, and talks to the demo only
over its HTTP endpoints and the Docker CLI.

## Status (2026-10-24)

| Part | Status |
|---|---|
| Investigation and diagnosis (8 tools, guards, confidence gate, report) | Working against the live demo |
| Human approval, kill switch, action layer, verification | Being finalised for Checkpoint 3; runs on the dry-run backend |
| Official `faultctl`, practice incidents, Action API contract, report schema | **BLOCKED**: not yet supplied by the organisers |

## Setup

Prerequisites: Python 3.11+, and Docker Desktop running the OpenTelemetry demo (`make start` in the repo root).

```bash
cd bosch-incident-zero
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt anthropic openai
cp .env.example .env
chmod 600 .env
```

Then set the model in `.env`, which is git-ignored. Never put a key in a tracked file such as `.env.override`.

```bash
LLM_PROVIDER=openrouter                 # or anthropic, openai, gemini, openai_compatible
LLM_BASE_URL=https://openrouter.ai/api/v1
LLM_MODEL=nvidia/nemotron-3-ultra-550b-a55b:free
LLM_FALLBACK_MODELS=nvidia/nemotron-3.5-super-vl:free,poolside/laguna-s-2.1:free,nvidia/nemotron-3.5-lightning:free,dots-studio/dots-3-note-preview:free
LLM_API_KEY=<your key>
```

**Models: free tier on OpenRouter only.**

- The main model is `nvidia/nemotron-3-ultra-550b-a55b:free`.
- The fallbacks in `LLM_FALLBACK_MODELS` are tried in order only when the provider fails (HTTP 402, 404,
  429, 5xx or a timeout), never because of bad model output. Bad output is handled by the guards and
  escalates.
- The model that actually answered is recorded in the transcript and in the `DIAGNOSIS` event.
- Free-tier limits on an account with no credits: about 20 requests a minute and about 50 a day. That is
  roughly 4 live investigations a day, which is why the tests and the rehearsal use recorded transcripts.
- Data policy: free providers may log prompts. Only demo telemetry is sent. Keys and secrets are scrubbed
  from events and never put in prompts.

Without a configured provider the agent refuses to run, exiting with code 2. It never falls back to a
canned diagnosis.

Check the environment and the live tools:

```bash
.venv/bin/python scripts/verify_environment.py
.venv/bin/python -m src.agent --tools-only        # every tool once against the live stack, no LLM
```

## How to run

```bash
.venv/bin/python -m src.agent --alert "Error rate above 5% on checkout"
```

The alert text is the only thing the agent receives. Each run writes `incident_output/<incident-id>/`:
`transcript.json` (every tool call, result and gate decision), `report.json`, and `run.log`. Safety events
are also appended to `audit_logs/audit.jsonl`.

Exit codes: `0` on a finished run, `2` when the LLM is not configured.

## How to watch a run

Run this in a second terminal while the agent works:

```bash
.venv/bin/python scripts/watch_run.py                        # follow new events as they arrive
.venv/bin/python scripts/watch_run.py --incident DEMO-002    # follow one incident
.venv/bin/python scripts/watch_run.py --once --incident DEMO-002   # print what exists and exit
```

It prints a colour-coded timeline, one line per event:

- the alert;
- each tool call, with its status and one-line result;
- model notes;
- the diagnosis and the confidence gate;
- the plan and the approval request and decision;
- the action (dry run or real), verification, rollback and kill switch;
- the report.

Sources:

- It tails `audit_logs/audit.jsonl`, and reads `incident_output/<id>/transcript.json` when a run finishes.
- `incident_output/<id>/run.log` is used only when there is no audit log, so nothing is printed twice.
- A missing file or a half-written line is retried, never fatal.

Options: `--from-start` (replay the audit log, then follow) and `--no-color`.

## Approval gate and kill switch

> **Provisional.** This describes the design being built for Checkpoint 3. Exact flag, status and action
> names are confirmed once that work lands; the code in `src/approval/` and `src/remediation/` is the source
> of truth.

**Approval gate.** A human approves every action. There is no auto-approve path in product code.

- Channels:
  - a y/N prompt in the terminal (the default, `--approve-via cli`);
  - a local approval page (`--approve-via chat`) at http://127.0.0.1:8765, bound to localhost, with a
    one-time token per action.
- Shown before approval:
  - the alert;
  - the diagnosis (root-cause service, category, summary), its confidence and the cited evidence;
  - the proposed action (type, target, reason) and its rollback;
  - a DRY RUN label.
- The approval page adds a countdown, Approve / Reject / Kill buttons, and a read-only "why?" chat. The chat
  answers only from the stored transcript and cannot approve or trigger anything.
- The operator approves the action and its rollback together.
- Reject, timeout, end of input or a non-interactive terminal all mean no action. The status is `REJECTED`
  and the decision is logged.
- In code, the action backend accepts only an approval object that the gate creates after a recorded human
  decision. It is tied to one action, single-use, and expires after about 120 seconds.

**Kill switch.**

- Engage it with any of these:

  ```bash
  touch .kill_switch                  # sentinel file (KILL_SWITCH_FILE); remove it to disengage
  export KILL_SWITCH_ENABLED=true     # environment variable
  ```

  The approval page's Kill button also works: it creates the sentinel and counts as a reject.
- It is checked three times: when the action is planned, right after approval, and immediately before the
  action is sent.
- When engaged, nothing runs: the status is `BLOCKED_BY_KILL_SWITCH`, and a `KILL_SWITCH` event is logged.
- `.kill_switch` is git-ignored.

**Actions.**

- The allowlist, until the organisers' catalog replaces it:
  - restart a service;
  - throttle the load generator;
  - scale a service (Kubernetes only);
  - toggle a feature flag through the Action API only. The agent never guesses a flag name and never reads
    flag state.
- A deterministic planner maps one diagnosis to one action plus its rollback.
- No action is proposed when the agent escalates, confidence is low, the target is excluded or there is no
  rollback.
- **Dry run is the default** (`DRY_RUN_MODE=true`): the dry-run backend records what it would send and
  makes no network call.
- **The real Action API backend is BLOCKED.** The organisers' contract (URL, auth, payloads, settle time)
  hasn't arrived, and nothing is invented in its place.
- The agent never edits flagd or `demo.flagd.json` and never uses the Feature Flags UI.

**Verification.**

- Before approval, a baseline of the target is recorded: error rate, p95 latency, request rate and
  container state.
- After the action and a settle window, a fresh snapshot is compared with that baseline.
- The service counts as recovered when all of these hold:
  - the error rate is below max(1%, half the baseline);
  - p95 latency is at most 1.2× the baseline;
  - the container is running.
- Outcomes:
  - recovered: the incident is resolved;
  - not recovered: the pre-approved rollback runs and the incident escalates;
  - no data: it escalates, with no rollback.
- **A dry run is never reported as a verified recovery** (`NOT_VERIFIED_DRY_RUN`). Live recovery can't be
  verified until the Action API contract arrives.
- The report gets a timeline, the action taken (including any rollback), the before/after verification,
  prevention advice and the path to the audit log.

**Demo commands (provisional).**

```bash
.venv/bin/python -m src.agent --alert "<alert text>"                       # full loop, dry run; answer y
.venv/bin/python -m src.agent --alert "<alert text>" --approve-via chat   # same, approve in the browser
.venv/bin/python scripts/run_demo.py --scenario checkout                   # dry-run demo; answer y (N to reject)
.venv/bin/python scripts/run_demo.py --test-kill-switch                    # kill-switch demo
```

## Evaluation harness

```bash
FAULTCTL_CMD="<organisers' faultctl>" .venv/bin/python -m src.agent.eval_harness cases.json
.venv/bin/python -m src.agent.eval_harness cases.json --no-inject --only <id>   # incident already active
```

- Injection and reset go only through the official `faultctl`. Without `FAULTCTL_CMD` the harness stops
  with a BLOCKED message.
- Expected answers are read only by the harness; the agent sees the alert text alone.
- Outcomes: `PASS`, `FAIL`, `ESCALATED`, `NO_DIAGNOSIS`, `FAIL_INVALID_CITATIONS`, `ERROR_SCHEMA`,
  `ERROR_MODEL`, `ERROR_INFRA`.
- Results go to `incident_output/eval-<stamp>/results.json` and `summary.json`.

## Tests

```bash
.venv/bin/python -m pytest -q
```

Tests use scripted model sessions and fixtures, so they need no API key and no running demo.

## Known limitations

- Free-tier models only: about 50 requests a day (roughly 4 live investigations), and free providers may log
  prompts. Only demo telemetry is sent.
- **The Checkpoint 3 rehearsal is a replay.** It feeds recorded real transcripts through the pipeline and is
  labelled `REPLAY`. Nothing replayed is claimed as a live diagnosis or as a verified recovery.
- `deploy_history` has no source and always returns `source_unavailable`.
- `dependency_map` is the static demo topology, not live-observed.
- The Jaeger Monitor tab shows "No Data" for `accounting`; not yet resolved.
- `system_overview` compares with the same window 30 minutes earlier, so right after a stack restart there is
  no baseline.
- Still BLOCKED, waiting on the organisers: the official `faultctl`, the practice incidents, the Action API
  contract and the official report schema. Until they arrive, actions run on the dry-run backend and no
  accuracy figure can be claimed.
- The report follows the team schema in `config/incident_schema.json` until the official one is available.

## Documentation

- [Architecture overview](docs/ARCHITECTURE_OVERVIEW.md): one page covering components, tools, decisions and
  safety.
- [Agent internals](docs/AGENT.md): files, guards and API assumptions.
- [Evaluation note](docs/EVALUATION_NOTE.md): what we can and cannot claim.
- [Team form draft](docs/TEAM_FORM.md): tools, models and libraries used.
- [Action API specification](docs/ACTION_API_SPECIFICATION.md): the contract items needed from the organisers.
- [Architecture & design](docs/ARCHITECTURE.md), [Decisions](docs/DECISIONS.md), [Setup](docs/SETUP.md),
  [Repository audit](docs/REPOSITORY_AUDIT.md), [Roadmap](docs/IMPLEMENTATION_ROADMAP.md).

## Repository structure

```text
bosch-incident-zero/
├── src/
│   ├── agent/          # LLM wrapper, tools, agent loop, guards, report, eval harness
│   ├── analysis/       # deterministic rule-based root-cause analyzer (no LLM)
│   ├── approval/       # human approval gate and safety pipeline
│   ├── remediation/    # kill switch, action layer, verification
│   ├── telemetry/      # Prometheus, Jaeger, OpenSearch clients
│   ├── models/         # data models
│   └── config.py       # settings from the environment and .env
├── config/             # incident_schema.json, default_config.yaml
├── scripts/            # verify_environment.py, run_demo.py, watch_run.py
├── docs/
└── tests/
```
