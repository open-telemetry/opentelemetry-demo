# Evaluation note

What we have measured, what we have not, and what we can honestly claim. Status as of 2026-10-24.

## Official evaluation: BLOCKED

None of the organisers' practice incidents has been run or scored, because these items are not yet on the
team machine:

- the official `faultctl` (needed to inject and reset faults);
- the list of practice incidents (or their offline bundles);
- the official incident report schema and template;
- the Action API contract (base URL, auth, action catalog, settle time).

The evaluation harness (`src/agent/eval_harness.py`) is ready for them. It refuses to run without
`FAULTCTL_CMD`, and it never touches flagd. Once those items arrive, a run is:

```bash
FAULTCTL_CMD="<organisers' faultctl>" .venv/bin/python -m src.agent.eval_harness cases.json
```

It writes `results.json` (expected and observed answers side by side) and `summary.json` (counts per outcome)
under `incident_output/eval-<stamp>/`.

## What has been run

| Run | What it shows | Limits |
|---|---|---|
| One live diagnosis (DEMO-002, Day 1) | The full Phase 1 → Phase 2 → guards path works against the live demo: payment named as root cause, checkout and its callers impacted, 5 of 5 citations valid, high confidence. | One run. The fault was turned on by a local edit to `demo.flagd.json`, which the rules forbid for official evaluation; that edit was never committed. |
| One unofficial harness run (`--no-inject`, Day 1) | PASS on the same active fault: payment / `dependency_unreachable`, 11 model requests for 9 tool calls. | Not an official incident. "PASS" only means it matched the answer we set ourselves. |
| Unit and integration tests | Guards, citation validation, confidence gate, attribution rule, telemetry clients, harness scoring and case validation, safety controls. | Tests use scripted model sessions and fixtures, not real incidents. |

## What we can claim

- The agent reaches a diagnosis from the alert text alone, using only read-only tools.
- Cited evidence is checked against stored tool results; invented trace IDs, values and log lines are rejected.
- Weak evidence lowers confidence and escalates instead of producing a confident wrong answer.
- Missing data is reported as missing, never as healthy.

## What we cannot claim yet

- Any accuracy figure. One run is an anecdote, not a rate.
- Performance on unseen incident types: CPU or memory exhaustion, latency without errors, queue lag,
  traffic spikes, combinations.
- Calibration: whether "high" confidence is right more often than "medium".
- Any verified recovery through the official Action API.

## Open questions for the mentors

- **Expected root cause for `paymentUnreachable`.** The organiser slides describe it as checkout calling a bad
  address so payment looks down. On that wording the scored answer might be **checkout** (bad configuration)
  rather than **payment**. The agent currently names payment. Changing it is a small, contained edit to the
  attribution rule.
- Whether our own OpenRouter key and model choice are allowed, or an organiser key must be used.

## Known gaps that affect results

- `deploy_history` has no source and always returns `source_unavailable`.
- `dependency_map` is the static demo topology, not live-observed.
- The Jaeger Monitor tab shows "No Data" for `accounting`; not yet resolved.
- `system_overview` compares with the same window 30 minutes earlier, so right after a stack restart there
  is no baseline.
