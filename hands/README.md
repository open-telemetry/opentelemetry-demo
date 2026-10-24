# Hands: Action Execution, Safety Gate & Recovery Verification

Hands delivers **Checkpoint 3 (M6: The agent can act safely)** from `ProblemStatement.md` and `ImplementationPlan.md`.

It provides the actuation and safety layer that executes approved remediation plans against the OpenTelemetry Demo environment, guarded by strict deterministic safety controls.

---

## 1. Safety Architecture

```
[ Proposed Plan (JSON) ]
          │
          ▼
   compute_plan_digest()  --> Canonical SHA-256 Hash
          │
          ▼
   ApprovalGate           --> Requires explicit human decision bound to Plan Digest
          │
          ▼
   KillSwitch Check       --> Durable emergency stop latch (checked at dispatch & in-flight)
          │
          ▼
   Idempotency Ledger     --> Prevents duplicate dispatches in SQLite
          │
          ▼
   ActionApiAdapter       --> Restricted to allowlisted operations & targets
          │
          ▼
   RecoveryVerifier       --> Measures post-remediation telemetry (fresh samples only)
          │
     ┌────┴────────────┐
     ▼                 ▼
[ Recovered ]    [ Not Recovered ]
                       │
                       ▼
                 Rollback / Escalation
```

### Safety Guarantees
1. **Zero Unapproved Mutations**: The model never has credentials to mutate the environment directly. No action can execute without an explicit operator approval bound to the exact plan SHA-256 digest.
2. **Durable Kill Switch**: An atomic, persistent latch stored in SQLite. Once engaged, all dispatching, retrying, and rollback operations are blocked immediately across restarts until an operator explicitly resets it.
3. **Idempotency & Replay Prevention**: Dispatches are recorded before execution. Re-dispatching an already executed plan is blocked.
4. **Target & Parameter Allowlisting**: Services and action types are constrained to the configured allowlist. Arbitrary shell commands and unsupported actions (like scaling in Docker Compose) are strictly rejected.
5. **Fresh Evidence Verification**: Recovery requires post-action telemetry samples strictly newer than the action timestamp. Stale or pre-action samples are never accepted.

---

## 2. Supported Action Types

| Action Type | Target | Description |
| :--- | :--- | :--- |
| `restart_service` | Compose service name | Triggers restart of the target service container. |
| `toggle_feature_flag` | Flag name in `flagd` | Changes flag state (e.g. disables a fault injection flag). |
| `throttle_load_generator` | `loadgenerator` | Modifies Locust user count / spawn rate to ease saturation. |
| `scale_service` | Service name | Disabled in Docker Compose (requires Kubernetes). |

---

## 3. Configuration

Copy `operator.example.toml` to a dedicated location:
```sh
cp incident_tools/hands/operator.example.toml /tmp/hands-operator.toml
```

Key sections:
* `data_dir`: Directory for `hands.sqlite` (plans, approvals, audit logs, and kill latch).
* `adapter.mode`: `"local_docker"` (live environment), `"http"` (Action API service), or `"mock"` (testing).
* `safety.services`: List of permissible target services.
* `verification.settling_period_seconds`: Delay after action before querying recovery metrics.

---

## 4. CLI Usage

### Check Status & Kill Switch
```sh
python3 -m incident_tools.hands --config /tmp/hands-operator.toml status
```

### Register a Proposed Remediation Plan
```sh
python3 -m incident_tools.hands --config /tmp/hands-operator.toml plan --file sample_plan.json
```
Output returns the canonical `plan_digest`.

### Explicit Human Approval
```sh
python3 -m incident_tools.hands --config /tmp/hands-operator.toml approve \
  --digest <PLAN_DIGEST> \
  --operator "oncall-alice" \
  --reason "Verified deadlock in checkout logs" \
  --ttl-minutes 15
```

### Dry Run (Validation Without Mutation)
```sh
python3 -m incident_tools.hands --config /tmp/hands-operator.toml dispatch \
  --digest <PLAN_DIGEST> \
  --dry-run
```

### Execute Approved Action & Verify Recovery
```sh
python3 -m incident_tools.hands --config /tmp/hands-operator.toml dispatch \
  --digest <PLAN_DIGEST>
```

### Emergency Stop (Kill Switch)
```sh
python3 -m incident_tools.hands --config /tmp/hands-operator.toml kill \
  --operator "oncall-alice" \
  --reason "Unexpected error rate spike in payment"
```

### Reset Kill Switch
```sh
python3 -m incident_tools.hands --config /tmp/hands-operator.toml reset-kill \
  --operator "oncall-alice" \
  --reason "Root cause resolved and blast radius contained"
```

---

## 5. Offline Verification

Run the test suite:
```sh
python3 -m unittest discover -s incident_tools/hands/tests -v
```
