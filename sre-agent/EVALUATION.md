# Evaluation note

> Fill the practice table from `python -m agent.main eval` after running the practice incidents
> (`diagnose --expect <service>` or `respond --expect <service>` per incident). Be honest: stating a
> limitation costs nothing.

## Practice incidents (live, own laptop)

| # | Incident (faultctl) | Expected root cause | Agent said | Confidence | Status / outcome | Right? | Why / notes |
|---|---|---|---|---|---|---|---|
| 1 |  |  |  |  |  |  |  |
| 2 |  |  |  |  |  |  |  |
| 3 |  |  |  |  |  |  |  |
| 4 |  |  |  |  |  |  |  |
| 5 |  |  |  |  |  |  |  |
| 6 |  |  |  |  |  |  |  |
| 7 |  |  |  |  |  |  |  |
| 8 |  |  |  |  |  |  |  |
| 9 |  |  |  |  |  |  |  |
| 10 |  |  |  |  |  |  |  |

**Service accuracy:** _/10 · **Fault-type accuracy:** _/10 · **Confident-and-wrong:** _ · **Escalated:** _
**Full loop (alert → approved action → verified recovery):** incidents _

### Calibration (from `eval`)

| Stated confidence | Runs | Actually right |
|---|---|---|
| < 0.4 | | |
| 0.4–0.6 | | |
| 0.6–0.8 | | |
| ≥ 0.8 | | |

## Offline tests (synthetic recorded telemetry, `python -m tests.run`)

These are hand-made recorded tool results that mimic each fault class; they test the reasoning and the
safety controls, **not** live accuracy.

| Scenario | Expected | Result |
|---|---|---|
| payment application error (error origin + logs + metrics) | payment / application_error, diagnosed | pass |
| payment container stopped (checkout spans "Unavailable") | payment (callee, not checkout) / service_down | pass |
| valkey-cart stopped (cart "UnableToConnect") | valkey-cart / dependency_unavailable | pass |
| ad high CPU (latency + CPU vs baseline) | ad / high_cpu | pass |
| homepage traffic flood | frontend / traffic_flood → throttle_load | pass |
| healthy system with background noise | no_incident, no action | pass |
| LLM tool loop with one invented metric | invented item flagged unverified, −0.1 confidence | pass |
| LLM returns invalid output 3× | rule-based fallback, still correct | pass |
| no approval / non-allowlisted action / kill switch | refused / refused / blocked | pass |
| full loop approved → recovered; not recovered → rollback; rejected → nothing changed | as expected | pass |

## What it gets wrong / known weak spots
- (fill in from practice: e.g. latency faults with low traffic, combined faults, faults with no error spans)
