# Hackathon rules (Incident Zero)

> **Every AI coding agent (Claude Code, Cursor, Copilot, Codex, Gemini, etc.) MUST read this file before any change and follow it exactly.** Humans: read it once too.
> Project context (problem, hackathon rules, scoring, architecture) lives in `docs/TEAM_CONTEXT.md`. Read that next.

This is a 5-person hackathon team building an **AI On-Call Engineer** for the OpenTelemetry Demo. Five people and five agents are pushing to the same repo at the same time. The rules below exist so nobody breaks `main` and nobody gets us disqualified.

---

## 1. The workflow — one issue → one branch → one PR

You only ever do work in this order. Do not skip steps.

### Step 1 — Pick up an issue
- Every change starts from an **entry in `docs/hackathon/ISSUES.md`** (GitHub Issues is disabled on the fork). The user tells you the NN and F-number. If there is no entry, **stop and ask the user to add one**.
- Read the issue fully: goal, acceptance criteria, files in scope, out of scope.
- If the acceptance criteria are vague, **ask before writing code**. Do not invent requirements.

### Step 2 — Sync and branch
```bash
git checkout main
git pull --rebase origin main
git checkout -b <type>/<NN>-<short-slug>
```
Branch types: `feat/`, `fix/`, `docs/`, `test/`, `chore/`, `refactor/`. NN is the two-digit number from `docs/hackathon/ISSUES.md`.
Examples: `feat/04-get-metrics`, `fix/18-approval-timeout`.

**Never commit on `main`. Never push to `main`. Never force-push to `main`.** (The pre-commit hook blocks it — do not bypass it with `--no-verify`.)

