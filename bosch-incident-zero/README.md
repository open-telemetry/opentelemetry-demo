# Bosch Incident Zero

**Autonomous Incident Diagnosis and Safe Remediation for Microservice Architectures**

Bosch Incident Zero is an autonomous Site Reliability Engineering (SRE) solution engineered for the OpenTelemetry Astronomy Shop ecosystem. It continuously monitors distributed telemetry, detects anomalous degradations, aggregates multi-signal evidence, pinpoints root causes, and executes verified, human-approved remediations under strict fail-safe controls.

---

## Key Capabilities

- **Autonomous Telemetry Triage:** Ingests and correlates distributed traces (Jaeger), RED metrics (Prometheus), and log events (OpenSearch).
- **Evidence-Driven Root Cause Analysis:** Evaluates upstream and downstream dependency graphs to isolate root causes from cascading side-effects.
- **Structured Incident Reporting:** Produces strictly schema-validated incident reports adhering to `config/incident_schema.json`.
- **Strict Safety Controls:**
  - **Emergency Kill-Switch:** Immediate hard shutoff (`KILL_SWITCH_ENABLED=true` or sentinel file) aborting all active and pending agent interventions.
  - **Mandatory Approval Gate:** Requires explicit human authorization before executing any remediation action.
- **Pluggable Architecture:** Decoupled interfaces for fault injection (`faultctl` / `flagd`) and remediation (`ActionAPI`).

---

## Architectural Separation

This solution lives in `bosch-incident-zero/` as a dedicated, self-contained project cleanly isolated from upstream OpenTelemetry Demo source code:

- **Upstream Demo:** Unmodified, external dependency providing application microservices, the OTel Collector, and observability stores.
- **Bosch Solution:** Standalone Python 3.11+ application communicating over standard HTTP/REST network boundaries.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/DECISIONS.md](docs/DECISIONS.md) for detailed architectural specifications.

---

## Prerequisites

- **Python:** 3.11 or later
- **Docker Desktop:** Installed and running (for the target OpenTelemetry Demo)
- **Host OS:** Windows (PowerShell 7+), macOS, or Linux

---

## Quick Start

### 1. Configure Environment

Copy the example configuration:

```bash
# Windows PowerShell
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```

Review `.env` and configure endpoints if running services on non-default ports.

### 2. Install Dependencies

```bash
# Recommended: Create and activate virtual environment
python -m venv .venv

# Windows PowerShell:
.venv\Scripts\Activate.ps1

# Linux / macOS:
source .venv/bin/activate

# Install dependencies:
pip install -r requirements.txt
```

### 3. Verify Environment

Run the diagnostic verification script to test Python dependencies, Docker daemon status, and service endpoint reachability:

```bash
python scripts/verify_environment.py
```

### 4. Run Tests

Execute the unit test suite:

```bash
pytest tests/
```

---

## Documentation Index

- [Repository Audit](docs/REPOSITORY_AUDIT.md) — Comprehensive audit of the target OpenTelemetry Demo codebase.
- [Implementation Roadmap](docs/IMPLEMENTATION_ROADMAP.md) — 7-stage prioritized implementation roadmap.
- [Architecture & Design](docs/ARCHITECTURE.md) — Architectural patterns, safety controls, and data flow.
- [Setup & Run Guide](docs/SETUP.md) — Step-by-step setup and operational runbooks.
- [Architecture Decisions (ADRs)](docs/DECISIONS.md) — Rationale for key technical and organizational choices.

---

## Repository Structure

```text
bosch-incident-zero/
├── README.md                   # Solution overview and quick start
├── .gitignore                  # Technology-specific gitignore
├── .env.example                # Safe environment configuration template
├── pyproject.toml              # Project metadata and tool configuration
├── requirements.txt            # Pinned dependencies
├── docs/                       # Architectural and audit documentation
│   ├── ARCHITECTURE.md
│   ├── REPOSITORY_AUDIT.md
│   ├── IMPLEMENTATION_ROADMAP.md
│   ├── SETUP.md
│   └── DECISIONS.md
├── src/                        # Core solution source code
│   ├── config.py               # Settings loader
│   ├── approval/               # Human approval workflow gate
│   ├── remediation/            # Safe Action API and kill-switch
│   ├── faultctl/               # Fault injection adapter
│   ├── telemetry/              # Jaeger, Prometheus, OpenSearch clients
│   └── models/                 # Pydantic data schemas
├── config/                     # Configuration and schemas
│   ├── incident_schema.json    # JSON schema for incident reports
│   └── default_config.yaml     # Baseline thresholds and parameters
├── scripts/                    # Operational and verification scripts
│   ├── verify_environment.py
│   └── verify_environment.ps1
└── tests/                      # Unit and integration test suite
```
