# Eval harness (F17)

Runs the agent on recorded scenarios and scores it against `expected.yaml`.

```bash
python -m eval.run_eval                         # all scenarios, offline replay
python -m eval.run_eval --scenarios baseline,scenario-06 --pause 30
python -m eval.run_eval --live --scenarios scenario-06   # inject by hand first
python -m eval.run_eval --fail-on-red            # exit non-zero if any RED verdict
```

- Offline replay reads `oncall/tests/fixtures/<scenario>/`, recorded with
  `python -m oncall.tools.record --scenario <name>` while the fault was injected
  with `scripts/faultctl`.
- `expected.yaml` is the only place the answers live. Nothing under `oncall/`
  may read it (CI `rules` job).
- Scenarios run one at a time with `--pause` seconds between them: the Groq
  free tier rate-limits.

Scoring per scenario:

| verdict | score |
|---|---|
| component and category right (or an accepted alternative) | 1.0 |
| component right, category wrong | 0.5 |
| escalated, right component in affected services or alternatives | 0.5 |
| baseline: escalated instead of no_action | 0.5 |
| RED: confident act with the wrong component, or on the healthy baseline | 0 |
| RED: no_action on a real fault (missed incident) | 0 |
| RED: report not schema-valid | 0 |

Output: `eval/results/summary.md` (table, total, RED count, calibration of
confidence bucket vs mean score) and one JSON per scenario in
`eval/results/` (gitignored). `--fail-on-red` makes the command exit non-zero
when any scenario gets a RED verdict, so the harness can gate a CI step on
confident misdiagnoses.
