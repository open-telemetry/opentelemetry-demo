# Autonomous AI On-Call Engineer for OpenTelemetry Demo

An autonomous, grounded, human-in-the-loop SRE and On-Call Engineer designed for the OpenTelemetry Astronomy Shop demo. The system detects incidents from live telemetry, investigates root causes using an LLM reasoning loop with read-only tools, verifies evidence citations, matches allowlisted runbooks, gates all actions behind a cryptographic approval dashboard, safely executes and verifies recovery via a dedicated Action API, records experiences into incident memory, and suggests concrete prevention measures.

---

## Quick Start

### 1. Prerequisites
- Docker & Docker Compose v2+
- Local Ollama running with an instruct model (default: `qwen2.5:7b-instruct` or any compatible model):
  ```bash
  ollama run qwen2.5:7b-instruct
  ```

### 2. Launch the Stack
Run the standard demo command:
```bash
make start
```
`compose.extras.yaml` automatically builds and attaches:
- **`action-api`**: Dedicated control plane gatekeeper on port `8201`.
- **`oncall-agent`**: AI agent and approval dashboard on port `8200`.

### 3. Access Interfaces
- **Approval Dashboard**: [http://localhost:8200](http://localhost:8200)
- **Action API Health & Audit**: [http://localhost:8201/health](http://localhost:8201/health) | [http://localhost:8201/audit](http://localhost:8201/audit)
- **Jaeger UI**: [http://localhost:8080/jaeger/ui](http://localhost:8080/jaeger/ui)
- **Prometheus UI**: [http://localhost:9090](http://localhost:9090)
- **Astronomy Shop Frontend**: [http://localhost:8080](http://localhost:8080)

---

## How It Works

```
[Prometheus / Jaeger / OpenSearch]
              │ (Read-only queries)
              ▼
    ┌───────────────────┐
    │  oncall-agent     │ ──► [Evidence Ledger] ──► [Validator]
    │  (:8200)          │                                │
    └───────────────────┘                                ▼
              │                               [Runbook Proposer]
              │                                          │
              ▼                                          ▼
    [Approval Dashboard] ◄────────────────────── [Approval Gate]
      • Live Incident Queue
      • Jaeger Trace Links
      • Dry-Run / Approve / Reject
      • Global Kill Switch
              │
              │ (Approved: Mints HMAC-SHA256 Token)
              ▼
    ┌───────────────────┐
    │  action-api       │ ◄── Enforces Kill Switch (423 Locked)
    │  (:8201)          │ ◄── Enforces Allowlist & Token Validation
    └───────────────────┘
              │ (Mutating Actions)
              ▼
    [Docker / flagd-ui / Locust]
              │
              ▼
    [Fresh Telemetry Recovery Verification] ──► (Rollback if failed)
```

### 1. Detection
The agent polls Prometheus span metrics every 30 seconds for anomaly symptoms (error ratio > 5%, p95 latency > 3× baseline). Alerts convey **symptoms only**; they never speculate on causes or flags.

### 2. Investigation & Anti-Hallucination
The LLM agent explores the system using strictly read-only tools:
- Traces (`search_traces`, `get_trace` — stripping any `feature_flag.*` attributes)
- Metrics (`get_health_overview`, `query_prometheus`)
- Logs (`search_logs` in OpenSearch)
- Container status (`get_container_health`, `get_recent_changes`)
- Incident memory (`search_incident_memory`)

Every tool response is written raw to `/data/incidents/<id>/evidence.jsonl`. When submitting a diagnosis, the deterministic validator checks:
1. Every cited `evidence_id` exists in the ledger.
2. Every cited log fragment or metric number is verbatim present in raw output (rejecting fabricated evidence).
3. Evaluates calibrated confidence: `min(model_confidence, evidence_score)`. If confidence < 0.70 or category is `unknown`, it **escalates** without proposing a fix.

### 3. Human Approval Gate
All actions must be explicitly approved by an operator in the Web Dashboard at `http://localhost:8200`.
- **Dry-run simulation:** Safe dry-run testing before executing.
- **HMAC token binding:** Approving mints a cryptographic HMAC-SHA256 token bound to `{incident_id, action, params, exp}`.
- **No auto-approve in production:** Unconditional human approval is required (`EVAL_AUTO_APPROVE=false`).

### 4. Safe Execution & Verification
`action-api` verifies the HMAC token, checks the allowlist, and executes the action. The agent enters `VERIFYING` state, waits `ONCALL_SETTLE_S` (60s), and inspects fresh telemetry. If error ratios do not drop below 2%, the agent automatically executes a rollback and escalates.

### 5. Incident Memory (Stretch A)
Past incident outcomes are stored in SQLite (`/data/memory.sqlite`). When repeat incidents occur, the agent consults past successes to prioritize its hypothesis, saving diagnostic tool steps. Memory is treated strictly as a **hint** and is never accepted as live evidence.

### 6. Automated Prevention (Stretch B)
Upon resolution, the engine generates concrete, non-applied alerting rules (with PromQL live-validated against Prometheus), compose configuration limits, and architectural code suggestions.

---

## Hard Rules Compliance (Section 2)

- **Zero Flag-Reading Policy:** The agent never inspects `demo.flagd.json` or flagd read endpoints, and strips `feature_flag.*` attributes from all trace spans. Diagnosis is derived 100% from system symptoms.
- **Action API Sole Write Path:** No direct mutation of Docker, flags, or Locust from the agent.
- **Global Kill Switch:** An operator can engage the kill switch at any time in the dashboard; `action-api` will reject all mutating actions with `HTTP 423 Locked`.

---

## Running Practice Incidents & Evaluation

Inject practice incidents using the provided test tooling:
```bash
# List available incidents (#1 to #15)
python tools/faultctl.py list

# Inject Incident #1 (payment charge failures)
python tools/faultctl.py inject 1

# Demonstrate Stretch A Repeat Incident (Memory Assist)
python tools/run_eval.py --repeat 1

# Reset all injected faults to clean baseline
python tools/faultctl.py reset
```

To run the complete test suite:
```bash
cd src/oncall-agent
PYTHONPATH=. pytest tests/ -v
```

---

## Documentation Links
- [Architecture Document](file:///Users/charanteja/Desktop/Team---35/docs/ARCHITECTURE.md)
- [Key Design Decisions](file:///Users/charanteja/Desktop/Team---35/docs/DESIGN_DECISIONS.md)
- [Evaluation Matrix & Benchmark Report](file:///Users/charanteja/Desktop/Team---35/docs/EVALUATION.md)
- [Reconnaissance Baseline](file:///Users/charanteja/Desktop/Team---35/docs/RECON.md)
- [Curated Incident Reports](file:///Users/charanteja/Desktop/Team---35/deliverables/incident-reports/)
