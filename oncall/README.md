# AI On-Call Engineer: Autonomous Incident Investigation & Remediation

Developed for the **Bosch "Incident Zero: Build an AI On-Call Engineer" Hackathon** (OpenTelemetry Demo).

---

## 1. System Overview & Architecture

The **AI On-Call Engineer** is an evidence-driven, safety-constrained autonomous agent designed to triage, isolate, remediate, and report microservice outages in real time.

```
       [ Alert Ingress: Prometheus / PagerDuty / Webhook ]
                               |
                               v
                     +-------------------+
                     |  AI On-Call Agent | <---+
                     |   (ReAct Loop)    |     | Iterative
                     +-------------------+     | Deep Dive
                               |               |
        +----------------------+----------------------+
        |                      |                      |
        v                      v                      v
[PrometheusTool]        [JaegerTraceTool]     [OpenSearchTool]
(Golden Signals:        (Span DAG & Parent-   (Exact Trace ID
 P95, Errors, RPS)       Child Bottlenecks)    Correlated Logs)
        |                      |                      |
        +----------------------+----------------------+
                               |
                               v
                [DeploymentHistoryTool (Git Commits)]
                               |
                               v
              +---------------------------------+
              | Evidence Consistency & Root     |
              | Cause Synthesis Engine          |
              +---------------------------------+
                               |
                               v
              +---------------------------------+
              | Adversarial Reviewer (Stretch 2)|
              +---------------------------------+
                               |
                               v
              +---------------------------------+
              | Human-in-the-Loop Safety Gate   |
              | (Token-based Approval Barrier)  |
              +---------------------------------+
                               |
                  [ APPROVED / REJECTED ]
                               |
                +--------------+---------------+
                |                              |
         [ REJECTED ]                     [ APPROVED ]
                |                              |
                v                              v
       [ Safe Escalation ]            [ Permitted Action API ]
                                      (Restart / Reset Flags / Throttle)
                                      + Action Log (action_log.jsonl)
                                               |
                                               v
                                      [ Recovery Verifier ]
                                      (Post-Action 10-60s)
                                      [ Auto-Rollback on Fail ]
                                               |
                                               v
                                      [ Post-Mortem & Prevention ]
                                      (JSON Schema + Prevention Strategy)
```

---

## 2. All Four Checkpoints Status

| Checkpoint | Status | Requirements & Verification |
| :--- | :--- | :--- |
| **Checkpoint 0: Setup** | **COMPLETE** | OpenTelemetry Demo environment configured with telemetry ingress, dual-mode fallback, and git workflow. |
| **Checkpoint 1: The Eyes** | **COMPLETE** | Prometheus, Jaeger, OpenSearch, Git tools operational; ReAct loop; 1 live practice run; 1-page architecture sketch ([`ARCHITECTURE.md`](ARCHITECTURE.md)). |
| **Checkpoint 2: The Brain** | **COMPLETE** | Evidence-based root-cause isolation; Downstream dependency isolation (`checkout` $\rightarrow$ `payment`); Rule 6 compliance (Zero flag-reading cheats); 3 mentor practice incidents passing in JSON schema ([`checkpoint2_diagnoses.json`](checkpoint2_diagnoses.json)). |
| **Checkpoint 3: The Hands** | **COMPLETE** | 4 Allowlisted Action API runbooks (`RESTART_CONTAINER`, `RESET_FEATURE_FLAG`, `THROTTLE_LOAD_GENERATOR`, `SCALE_SERVICE`), Human Approval Gate with cryptographic tokens, Pre-flight Consistency Guard, Dry-run mode, Emergency Kill Switch, Action Audit Logging, and Automated Rollback on recovery failure. |
| **Checkpoint 4: The Voice & Submission** | **COMPLETE** | Structured post-mortem reports with categorized evidence, incident recurrence prevention recommendations, all 5 hackathon deliverables in repo, ready for unseen evaluation incidents. |

---

## 3. Quick Start & Execution Commands

### A. Run End-to-End CLI Pipeline (Production Run)
```bash
# Interactive mode (prompts human operator for approval):
python oncall/cli.py --service cart

# Automated evaluation mode (auto-approves validated actions):
python oncall/cli.py --service cart --auto-approve

# Dry-run mode (validates action without mutating system state):
python oncall/cli.py --service cart --auto-approve --dry-run

# Emergency Kill Switch (halts all actions and escalates):
python oncall/cli.py --kill-switch
```

