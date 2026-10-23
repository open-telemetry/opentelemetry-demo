---
name: start-issue
description: Start work on an entry in docs/hackathon/ISSUES.md for the Incident Zero hackathon. Reads the entry, checks acceptance criteria, syncs main, and creates a correctly named branch. Use when the user gives an F-number or NN or says to start, pick up, or begin an entry.
---

# Start an issue

Every change starts from one entry in `docs/hackathon/ISSUES.md` (GitHub Issues is disabled on the fork). Follow these steps in order.

## 1. Get the entry
- Require an F-number (for example F04). If none is given, or it isn't in `docs/hackathon/ISSUES.md`, stop and ask the user to add it. Offer to draft the text, but do not post it.
- Read the entry in `docs/hackathon/ISSUES.md` and its section in `docs/hackathon/FEATURES.md`.
- Note the goal, acceptance criteria, files in scope, and out of scope.

## 2. Check the issue is ready
- If acceptance criteria are vague or missing, stop and ask the user. Do not invent requirements.
- If the entry touches a shared interface (`docs/hackathon/interfaces.md`, the incident report schema, the Action API client's public functions, the orchestrator state object), it needs an `interface-change` entry in `docs/hackathon/ISSUES.md` and owner approval before code. Say so and stop.
- If the module is another person's folder, say who owns it. Their review is needed.

## 3. Sync and branch
```bash
git status --short            # must be clean, or ask the user what to do with changes
git checkout main
git pull --rebase origin main
git checkout -b <type>/<NN>-<short-slug>
```
- Type is one of `feat`, `fix`, `docs`, `test`, `chore`, `refactor`.
- NN is the two-digit number from `docs/hackathon/ISSUES.md`.
- The slug is lowercase letters, digits, and hyphens.
- Example: `feat/04-get-metrics`.
- The pre-commit hook rejects any other pattern.

## 4. Hand off
- Confirm the branch name and the issue's acceptance criteria back to the user.
- Next step: the `plan-change` skill. Do not write code yet.

## Never
- Commit or push to `main`.
- Use `--no-verify`.
- Start code on an issue that has no concrete acceptance criteria.
