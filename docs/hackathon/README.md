# Incident Zero: team workflow index

Start here. This folder and the `.claude/` and `.cursor/` folders hold everything the team's AI agents need for the hackathon.

## Read first (every member, once)
1. [RULES.md](RULES.md): binding workflow and hackathon hard rules. Breaking the hard rules can disqualify the team.
2. [TEAM_CONTEXT.md](TEAM_CONTEXT.md): the problem, scoring, timeline, and architecture.
3. [REPO_SETUP.md](REPO_SETUP.md): one-time setup, including branch protection and git identity.
4. [interfaces.md](interfaces.md): shared tool and safety contracts. Changing these needs an `interface-change` issue.

## Setup (each teammate, once)
```bash
git config user.name "Your Name"; git config user.email "you@example.com"   # your own identity
bash scripts/setup-hooks.sh
```
The hooks block commits to `main`, staged secrets, and staged flag-config reads. They are opt-in because `setup-hooks.sh` sets `core.hooksPath`.

## Daily loop
```
/start-issue <n>  →  plan  →  code  →  /verify-change  →  /check-rules  →  /open-pr  →  teammate review  →  squash merge
```

## What lives where

| Path | What it is | Used by |
|---|---|---|
| `.claude/settings.json` | Shared permissions: denies pushes to `main` and `--no-verify`; asks before pushes and flagd reads | Claude Code |
| `.claude/skills/<name>/SKILL.md` | Reusable procedures: start-issue, plan-change, verify-change, open-pr, check-hackathon-rules, add-readonly-tool, incident-report | Claude Code (auto or by name) |
| `.claude/agents/<name>.md` | Subagents: `safety-reviewer` (read-only) and one builder per module | Claude Code |
| `.claude/commands/<name>.md` | Slash commands: `/start-issue`, `/verify-change`, `/check-rules`, `/open-pr` | Claude Code |
| `.cursor/rules/team-workflow.mdc` | Always-on Cursor rule that points to RULES.md | Cursor |
| `docs/hackathon/` | Rulebook, context, setup, interface contracts, and issue and PR templates | Everyone |
| `scripts/hooks/`, `scripts/setup-hooks.sh` | Git hooks that enforce branch, secret, and flag-read rules | Git |

## Module ownership

Each builder agent is scoped to one module. Changes in another person's folder need that person's review.

| Module | Folder | Agent | Owner |
|---|---|---|---|
| Platform and tooling | `oncall/platform/` | `platform-builder` | _fill in_ |
| Telemetry tools | `oncall/tools/` | `tools-builder` | _fill in_ |
| Agent brain | `oncall/agent/` (see note) | `agent-brain-builder` | _fill in_ |
| Safety and action | `oncall/safety/` | `safety-builder` | _fill in_ |
| Eval, reports, docs | `eval/`, `reports/`, `docs/hackathon/` | `eval-docs-builder` | _fill in_ |

**Note:** our code lives only in `oncall/`. The demo's `src/` is not ours to change.

**Note on the upstream rules:** the repo-level [AGENTS.md](../../AGENTS.md) covers OpenTelemetry Demo contributions and still applies. It says AI agents may post only text that a human wrote or approved verbatim, and it requires `Assisted-by:` trailers instead of `Co-authored-by:`. The skills in `.claude/skills/` follow both rules.

## Templates
- PR: [templates/pull_request_template.md](templates/pull_request_template.md). Use it for hackathon PRs. The repo's own `.github/PULL_REQUEST_TEMPLATE.md` is for upstream PRs.
- Issues: [templates/issue_feature.md](templates/issue_feature.md) and [templates/issue_bug.md](templates/issue_bug.md)
