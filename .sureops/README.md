# `.sureops/` — Sureops agent contract files

This directory holds files that sureops's diagnosis and fix-PR agents read
when investigating incidents in your environment. It's the "agent contract":
a stable, structured handoff between your service code and sureops's
incident-response automation.

## Files

### `service-map.yaml`
Maps each service in `src/` to its source directory, container image,
chart values path, language, dependencies, and runbook. Agents use this
as the routing table — when an incident fires on service X, the agent
reads this file to know:
- where in `src/` the code lives
- which `chart/values.yaml` key controls the deployed image tag
- what runbook to consult first
- what services upstream/downstream might be implicated

### `runbooks/{service}.md`
Production-style runbook for each service. Symptoms first, common causes,
step-by-step triage. Written in the style of Google SRE Workbook runbooks.
Agents read these as their **first** step when investigating an incident
on a service — they shape the diagnosis prompt and constrain the
hypothesis space the agent considers.

## Editing guidance

- **Owned by sureops staff** (CODEOWNERS gate). If you want to update a
  runbook with site-specific knowledge for your team, file a PR — it'll
  go to sureops staff for review and merge.
- **The contract is additive**: the more accurate the runbook, the better
  sureops's agent diagnoses. Empty/sparse runbooks still work; the agent
  falls back to traces + logs + service-map alone.
- **Keep service-map.yaml structural**: don't add diagnostic hints, fix
  recipes, or symptom-to-root-cause mappings here. Those belong in the
  runbook for the relevant service.

## What sureops promises in return

When your service has an incident:
1. The diagnosis agent reads `service-map.yaml` to find the right service entry
2. It reads the matching runbook to seed its reasoning
3. It pulls relevant traces from your per-customer Tempo, logs from Loki,
   metrics from Prometheus
4. If a fix is identifiable in code, the fix-PR agent opens a draft PR
   against your fork on the relevant `src/{service}/` files (and bumps
   `chart/values.yaml` image tags as needed)
5. You review the PR like any other code change. Approve, merge, ArgoCD
   syncs, incident closes

The contract files in this directory are what make step 1 deterministic
instead of "agent guesses where to look."
