# Demo runbook

How to start everything, operate it, and give the demo. All commands below run from
`team8-otel-demo/` (the demo) or `team8-otel-demo/bosch-incident-zero/` (the agent), as marked.

## What runs where

| Piece | What it is | Where |
|---|---|---|
| OpenTelemetry demo | The shop plus Jaeger, Prometheus, OpenSearch, Grafana, Locust, flagd (28 containers) | http://localhost:8080 |
| Incident hub | Always-on page: stored incidents, read-only "why?" chat, jumps to a waiting approval | http://localhost:8799 |
| Alert watcher | Checks Prometheus every 30 s and starts the agent by itself when a service is unhealthy | Terminal (starts the hub too) |
| Agent | Runs once per alert: investigates, diagnoses, proposes one action, asks a human | Started by the watcher |
| Approval page | Opened by an agent run for one action; one-time token; closes after the decision | The hub sends you there |
| Run watcher | Colour-coded live timeline of every event | Terminal |

## 1. Start everything, in order

1. **Docker Desktop** must be running.
2. **Demo** (from `team8-otel-demo/`). It takes a few minutes the first time.

   ```bash
   make start
   ```

3. **Check the environment** (from `bosch-incident-zero/`). Expect five `[OK]` lines and `5/5 reachable`.

   ```bash
   .venv/bin/python scripts/verify_environment.py
   ```

4. **Check the live tools without the LLM.** Expect `ok` for every tool except `deploy_history`
   (`source_unavailable`: the organisers have not supplied that source).

   ```bash
   .venv/bin/python -m src.agent --tools-only
   ```

5. **Start the alert watcher and the hub** in its own terminal and leave it running. One command starts both.

   ```bash
   .venv/bin/python -m src.alerting
   ```

   It fires when a service's error rate is at least 5% with at least 3 failed requests in 5 minutes, or its
   p95 latency reaches 5000 ms, on 2 checks in a row. It then starts one agent run with an alert such as
   "Error rate above 5% on checkout", shows a macOS notification, and writes the run's output to
   `audit_logs/auto_runs/`. Only one run happens at a time, a service fires again only after it recovers
   (or after an hour if still broken), and at most 4 runs start per day to stay within the free LLM quota.
   Thresholds are flags: `--error-rate`, `--min-errors`, `--p95-ms`, `--consecutive`, `--max-runs-per-day`,
   `--approval-timeout` (default 900 s).

6. **Start the run watcher** in a second terminal and leave it running.

   ```bash
   .venv/bin/python scripts/watch_run.py
   ```

7. **Open the UIs**: http://localhost:8799 (hub), http://localhost:8080/jaeger/ui/ (traces) and
   http://localhost:8080/feature/ (fault flags).

## 2. Run an incident

1. **Inject a fault.** On http://localhost:8080/feature/ set `paymentUnreachable` to `on`. (The organisers'
   `faultctl` replaces this once supplied.)
2. **Wait for the alert.** Within a few minutes (checkout gets little traffic) the watcher prints `FIRING:` and
   starts the agent. Nothing to type. The alert text is all the agent gets; each tool call appears in the
   run watcher. To start a run by hand instead:

   ```bash
   APPROVAL_TIMEOUT_SECONDS=600 .venv/bin/python -m src.agent --alert "Error rate above 5% on checkout" --approve-via chat --dry-run
   ```

3. **Approve or reject** on http://localhost:8799. An open hub tab switches to the approval page by itself.
   Approval is never automatic: no decision within the timeout means no action.
   Read the diagnosis and evidence, ask "why?", then click **Approve**, **Reject** or **Emergency kill switch**.
4. **Read the result.** The terminal prints the brief; files are in `incident_output/<incident-id>/`:
   `report.md`, `report.json`, `transcript.json`, `run.log`. Safety events also go to `audit_logs/audit.jsonl`.
5. **Remove the fault**: set `paymentUnreachable` back to `off`.

### When the LLM quota is used up: replay