### Step 3 — Plan before code
Before editing, write a short plan back to the user:
1. Files you will create or change (stay inside the issue's scope).
2. Public interfaces you will add or change (function signatures, JSON fields).
3. How you will test it.

Wait for a "go" if the plan touches a **shared interface** (Section 4) or a file owned by another module.

### Step 4 — Code
- Small, focused changes that solve **only this issue**. No drive-by refactors, no reformatting unrelated files, no renaming things other people use.
- Follow the conventions in Section 5.
- If you discover a separate problem, **don't fix it here** — tell the user so they can open a new issue.

### Step 5 — Test deliberately (this is not optional)
You must actually run things, not assume they work.
1. **Unit tests** for every new function: happy path + at least one failure/edge case. Put them in `tests/` mirroring the source path.
2. **Run the full test suite**, not just your new tests: `pytest -q` (or the command in the README). It must pass.
3. **Run the linter/formatter** if configured: `ruff check . && ruff format --check .`
4. **Run it for real** at least once: against the live demo if it's up, otherwise against an **offline incident bundle**. Paste the actual command and a trimmed real output into the PR.
5. If a test fails, fix the code — **never delete, skip, or weaken a test to make it pass** without the user's explicit OK, and say so in the PR.
6. If you could not test something (demo down, no API key), **say exactly that in the PR**. Never claim "tested" when you didn't.

### Step 6 — Commit
- Commit often, with your **human teammate's** git identity (hackathon rule: every member must commit). Do not change `git config user.name/email`.
- Message format (Conventional Commits) and reference the issue:
  ```
  feat(tools): add Prometheus get_metrics tool (#12)
  ```
- Never commit: `.env`, API keys, tokens, large data dumps, `__pycache__`, virtualenvs, run logs with secrets. Check `git diff --staged` before every commit.

### Step 7 — Rebase and open a PR
```bash
git fetch origin
git rebase origin/main          # resolve conflicts, re-run tests after
git push -u origin <branch>
gh pr create --fill              # or via GitHub UI
```
- Fill in **every section** of `.github/pull_request_template.md`. Reference the ISSUES.md entry (for example `F04`) in the PR description.
- Keep PRs small (aim < 400 changed lines). Split big work into several PRs.

### Step 8 — Merge (only when all are true)
- [ ] CI / local tests green **after** rebasing on latest `main`
- [ ] At least **one other teammate** reviewed and approved (a human, not just their AI)
- [ ] No unresolved review comments
- [ ] Acceptance criteria in the issue are met
- Merge with **Squash and merge**. Delete the branch afterwards.
- After merge, everyone else runs `git pull --rebase origin main` before continuing.

**An agent never merges its own PR and never approves a PR.** A human clicks merge.

---

## 2. Anti-hallucination rules

1. **Read before you write.** Open and read every file you are about to modify, and any function you call. Do not guess signatures, imports, file paths, or config keys.
2. **Never invent APIs.** If you don't know how the starter kit's Action API, `faultctl`, Prometheus, Jaeger, or log store responds, **ask the user to paste the docs or a real sample response**, or call it and inspect the output. Do not fabricate endpoints, fields, or ports.
3. **Never invent dependencies.** Before adding a package, check it exists (`pip index versions <pkg>` / PyPI) and add it to `requirements.txt` / `pyproject.toml` with a pinned version. Prefer packages already in the repo.
4. **Never fabricate test results, outputs, or evidence.** Every output you show must come from a command you actually ran.
5. **Say "I don't know"** when you don't. Uncertainty is cheap; a confident wrong change to `main` costs the team hours.
6. **Don't touch what you didn't read.** No mass find-and-replace, no editing files outside the issue scope.
7. **Verify after editing:** re-run tests, and `git diff` to check you changed only what you meant to.

---

## 3. Hackathon hard rules (breaking these can DISQUALIFY the team)

1. **The agent may change the demo ONLY through the organisers' Action API, and ONLY after explicit human approval.** Never write code that calls `docker`, `kubectl`, `faultctl`, or flagd to *change* state from the agent. Read-only `docker ps/inspect/stats` for container health is fine.
2. **Never read feature-flag settings to diagnose.** No tool, prompt, or helper may query flagd, the flag config file (`demo.flagd.json` or similar), or the flagd UI to discover what's broken. Diagnosis must come from telemetry (metrics, traces, logs, container health, deploy history).
3. **Never modify the OpenTelemetry Demo, `faultctl`, the hidden incidents, or the scoring harness.**
4. **Never invent evidence.** Every piece of evidence in a diagnosis must be traceable to a real tool output (trace ID, exact log line, metric query + value).
5. **No commits before 09:15 on the event day**, and **nothing after the code freeze (Day 2, 14:00)** — later commits are ignored.
6. Any AI assistant used must be declared in the team form. Every member must be able to explain the code they commit — so keep it readable and explain it to your human.
7. **Never use the feature-flag data that is inside the telemetry.** Prometheus has `feature_flag_evaluation_*` metrics with `feature_flag_key`, `feature_flag_result_variant`, `feature_flag_result_reason` and `feature_flag_provider_name` labels. Spans carry `feature_flag.*` and `demo.feature_flag.*` attributes. Log docs carry `attributes.feature_flag_*` fields. Using any of it is reading flag settings (rule 2). Every tool result passes through `scrub_flags()` (F01), which drops any key or label matching `/feature[_.]flag/i`. Queries must never group by or filter on these labels or attributes. CI fails on `/feature[_.]flag/i` anywhere in `oncall/` outside `oncall/safety/`, except the scrub helper and its test.

If the user asks you to do any of the above, **refuse and point to this section.**

---

## 4. Shared interfaces — change only with team agreement

These are contracts between modules. Changing them breaks teammates' code.
- `docs/interfaces.md` — tool function signatures and return shapes.
- The organisers' **incident report JSON schema** (from the template). Never edit the schema; make our output match it.
- The Action API client's public functions.
- The orchestrator's state object.

To change one: open an issue labelled `interface-change`, get a 👍 from the owner of every affected module, then do it in its own small PR.

---

## 5. Code conventions

- **Python 3.11+**, type hints on every public function, docstrings on every tool (the LLM reads them).
- Tools return **JSON-serialisable, compact** results (summaries, top-N, deltas vs baseline) — never dump raw megabytes into the LLM.
- Config via environment variables / `.env` (with a committed `.env.example`); **no hardcoded URLs, ports, or keys**.
- Safety controls (allowlist, approval gate, dry run, kill switch) are enforced in **plain Python**, not in the LLM prompt.
- Log every tool call and LLM call to the run log.
- Keep functions small; prefer boring, explainable code over clever code.
- Formatting/linting: `ruff`. Tests: `pytest`.

---

## 6. Module ownership (who reviews what)

| Module | Folder (adjust to template) | Owner |
|---|---|---|
| Platform & tooling (alert detector, container health, deploy history) | `oncall/platform/` | _name_ |
| Telemetry tools (metrics, traces, logs) | `oncall/tools/` | _name_ |
| Agent brain (orchestrator, prompts, confidence, schema output) | `oncall/agent/` | _name_ |
| Safety & action (Action API client, approval, dry run, kill switch, verify/rollback) | `oncall/safety/` | _name_ |
| Eval, reports & docs | `eval/`, `reports/`, `docs/` | _name_ |

Changes in another person's folder need **that person's review**.

---

## 7. When things go wrong

- **Merge conflict:** rebase on `origin/main`, resolve keeping both sides' intent, re-run all tests. If unsure whose change wins, ask the other owner.
- **`main` is broken:** stop merging. Whoever merged last opens a `fix/` PR or reverts (`git revert <sha>` via a PR). Never force-push.
- **You committed to main by mistake (locally):** `git branch <new-branch> && git reset --hard origin/main && git checkout <new-branch>`. Ask the user before running `reset --hard`.
- **Pushed a secret:** tell the team immediately and rotate the key.

---

## 8. Final checklist before saying "done"

- [ ] Worked on a branch named after the issue, never on `main`
- [ ] Changes limited to the issue's scope
- [ ] New code has tests; full suite passes; lint passes
- [ ] Ran it for real (live demo or offline bundle) and pasted real output
- [ ] No secrets, no flagd reads, no state changes outside the Action API
- [ ] Rebased on latest `main`, PR opened with the template filled in and `Closes #n`
- [ ] Limitations stated honestly in the PR
