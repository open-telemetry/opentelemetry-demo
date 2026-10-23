# AI On-Call Engineer: Autonomous Incident Investigation & Remediation

Developed for the **Bosch "Incident Zero: Build an AI On-Call Engineer" Hackathon** (OpenTelemetry Demo).

---

## 1. System Overview & Architecture

The **AI On-Call Engineer** is an evidence-driven, safety-constrained autonomous agent designed to triage, isolate, and remediate microservice outages in real time.

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
                                      (Restart / Reset Flags)
                                               |
                                               v
                                      [ Recovery Verifier ]
                                      (Post-Action 10-60s)
                                               |
                                               v
                                      [ Post-Mortem Report ]
                                      (Markdown + JSON Schema)
```

---

## 2. Checkpoint Status Summary

| Checkpoint | Status | Key Deliverables Verified |
| :--- | :--- | :--- |
| **Checkpoint 1: The Eyes** | **COMPLETE** | Prometheus, Jaeger, OpenSearch, Git tools operational; ReAct loop; 1 live practice run; 1-page architecture sketch |
| **Checkpoint 2: The Brain** | **COMPLETE** | Evidence-based root cause isolation; Downstream dependency isolation (`checkout` -> `payment`); Rule 6 compliance (Zero flag-reading cheats); 3 mentor practice incidents passing in JSON schema |
| **Checkpoint 3: The Hands** | **READY** | Action API client (Flagd, Docker container restart), Human Approval Gate with cryptographic tokens, Evidence Consistency Guard, Post-action recovery verifier |
| **Checkpoint 4: The Voice** | **READY** | Automated structured post-mortem reports with categorized evidence (Confirmed Facts, Likely Causes, Ruled Out Hypotheses) in Markdown & JSON |

---

## 3. Quick Start & Evaluation Commands

### Checkpoint 1 Demo (Live Practice Run)
Demonstrates the working telemetry tools, correct root-cause logic, downstream isolation, and consistency guard:
```bash
python oncall/demo_practice_incident.py
```

### Checkpoint 2 Benchmark (3 Practice Incidents in JSON Schema)
Evaluates the agent across all 3 mentor scenarios and outputs `oncall/checkpoint2_diagnoses.json`:
```bash
python oncall/evaluate_practice_incidents.py
```

### End-to-End Interactive CLI (With Safety Gate)
```bash
# Interactive mode (prompts human operator for approval):
python oncall/cli.py --service cart

# Automated evaluation mode (auto-approves validated actions):
python oncall/cli.py --service cart --auto-approve
```

---

## 4. Emergency Kill Switch & Safety Controls

1. **Human Approval Barrier**:
   The agent **cannot execute any action** without an explicit approval token signed by an authorized human operator. If rejected or timed out, the incident is cleanly escalated without mutating system state.
2. **Pre-Execution Consistency Guard**:
   If an operator or agent attempts to mutate a configuration flag or container that is already in the target state, the action is **aborted immediately** with an `EVIDENCE CONSISTENCY ERROR` to prevent redundant or destructive operations.
3. **Core Infrastructure Whitelist**:
   The Action API enforces an immutable deny-list. Critical infrastructure (`otel-collector`, `prometheus`, `jaeger`, `opensearch`, `flagd`) can never be stopped or restarted by the agent.
4. **Emergency Abort (`Ctrl+C`)**:
   All async verification loops and tool calls register SIGINT handlers, ensuring that interrupting the CLI halts all outbound requests immediately.

---

## 5. Team Structure & Contributions (5 Members)

| Member | Branch | Responsibilities |
| :--- | :--- | :--- |
| **Teammate 1** (Observability Lead) | `feat/telemetry-signals` | `oncall/tools/prometheus.py`, `oncall/tools/jaeger.py` (Golden signals, latency quantiles, span DAG traversal) |
| **Teammate 2** (Context & Logs Lead) | `feat/telemetry-context` | `oncall/tools/opensearch.py`, `oncall/tools/deployment_history.py` (Trace ID log correlation, git deployment history) |
| **Teammate 3** (Agent Brain Lead) | `feat/agent-brain` | `oncall/agent.py`, `oncall/models.py` (ReAct investigation loop, calibrated confidence scoring, root-cause synthesis) |
| **Teammate 4** (Safety & Action Lead) | `feat/actions-safety` | `oncall/actions/`, `oncall/safety/` (Approval barrier, action API, evidence consistency guard, recovery verifier) |
| **Teammate 5** (Integration & Evaluation Lead) | `feat/pipeline-integration` | `oncall/cli.py`, `oncall/reporter.py`, `oncall/evaluate_practice_incidents.py` (Evaluation benchmarks, schema compliance) |