The free OpenRouter tier allows 50 requests a day per account (resets 00:00 UTC, 05:30 IST); one live run
uses about 10. When it is used up the agent switches to the Gemini free tier (`LLM_FALLBACK_*` in `.env`);
the model that answered is shown in the `DIAGNOSIS` event. Only if both are used up does it escalate with a
429. The approval, action and verification steps still run from a recorded diagnosis, with no LLM call:

```bash
APPROVAL_TIMEOUT_SECONDS=600 .venv/bin/python scripts/run_demo.py --replay incident_output/INC-20261023-121354/transcript.json --approve-via chat
```

## 3. Operating it

- **Approval is always a human decision.** Reject, timeout, Ctrl+C or a non-interactive terminal all mean
  no action. `--approve-via cli` asks y/N in the terminal instead of the page.
- **Dry run is the default.** The action is recorded, not sent, so verification reports
  `NOT_VERIFIED_DRY_RUN` and the report `MITIGATION_UNVERIFIED`. A live action needs the organisers' Action API.
- **Kill switch.** Engage with `touch .kill_switch` (or `export KILL_SWITCH_ENABLED=true`, or the page's Kill
  button); `rm .kill_switch` disengages it. While engaged every action is `BLOCKED_BY_KILL_SWITCH`.
  Test it without the LLM:

  ```bash
  .venv/bin/python scripts/run_demo.py --replay incident_output/INC-20261023-121354/transcript.json --test-kill-switch
  ```

- **Retries.** Only a measured non-recovery on a live backend starts another attempt (default 3, cap 5,
  `--max-attempts`), and each attempt asks a human again.
- **Tests**: `.venv/bin/python -m pytest -q`.

## 4. Demo script (about 10 minutes)

1. **Healthy system (1 min).** Show the shop, Jaeger and the hub. "The agent only reads telemetry; it cannot
   change anything without a human."
2. **Break it (1 min).** Turn on `paymentUnreachable`. Show failed checkouts in the load generator or Jaeger.
3. **Investigate (2–3 min).** Nobody starts anything: the alert watcher notices and starts the agent with only
   the alert text. Narrate the run watcher: system overview,
   checkout metrics, error traces, "checkout's calls to payment never reached payment".
4. **Diagnosis (1 min).** Root cause payment (dependency unreachable), impacted checkout, each citation
   checked against real tool output, confidence gated.
5. **Human approval (2 min).** The hub switches to the approval page. Point out the DRY RUN badge, the
   NO ROLLBACK warning and the countdown. Ask the chat "why payment and not checkout?". Approve.
6. **Outcome (1 min).** Show the timeline and `report.md`. Dry run, so recovery is not claimed.
7. **Safety (1 min).** Run the kill-switch test and show `BLOCKED_BY_KILL_SWITCH`.
8. **Clean up.** Turn the flag off.

If the quota is used up, do step 3 with the replay command and say so: the recorded diagnosis is a real
live run against the same fault.

## 5. Troubleshooting

| Symptom | Fix |
|---|---|
| `429 free-models-per-day` on every model | OpenRouter and Gemini quotas both used up; replay, or wait for the reset |
| Agent exits with code 2 | No LLM configured in `.env` |
| Checkout still fails after the flag is off | After a flagd restart checkout keeps its cached flag: `docker restart checkout` |
| Hub says "Address already in use" | Something holds 8799: `lsof -iTCP:8799 -sTCP:LISTEN` |
| Watcher never fires | Check the thresholds against the numbers in Grafana; low-traffic services need `--min-errors` failures |
| Watcher says "daily cap ... reached" | 4 runs today already; raise `--max-runs-per-day` only if the LLM quota allows |
| Auto run did nothing visible | Its output is in `audit_logs/auto_runs/` |
| Hub chat says "LLM unavailable" | Same quota or `.env` issue; the evidence panel still works |
| Environment check below 5/5 | Demo still starting; wait and rerun |

## 6. Shut down

Stop the alert watcher (and with it the hub) and the run watcher with Ctrl+C, then from `team8-otel-demo/`:

```bash
make stop
```
