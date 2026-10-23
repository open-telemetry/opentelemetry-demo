---
name: start-issue
description: Start work on a GitHub issue for the Incident Zero hackathon. Reads the issue, checks acceptance criteria, syncs main, and creates a correctly named branch. Use when the user gives an issue number or says to start, pick up, or begin an issue.
---

# Start an issue

Every change starts from one GitHub issue. Follow these steps in order.

## 1. Get the issue
- Require an issue number. If none is given, stop and ask the user to create one from `docs/hackathon/templates/issue_feature.md` or `issue_bug.md`. Offer to draft the text, but do not post it.
- Run `gh issue view <n> --comments`. Read the full body and comments.
- Note the goal, acceptance criteria, files in scope, and out of scope.

## 2. Check the issue is ready
- If acceptance criteria are vague or missing, stop and ask the user. Do not invent requirements.
- If the issue touches a shared interface (`docs/hackathon/interfaces.md`, the incident report schema, the Action API client's public functions, the orchestrator state object), it needs an `interface-change` label and owner approval before code. Say so and stop.
- If the module is another person's folder, say who owns it. Their review is needed.

## 3. Sync and branch
```bash
git status --short            # must be clean, or ask the user what to do with changes
git checkout main
git pull --rebase origin main
git checkout -b <type>/<issue-number>-<short-slug>
```
- Type is one of `feat`, `fix`, `docs`, `test`, `chore`, `refactor`.
- The slug is lowercase letters, digits, and hyphens.
- Example: `feat/12-prometheus-metrics-tool`.
- The pre-commit hook rejects any other pattern.

## 4. Hand off
- Confirm the branch name and the issue's acceptance criteria back to the user.
- Next step: the `plan-change` skill. Do not write code yet.

## Never
- Commit or push to `main`.
- Use `--no-verify`.
- Start code on an issue that has no concrete acceptance criteria.
