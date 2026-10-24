---
name: plan-change
description: Write a short plan (files, public interfaces, tests) for an Incident Zero issue before any code is edited, and wait for a go-ahead when the plan touches a shared interface or another person's module. Use after start-issue, or whenever the user asks for a plan.
---

# Plan a change

Plan before code. The plan is short and goes back to the user.

## 1. Read first
- Read the issue, `docs/hackathon/RULES.md` sections 1 and 4, and `docs/hackathon/interfaces.md`.
- Read every file you expect to change, and every function you plan to call. Do not guess signatures, imports, or config keys.

## 2. Write the plan
Show the user this, in order:

1. **Files to create or change.** Stay inside the issue's scope. List any file outside the scope and say why it is needed.
2. **Public interfaces.** Give each new or changed function signature and JSON field exactly. Say whether it matches `docs/interfaces.md`.
3. **Tests.** Name the unit tests (happy path plus at least one failure or edge case) and the real run you will use. Name the offline bundle or live-demo command.
4. **Module owner.** Name the owner of each touched folder (`docs/hackathon/README.md`).
5. **Unknowns.** List what you do not know, and what you need from the user or a sample response.

## 3. Wait for a go when
- The plan touches a shared interface. Open an `interface-change` issue first.
- The plan changes another person's module folder.
- The plan has unknowns that change the design.

Otherwise, say "Plan ready, starting unless you object" and continue.

## Never
- Invent an endpoint, field, port, package, or response shape. If you do not know it, call the real thing or ask for a sample.
- Plan a state change outside the Action API. Plan a read of flagd for diagnosis. Both are hard-rule violations (`docs/hackathon/RULES.md` section 2.3).
