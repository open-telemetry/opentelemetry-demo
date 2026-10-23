# Key Architectural & Design Decisions

This document details the engineering rationales behind the fundamental architectural choices of the AI On-Call Engineer.

---

## 1. Hand-Rolled Tool Loop vs. Heavy Frameworks (LangChain / AutoGen / CrewAI)

### Decision:
We implemented an explicit, deterministic tool-execution loop in Python (`investigator.py`) using clean Pydantic schemas and standard HTTP clients, rather than adopting heavy agent frameworks.

### Rationale:
1. **Total Observability & Auditability:** In on-call remediation, opacity is fatal. Heavy multi-agent frameworks introduce hidden prompts, uncontrolled retry loops, non-deterministic planning cycles, and unpredictable token consumption. A hand-rolled loop guarantees that every tool call, input, and output is captured exactly as dispatched.
2. **Deterministic Context Window Management:** Raw telemetry responses (Jaeger trace trees, OpenSearch log batches) easily overflow model context limits or dilute reasoning. Our custom loop implements strict compact output renderers (capping tool responses to ~2,000 characters) before context injection.
3. **Zero Deprecation Churn & Minimal Footprint:** Production incident response demands reliability. A lean, dependency-free loop runs seamlessly in constrained container environments (Python slim, memory limits < 400MB) without external framework breaking changes.

---

## 2. Decoupled Two-Service Architecture (`action-api` + `oncall-agent`)

### Decision:
The architecture strictly separates the **Control Plane** (`action-api`) from the **Agent Reasoning Plane** (`oncall-agent`) into two distinct Docker containers.

### Rationale:
1. **Principle of Least Privilege:** `oncall-agent` has zero access to the host Docker daemon (`/var/run/docker.sock`), no credentials to modify feature flags, and no mutation authority. Even if an LLM is prompt-injected or compromised through malicious log payloads, it physically lacks the access vector to mutate containers or flags.
2. **Blast Radius Containment:** `action-api` serves as an immutable gatekeeper enforcing hard allowlists, parameter validation, and emergency kill switch locks. Core observability services (`prometheus`, `jaeger`, `opensearch`, `collector`) can never be stopped or restarted, even if requested by an approved proposal.
3. **Auditable Control Plane:** All mutations must pass through `action-api`, creating an independent, immutable audit log (`/data/audit.log`) outside the agent's filesystem.

---

## 3. Cryptographic HMAC-SHA256 Approval Tokens

### Decision:
All mutating operations executed by `action-api` require a time-bound HMAC-SHA256 signature minted only upon explicit human approval.

### Rationale:
1. **Plan Tampering & Injection Prevention:** The token signature binds `{incident_id, action, params, exp}`. If an actor attempts to tamper with the action (e.g. changing `set_feature_flag` to `restart_service` or modifying parameters), the signature verification fails with `403 Forbidden`.
2. **Replay & Re-use Protection:** Tokens are tied to a specific incident and carry a strict Time-to-Live (`ONCALL_APPROVAL_TTL_S`, default 15 minutes). Expired tokens are rejected, preventing stale approvals from being replayed.
3. **Unconditional Human Approval:** By requiring a cryptographic token minted exclusively when the operator clicks "Approve" in the dashboard, automated or accidental execution is structurally impossible in production mode.

---

## 4. Deterministic Evidence Citation Validator & Calibrated Confidence

### Decision:
Diagnoses submitted by the LLM undergo strict programmatic verification in `validator.py` before any remediation proposal is accepted.

### Rationale:
1. **Elimination of Hallucinations:** LLMs frequently generate plausible-sounding diagnoses citing non-existent trace IDs or invented metric percentages. The validator checks that every cited `evidence_id` exists in the incident's immutable evidence ledger and that every cited log line or metric value actually appears in the raw payload.
2. **Calibrated Confidence Formula:** Model-reported self-confidence is notoriously overconfident. We compute `calibrated_confidence = min(model_confidence, evidence_score)`. The `evidence_score` penalizes single-source evidence, unrefuted alternative hypotheses, and fabricated references.
3. **Enforced Escalation:** If calibrated confidence is below `ONCALL_CONFIDENCE_THRESHOLD` (0.70) or the failure category is `unknown`, the agent transitions to `ESCALATED`. In on-call systems, a well-reasoned escalation is far superior to a confident wrong fix.

---

## 5. Incident Memory as a Hint Only (Never Live Evidence)

### Decision:
Historical incident knowledge retrieved from SQLite (`/data/memory.sqlite`) serves only to guide hypothesis prioritization, never as valid evidence in the diagnosis ledger.

### Rationale:
1. **Preventing Anchoring & Confirmation Bias:** Real production environments experience dynamic regressions where similar symptoms stem from completely different root causes. If past incidents were accepted as evidence, the agent would anchor on historical fixes rather than inspecting live telemetry.
2. **Strict Verification Requirement:** The agent is permitted to consult memory ("similar incident INC-001 was resolved by disabling flag paymentFailure"), but the validator forces the agent to gather live, corroborating traces and logs before submitting a diagnosis.
3. **Failed Fix Deprioritization:** Historical remedies that failed or were rolled back have their similarity score discounted by 25%, preventing the repetition of past mistakes.

---

## 6. Safety-First Operational Defaults

1. **Safe Recovery Verification:** After applying any remediation, the agent enters `VERIFYING` state and waits `ONCALL_SETTLE_S` (60s) to account for Prometheus scrape lag (~60s). It queries fresh Jaeger traces and Prometheus metrics. If error ratios remain elevated, it triggers an immediate rollback.
2. **Strict Flag-Reading Prohibition (Hard Rule 1):** The agent never inspects `src/flagd/demo.flagd.json` or flagd read endpoints, and strips all `feature_flag.*` trace attributes. Remediation is reasoned strictly from system symptoms.
