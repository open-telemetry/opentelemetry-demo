---
name: verify-change
description: Verify an Incident Zero change before it goes in a PR. Runs the full test suite, linter, and formatter, does one real run against the live demo or an offline bundle, and reports the real output and anything untested. Use when the user asks to test, verify, or check a change, or before open-pr.
---

# Verify a change

Nothing counts as done until it has been run. Never claim "tested" without the output to show.

## 1. Check the diff is in scope
```bash
git status --short
git diff origin/main...HEAD --name-only
```
- Every file should be in the issue's scope. Stop and report anything outside it.

## 2. Unit tests for new code
- Confirm each new function has tests in `tests/`, mirroring the source path.
- Each function needs a happy path and at least one failure or edge case.
- If a test is missing, write it before running the suite.

## 3. Full suite and lint
```bash
pytest -q
ruff check .
ruff format --check .
```
- The full suite must pass, not only the new tests.
- If a test fails, fix the code. Never delete, skip, or weaken a test without the user's explicit OK, and say so in the PR.

## 4. Real run
- Run it against the live demo if it is up, or against an offline incident bundle. Use the command the README or `docs/hackathon/REPO_SETUP.md` gives.
- Capture the exact command and a trimmed real output.
- If the demo is down or there is no API key, say exactly that. Do not fake the run.

## 5. Check the diff again
```bash
git diff --staged
git diff
```
- Only the intended changes. No `.env`, keys, `__pycache__`, or large dumps.

## 6. Report
Give the user a short table:

| Check | Command | Result |
|---|---|---|
| Unit tests | `pytest -q tests/...` | pass or fail, with the counts |
| Full suite | `pytest -q` | |
| Lint | `ruff check .` | |
| Format | `ruff format --check .` | |
| Real run | the command used | the trimmed output |

Then list anything not tested and why. These go into the PR's "Not tested" section.

## Never
- Claim a check passed when it did not run.
- Paste output you did not produce in this session.
