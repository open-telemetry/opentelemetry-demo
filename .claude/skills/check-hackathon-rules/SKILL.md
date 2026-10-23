---
name: check-hackathon-rules
description: Check the current branch's changes against the Incident Zero hard rules and PR safety checklist (no flagd reads, Action API only, no invented evidence, no secrets, scope, commit timing). Use before opening a PR, or when the user asks whether a change is safe or rule-compliant.
---

# Check hackathon rules

This is the checklist. The `safety-reviewer` agent runs it read-only. Use this skill to run it yourself.

## Procedure
1. Get the diff:
   ```bash
   git diff origin/main...HEAD --name-only
   git diff origin/main...HEAD
   ```
2. Check each rule. Quote `file:line` for every hit.

| # | Rule | How to check |
|---|---|---|
| H1 | No system changes outside the Action API | Search added lines for `docker`, `kubectl`, `faultctl`, `flagd` used to change state. Read-only `docker ps`, `inspect`, `stats` are allowed. |
| H2 | No reads of flagd or flag config to diagnose | Search added lines outside `oncall/safety/` and `tests/` for `flagd`, `demo.flagd.json`, `flagd-ui`, `/feature/`, `ofrep`. |
| H3 | No edits to the demo, `faultctl`, hidden incidents, or scoring harness | Check the changed-file list for upstream demo paths or the harness. |
| H4 | No invented evidence | Check that every evidence item comes from a tool call, not a literal string. |
| H5 | Commit timing | `git log origin/main..HEAD --format='%ad %s'`. Flag anything before 09:15 on event day or after the Day 2 14:00 freeze. |
| S1 | No secrets | Search added lines for `sk-`, `sk-ant-`, `AKIA`, `ghp_`, `BEGIN PRIVATE KEY`. Check for `.env`, `*.pem`, `id_rsa`, `credentials.json`. |
| S2 | No generated junk | No `__pycache__`, `.venv`, `node_modules`, large data files. |
| S3 | Scope | Changed files match the issue's "Files in scope". |
| S4 | Interfaces | Changes to `docs/hackathon/interfaces.md`, the report schema, the Action API client's public functions, or the orchestrator state object have an `interface-change` issue. |
| S5 | Ownership | Changed folders are the author's module, or the owner has reviewed. |
| S6 | Commit authorship | `git log origin/main..HEAD --format='%an <%ae>'` shows a human. No `Co-authored-by:` trailer. |

## Report
- Give a table: rule, result (pass, fail, or not checked), and `file:line` for each failure.
- Verdict: **PASS**, **BLOCK** (any H-rule failure), or **REVIEW** (unclear).
- Say plainly which checks you could not run.

## Never
- Mark a rule as passed without checking it.
- Fix violations silently. Report them and let the user decide.
