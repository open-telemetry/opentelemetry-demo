# Bosch Incident Zero Hackathon: Official Team Form

**Hackathon Deliverable 5**: Team declaration, role distribution, tool usage, and third-party libraries.

---

## 1. Team Information

* **Team Name**: Incident Zero Pioneers
* **Institution**: PES University
* **Track**: Bosch "Incident Zero: Build an AI On-Call Engineer"
* **Repository**: OpenTelemetry Astronomy Shop Demo (`open-telemetry/opentelemetry-demo`)

---

## 2. Team Member Roles & Contributions (5 Members)

| Member Name | Role | Git Branch | Core Responsibilities & Files Built |
| :--- | :--- | :--- | :--- |
| **Member 1** (Observability Lead) | Telemetry Signals | `feat/telemetry-signals` | Built `oncall/tools/prometheus.py` (Golden signals, PromQL instant queries) and `oncall/tools/jaeger.py` (Parent-child span DAG traversal, bottleneck isolation). |
| **Member 2** (Context & Logs Lead) | Telemetry Context | `feat/telemetry-context` | Built `oncall/tools/opensearch.py` (Strict trace-ID log scoping) and `oncall/tools/deployment_history.py` (Subprocess `git log` commit auditor; Rule 6 compliance). |
| **Member 3** (Agent Brain Lead) | Reasoning & Logic | `feat/agent-brain` | Built `oncall/agent/engine.py` (ReAct investigation loop, downstream vs alerted fault isolation, calibrated confidence engine) and `oncall/models.py`. |
| **Member 4** (Safety & Actions Lead) | Safety & Execution | `feat/actions-safety` | Built `oncall/actions/` (ActionManager, Flagd, Docker, Loadgen clients), `oncall/safety/approval_gate.py` (Token barrier), `recovery_verifier.py`, and rollback engine. |
| **Member 5** (Integration Lead) | Evaluation & UI | `feat/pipeline-integration` | Built `oncall/cli.py`, `oncall/evaluate_practice_incidents.py`, `oncall/ui.py` (Interactive web console), `oncall/reporter.py`, and stretch goal engines. |

---

## 3. Declaration of AI Coding Assistants & Tools (Rule 2 Compliance)

In compliance with **Hackathon Rule 2** (*"AI coding assistants are allowed if declared in the team form; every member must be able to explain and change the code they submit"*):

* **AI Coding Assistant**: Google Antigravity / Gemini Coding Assistant
* **AI Model / LLM Configuration**: Gemini 2.5 Flash / Pro (used for planning, ReAct prompt templates, and code scaffolding).
* **Commit Trailer Compliance**: Disclosed using `Assisted-by: Antigravity` trailers per repository `AGENTS.md`. No `Co-authored-by:` trailers used (ensuring EasyCLA compliance).
* **Code Competency**: Every member has reviewed, debugged, and is prepared to explain and modify their designated modules during the mentor review and finalist interviews.

---

## 4. Third-Party Libraries & Dependencies

All dependencies are lightweight and standard:
* `pydantic` (v2.x): Strict data contract validation, JSON Schema export.
* `requests`: HTTP communication with telemetry backends and Action APIs.
* Python Standard Library:
  * `subprocess`: Executing Git commit log queries.
  * `http.server` & `socketserver`: Powering the zero-dependency interactive Web UI console.
  * `json` & `uuid`: Audit log serializing and cryptographic approval token generation.
  * `datetime`: UTC incident timestamps and timeline formatting.
