# Architecture Decision Records (ADRs)

**Project:** Bosch Incident Zero  
**Scope:** Hackathon System Architecture & Implementation Strategy  

---

## ADR 001: Dedicated Solution Directory (`bosch-incident-zero/`)

### Status
Accepted

### Context
We are participating in a Bosch hackathon based on the upstream `open-telemetry/opentelemetry-demo` repository. We must establish a clean, maintainable separation between upstream demo code and our solution. The upstream repository contains over 20 microservices, an OpenTelemetry Collector, and a complex Docker Compose layer.

### Decision
We create a dedicated, self-contained solution directory named `bosch-incident-zero/` inside the workspace root (or capable of living as a standalone sibling repository). We strictly avoid modifying upstream microservice source code, compose files, or tests unless an explicit, documented integration point necessitates it.

### Consequences
- **Positive:**
  - Upstream updates can be pulled from `open-telemetry/opentelemetry-demo` without merge conflicts.
  - Clear ownership boundary: all team files reside under `bosch-incident-zero/`.
  - Can be turned into an independent Git repository at any time with a single `git init`.
  - Upstream files remain clean, preventing accidental submission of unrelated diffs.
- **Negative / Trade-off:**
  - Requires explicit network configuration to communicate with demo services across host/bridge networks.

---

## ADR 002: Python 3.11+ for Solution Implementation

### Status
Accepted

### Context
We need a runtime for the SRE agent that provides:
1. Rich, asynchronous HTTP client libraries for Prometheus, Jaeger, and OpenSearch.
2. Strong typing and schema validation (Pydantic / JSON Schema).
3. Fast prototyping and interactive CLI support for human approval workflows.
4. Native compatibility with AI/LLM frameworks (e.g., LangChain, LiteLLM) should intelligent reasoning be required.

The host machine already has Python 3.11.9 and pytest 7.4.4 installed. Upstream also utilizes Python for several components (`src/recommendation`, `src/load-generator`, `src/agent`).

### Decision
Implement the Bosch Incident Zero solution in Python 3.11+ using standard, pinned dependencies (`pydantic`, `requests`, `pyyaml`, `jsonschema`, `rich`, `pytest`).

### Consequences
- **Positive:**
  - Rapid development of evidence gathering, correlation, and remediation workflows.
  - Native integration with Python ecosystem for data analysis and ML/LLM tooling.
  - Zero compilation overhead during hackathon development.
- **Negative:**
  - Dynamic runtime requires strict type hinting (`mypy`/Pydantic) to avoid runtime type bugs.

---

## ADR 003: Non-Negotiable Safety Controls (Kill-Switch & Approval Gate)

### Status
Accepted

### Context
Automated remediation systems can induce catastrophic failure loops (e.g., repeatedly restarting a database under heavy load or misinterpreting a planned promotion as an anomaly). Safety mechanisms must be absolute, deterministic, and verifiable.

### Decision
Enforce two mandatory safety controls in the execution path:
1. **Emergency Kill-Switch (`src/remediation/kill_switch.py`):**
   - Supports both environment variable (`KILL_SWITCH_ENABLED=true`) and file sentinel (`.kill_switch`).
   - Evaluated synchronously immediately before *any* remediation execution.
   - If engaged, raises `KillSwitchEngagedException` and halts immediately.
2. **Human Approval Gate (`src/approval/gate.py`):**
   - Requires explicit human authorization before executing any non-idempotent remediation action.
   - Supports interactive CLI confirmation, dry-run mode, and automated token validation.

### Consequences
- **Positive:**
  - Guarantees that the agent will never trigger unintended actions in production or during evaluation.
  - Provides a single, instantaneous shutoff mechanism for evaluators and operators.
- **Negative:**
  - Autonomous loop is paused pending human sign-off when approval mode is enabled.

---

## ADR 004: Pluggable Abstractions for Missing Bosch Contracts

### Status
Accepted

### Context
The audited repository contains zero Bosch-specific starter code, and neither `faultctl` nor the official Action API specification were found in the checked-out repository.

### Decision
Define clean, abstract interfaces:
1. `FaultController` (base interface in `src/faultctl/base.py`). The `FlagdAdapter` implementation that edited `src/flagd/demo.flagd.json` was removed on Day 2 because the rules allow injection only through the official `faultctl`.
2. `ActionAPIClient` (base interface in `src/remediation/action_api.py`) with support for flag deactivation, container restart, and dry-run execution.

When the hackathon organizers provide the official `faultctl` binary or Action API endpoint, only concrete adapters need to be swapped or configured via `.env`.

### Consequences
- **Positive:**
  - Development and testing proceed immediately without blockers.
  - Zero risk of rewriting core diagnosis logic when official contracts are released.
- **Negative:**
  - Requires maintaining an adapter layer until official contracts stabilize.

---

## ADR 005: Schema-Driven Incident Reporting

### Status
Accepted

### Context
Incident reports must be machine-readable, auditable, and verifiable by hackathon evaluation harnesses.

### Decision
Define a formal JSON Schema (`config/incident_schema.json`) and corresponding Pydantic models (`src/models/incident.py`). Every incident report generated by the agent must validate against this schema before persistence and presentation.

### Consequences
- **Positive:**
  - Guarantees strict structure across all output artifacts.
  - Prevents missing citations, missing trace IDs, or unformatted timestamps.
- **Negative:**
  - Diagnosis output generation must handle schema validation exceptions gracefully.