### B. Run Checkpoint 1 Demo (Live Practice Run)
```bash
python oncall/demo_practice_incident.py
```

### C. Run Checkpoint 2 Benchmark (3 Practice Incidents)
```bash
python oncall/evaluate_practice_incidents.py
```

### D. Launch Interactive Web Console (Stretch Goal 4)
```bash
python oncall/ui.py
# Open in browser: http://localhost:5000
```

---

## 4. Safety Controls & The Approval Gate

1. **Human Approval Barrier**:
   The agent **cannot execute any action** without an explicit approval token signed by an authorized human operator. If rejected or timed out, the incident is cleanly escalated without mutating system state.
2. **Pre-Execution Consistency Guard**:
   If an operator or agent attempts to mutate a configuration flag or container that is already in the target state, the action is **aborted immediately** with an `EVIDENCE CONSISTENCY ERROR` to prevent redundant or destructive operations.
3. **Core Infrastructure Whitelist**:
   The Action API enforces an immutable deny-list. Critical infrastructure (`otel-collector`, `prometheus`, `jaeger`, `opensearch`, `flagd`, `astronomy-db`, `valkey-cart`) can never be stopped or restarted by the agent.
4. **Dry-Run Mode (`--dry-run`)**:
   Allows operators or testing harnesses to simulate and validate the execution path, parameters, and safety barriers without mutating application state.
5. **Emergency Kill Switch (`--kill-switch` / `Ctrl+C`)**:
   Provides an immediate, unconditional halt to all agent operations, cleanly transferring incident context to human responders.
6. **Automated Rollback & Audit Trail**:
   All executed actions are appended to `oncall/action_log.jsonl`. If post-action recovery verification fails, the Action Manager automatically triggers a rollback to the previous state.

---

## 5. Five Stretch Goals Implemented

1. **Stretch Goal 1: Incident Memory (`oncall/memory/incident_memory.py`)**:
   Matches incident symptoms against previously resolved outages to accelerate triage and reuse proven remediation patterns.
2. **Stretch Goal 2: Adversarial Reviewer Agent (`oncall/safety/reviewer_agent.py`)**:
   An independent critic agent audits the primary diagnosis for counter-hypotheses, evidence gaps, and Rule 6 compliance before presenting to human on-call.
3. **Stretch Goal 3: Calibrated Confidence**:
   Dynamic confidence scoring matches empirical accuracy across the practice set (0.82–0.98).
4. **Stretch Goal 4: Chat-Style / Web Console Approval (`oncall/ui.py`)**:
   Interactive dark-mode incident operations console for point-and-click triage, live ReAct stepping, and approval authorization.
5. **Stretch Goal 5: Prevention Engine (`oncall/prevention.py`)**:
   Generates actionable code, configuration, and alerting improvements to prevent incident recurrence.

---

## 6. Official Deliverables Checklist (Slide 4)

- [x] **Deliverable 1: Source Code & README**: This documentation and clean codebase.
- [x] **Deliverable 2: Architecture Overview**: [`ARCHITECTURE.md`](ARCHITECTURE.md) (One-page architecture overview).
- [x] **Deliverable 3: Incident Reports**: [`checkpoint2_diagnoses.json`](checkpoint2_diagnoses.json) (JSON schema + Markdown post-mortems).
- [x] **Deliverable 4: Evaluation Note**: [`EVALUATION_NOTE.md`](EVALUATION_NOTE.md) (Practice incident accuracy analysis).
- [x] **Deliverable 5: Team Form**: [`TEAM_FORM.md`](TEAM_FORM.md) (Team declaration and tool disclosures).

---

## 7. Known Limitations

1. **Kubernetes Multi-Cluster Scaling**: The `SCALE_SERVICE` action operates locally in simulation or Docker compose mode; native multi-node Kubernetes HPA scaling requires active `kubectl` cluster credentials.
2. **Offline Telemetry Granularity**: In offline mode (when Docker is terminated), the system uses recorded OpenTelemetry incident bundles. While realistic, real-time live Prometheus metric scrapes provide higher temporal granularity.
3. **Action API Concurrency**: To avoid race conditions, the Action API allows only one active remediation action at a time per incident.
