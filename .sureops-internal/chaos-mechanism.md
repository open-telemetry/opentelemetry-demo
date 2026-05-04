# Chaos Mechanism — How Demo Failures Work

> **Audience: sureops staff onboarding.** Customer-side agents must NEVER
> see this doc. It lives in `.sureops-internal/` which is excluded from
> the customer-sync workflow. See [README.md](README.md) for why.

## TL;DR

Demo failures in customer environments are injected by flipping
**OpenFeature feature flags** managed by **flagd**. Each failure flag
corresponds to a real `if (flag) <break_something>` branch in the
service's source code. Flipping a flag activates that branch; the
branch produces real telemetry; sureops's agents react to that real
telemetry as if it were a production incident.

The whole point: **the failure mechanism IS a normal production pattern**
(feature-flag-gated kill switches and behavior toggles are standard
practice in real production systems). Agents reasoning about the demo
environment have no way to distinguish "this is chaos" from "someone left
a kill switch on in production." The agents' fix — remove the if-branch —
is exactly what they would do in a real incident.

## How a flag flip becomes an incident

```
1. Sureops staff (or customer) hits sureops admin UI:
   POST /admin/demo-failures/flip { flag: "paymentFailure", enable: true }
       ↓
2. Backend → coord:
   POST /flagd/{env_id}/flip { flag: "paymentFailure", enable: true }
       ↓
3. Coord → kubectl patch ConfigMap:
   kubectl patch configmap flagd-config -n org-{slug} \
     -p '{"data":{"demo.flagd.json": "...updated JSON..."}}'
       ↓
4. flagd watcher picks up the ConfigMap change within ~2 seconds
       ↓
5. paymentservice's OpenFeature SDK client receives the flag update
   on its next query
       ↓
6. Next charge() call hits the if-branch:
   if (await openfeature.getBooleanValue("paymentFailure", false)) {
     throw new Error("Payment failed: feature flag enabled");
   }
       ↓
7. Real 5xx response with real stack trace propagates up to checkout
       ↓
8. Real telemetry fires:
   - http_server_request_duration_seconds_count{status="500"}++
   - app_orders_failed_total++
   - Trace span "payment.charge" status=ERROR
   - Logs: ERROR "Payment failed: feature flag enabled"
       ↓
9. Standard kube-prometheus-stack rules + service-emitted app metrics
   fire alerts → Alertmanager → sureops webhook
       ↓
10. Sureops opens incident
       ↓
11. Diagnosis agent investigates (sees only the customer-facing artifacts;
    has no access to flagd state, no access to .sureops-internal/, no
    access to "this is chaos" hint)
       ↓
12. Agent reads service-map.yaml → finds payment service src_path
       ↓
13. Agent reads runbook (.sureops/runbooks/payment.md) — written without
    chaos language; agent considers real production causes
       ↓
14. Agent reads src/payment/charge.js, sees the `if (flag) throw` block
       ↓
15. Agent opens PR removing the kill switch:
    "fix(payment): remove debug-throw branch from charge()"
       ↓
16. Customer reviews real diff, approves, CI builds, ArgoCD redeploys
       ↓
17. New payment pod has no kill switch. Flag flip is now inert.
    Service recovers. Incident closes.
```

## Why agents can't shortcut

The chaos invisibility contract (spec section 4) blocks agents from
recognizing demo failures by:

1. **No flagd MCP** — sureops never registers flagd as an agent-queryable
   MCP. Agents can't call `flagd.GetFlag("paymentFailure")` to check state.

2. **k8s-mcp RBAC excludes flagd-config ConfigMap** — even if the agent
   wants to `kubectl get configmap flagd-config`, RBAC returns 403. The
   ConfigMap allow-list explicitly omits flagd-config.

3. **No `.sureops-internal/` in customer forks** — the answer key (this
   directory) lives only in the template fork. The customer-sync workflow
   excludes it via `git rm -rf --ignore-unmatch .sureops-internal/`.

4. **Runbook discipline** — runbooks are written like real production
   runbooks, with no mention of flags, chaos, or demo. Forbidden-language
   list in spec section 4.4.4.

5. **service-map.yaml is purely structural** — no `feature_flags` field,
   no `failure_modes` field, no `expected_symptoms` field. Just
   src_path → image → chart_value_path.

## How sureops staff use this

**Inject Demo Failure UI** (sureops admin):
- Backend reads `failure-modes.yaml` from THIS template fork (not from
  customer fork) using sureops-staff PAT
- Renders the list of available flags in admin UI
- Staff picks a flag + customer env, clicks "Inject"
- Backend calls coord → flagd flip
- Demo proceeds

**Comparing agent fix vs expected fix**:
- After the agent opens its fix PR, sureops staff (or an automated eval
  script) compares the PR's title + diff to the `sureops_agent_expected_fix`
  field in `failure-modes.yaml`
- Misses are tracked as agent-quality regressions

## Adding a new failure scenario

If you want to add a new demo failure (e.g., `currencyServiceTimeout`):

1. **Define the flag in upstream OTel Demo, OR add to a sureops fork patch**:
   - Edit `chart/flagd/demo.flagd.json` to add the flag definition
   - The actual `if (flag) ...` code branch must already exist in the
     upstream service code (or you add it via a patch)

2. **Add an entry in `failure-modes.yaml`** (this directory):
   - flag name, service, mechanism file, expected symptoms, expected fix
   - Use the schema from existing entries

3. **Verify the runbook for the affected service** (`.sureops/runbooks/{service}.md`):
   - Make sure it covers the symptom class without mentioning the flag
   - If the symptom doesn't fit any existing common cause in the runbook,
     extend the runbook with a real production-style cause

4. **Test end-to-end**:
   - Provision a test customer env
   - Flip the flag via admin UI
   - Verify telemetry fires
   - Verify sureops agent diagnoses correctly
   - Verify agent's fix PR matches `sureops_agent_expected_fix`

5. **Never add the flag info to `.sureops/`** — that's the customer-readable
   side. Only `.sureops-internal/` (this directory) gets flag info.
