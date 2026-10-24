# AI On-Call Engineer: One-Page Architecture Overview

**Hackathon Deliverable 2**: High-level system design, components, tool selection, reasoning loop, and safety gates.

---

## 1. System Topology & Pipeline

```
                       [ Incident Alert Ingress ]
                                   |
                                   v
                    +-----------------------------+
                    |  Incident Memory (Stretch 1)|
                    | (Historic Precedent Match)  |
                    +-----------------------------+
                                   |
                                   v
             +-------------------------------------------+
             |       AI On-Call Agent (The Brain)        | <---+
             |       Iterative ReAct Decision Loop       |     | Telemetry
             +-------------------------------------------+     | Feedback
                                   |                           |
         +-------------------------+-------------------------+ |
         |                         |                         | |
         v                         v                         v |
 [PrometheusTool]           [JaegerTool]             [OpenSearchTool]
(Golden Signals: P95,      (Parent-Child Span DAG   (Trace-ID Correlated
 Error Rates, RPS)          Downstream Isolation)    Exception Logs)
         |                         |                         |
         +-------------------------+-------------------------+
                                   |
                                   v
                [DeploymentHistoryTool (Git Commits)]
                                   |
                                   v
             +-------------------------------------------+
             |   Evidence Consistency Synthesis Engine   |
             +-------------------------------------------+
                                   |
                                   v
             +-------------------------------------------+
             |   Adversarial Reviewer Agent (Stretch 2)  |
             |   (Disproves False Diagnoses / Rule 6)    |
             +-------------------------------------------+
                                   |
                                   v
             +-------------------------------------------+
             |     Human-in-the-Loop Safety Gate         |
             | (Tokenized Barrier: AUTH-XXXX / Dry-Run)  |
             +-------------------------------------------+
                                   |
                                   v
             +-------------------------------------------+
             |    Permitted Action API (The Hands)       |
             | (Restart, Toggle Flag, Throttle Loadgen)  |
             |  + Action Audit Logging (action_log.jsonl)|
             +-------------------------------------------+
                                   |
                                   v
             +-------------------------------------------+
             |    Recovery Verifier & Rollback Guard     |
             |  (10-60s Polling; Auto-Rollback on Fail)  |
             +-------------------------------------------+
                                   |
                                   v
             +-------------------------------------------+
             |     Post-Mortem & Prevention Engine       |
             |    (JSON Schema + Prevention Strategy)    |
             +-------------------------------------------+
```

---

## 2. Component Directory

| Component | Class / Engine | Responsibility |
| :--- | :--- | :--- |
| **Ingress & Memory** | `IncidentMemory` | Fingerprint matcher that checks past incident resolutions to accelerate repeat triage. |
| **Observation (Eyes)** | `PrometheusTool`, `JaegerTool`, `OpenSearchTool`, `DeploymentHistoryTool` | Dual-mode telemetry tools querying live Prometheus, Jaeger v3, OpenSearch, and Git commits. |
| **Reasoning (Brain)** | `AIOnCallAgent` | ReAct loop that formulates intents, evaluates observations, isolates downstream bottlenecks, and computes calibrated confidence scores. |
| **Adversarial Audit** | `ReviewerAgent` | Secondary critic that verifies evidence grounding, tests counter-hypotheses, and validates Rule 6 compliance. |
| **Safety Barrier** | `HumanApprovalGate` | Enforces explicit human authorization, generates signed cryptographic tokens, and handles dry-runs. |
| **Remediation (Hands)** | `ActionManager` | Restricts actions to allowlisted runbooks, enforces deny-lists for critical infrastructure, logs to `action_log.jsonl`. |
| **Verification & Rollback** | `RecoveryVerifier` | Mathematical stability verifier checking P95 latency baseline across consecutive polling cycles; triggers auto-rollback if recovery fails. |
| **Synthesis (Voice)** | `PreventionEngine`, `IncidentReporter` | Produces compliant JSON schema diagnoses and post-mortems with prevention strategies. |

---

## 3. How the Agent Decides Which Tool to Call

1. **Step 1 (Prometheus)**: Formulates intent to verify if the alert is real. If P95 $< 100\text{ms}$ and errors $= 0$, short-circuits as `NORMAL_BASELINE_HEALTH (False Positive)`.
2. **Step 2 (Jaeger)**: Inspects distributed trace parent-child relationships. If a child span dominates execution duration or flags an error, dynamically re-points culprit from alerted service to downstream child.
3. **Step 3 (OpenSearch)**: Takes the degraded `trace_id` discovered in Step 2 and filters logs exclusively for that trace ID, eliminating hallucinated log matches.
4. **Step 4 (Deployment History)**: Queries `git log -n 3` via subprocess to verify if breaking commits occurred in the incident window; rules out deployment regressions if clean.
5. **Step 5 (Synthesis & Review)**: Compiles categorized evidence, calibrated confidence, submits to adversarial reviewer agent, and formats the remediation plan.

---

## 4. Safety & Kill-Switch Controls

- **Pre-Execution Consistency Guard**: Rejects redundant mutations (e.g., turning off a flag that is already off).
- **Core Infrastructure Whitelist**: Prevents restarts of databases or observability collectors (`otel-collector`, `jaeger`, `prometheus`, `valkey-cart`).
- **Emergency Kill Switch**: Supported via `--kill-switch` flag and `SIGINT` (`Ctrl+C`) handling, immediately aborting all actions and escalating to human on-call.
- **Automated Rollback**: Reverts the last mutated state if recovery telemetry fails to normalize.
