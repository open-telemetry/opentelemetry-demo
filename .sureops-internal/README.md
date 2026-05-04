# `.sureops-internal/` — SUREOPS STAFF ONLY

> ⚠️ **THIS DIRECTORY IS EXCLUDED FROM THE CUSTOMER-SYNC WORKFLOW.**
> It exists ONLY in the template fork (`sureops-private-beta/sample-app-otel-demo`)
> and **is never copied into per-customer forks**.

## Why this directory exists

Files here document the demo's failure-injection mechanism in a way that
would **break the demo if customer-side sureops agents could see them**.

The chaos-invisibility contract (see [docs/backend/22-sample-stack-otel-demo-spec.md](https://github.com/codehaus-ai/sureops-frontend-v3/blob/main/docs/backend/22-sample-stack-otel-demo-spec.md) section 4 in the sureops repo) requires that sureops's diagnosis and fix-PR agents perceive demo failures as real production bugs. If an agent reads `.sureops-internal/failure-modes.yaml` and sees "this flag injects a payment failure → just disable the flag," the agent's "fix" becomes theatrical (disable the chaos) rather than legitimate (find and patch the underlying bug).

Keeping this directory out of customer forks is what makes that contract enforceable.

## Files

### `failure-modes.yaml`
The answer key. Maps each demo failure flag → service → in-code mechanism →
expected observable symptoms → expected agent fix path. Used by sureops
staff during guided demos and by the sureops admin UI for the "Inject Demo
Failure" feature.

### `chaos-mechanism.md`
Onboarding doc for new sureops staff explaining how the flagd-driven
failure injection works end-to-end.

## DO NOT

1. **Do NOT add this directory's content to `.sureops/`** (which IS synced to customer forks).
2. **Do NOT remove the exclusion line** in `.github/workflows/customer-sync.yml`:
   ```yaml
   git rm -rf --ignore-unmatch .sureops-internal/
   ```
   That line is what enforces the chaos-invisibility contract at the file-sync level.
3. **Do NOT reference flag names or the chaos mechanism** in any of the
   `.sureops/runbooks/{service}.md` files. Those are agent-readable. The
   forbidden-language list is in the spec (section 4.4.4): no "feature flag,"
   "chaos," "injection," "demo," or specific flag names.

If you're adding a new file here, double-check that it's not also referenced
from somewhere agent-readable.
