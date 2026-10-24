# Bosch Incident Zero — Setup & Operational Guide

This document details how to set up, configure, and execute both the upstream OpenTelemetry Demo and the Bosch Incident Zero solution, on Windows (PowerShell) and Linux/macOS.

---

## 1. Prerequisites

Ensure the following tools are installed:

- **Docker Desktop** (version 24.0+ recommended). The Docker daemon must be running.
- **Python** (version 3.11+).
- **Git** (version 2.30+).

---

## 2. Upstream OpenTelemetry Demo Execution

The OpenTelemetry Demo is the target system under observation.

### 2.1 Starting the Demo

#### Option A: Full Demo with Observability (Recommended for Full Testing)
Starts all 14 core services, Kafka, PostgreSQL, Valkey, Jaeger, Prometheus, OpenSearch, Grafana, and Flagd:

**Windows PowerShell:**
```powershell
# From repository root:
docker compose --env-file .env --env-file .env.override `
  -f compose.yaml -f compose.full.yaml -f compose.observability.yaml up -d
```

**Linux / macOS:**
```bash
docker compose --env-file .env --env-file .env.override \
  -f compose.yaml -f compose.full.yaml -f compose.observability.yaml up -d
```

#### Option B: Minimal Demo with Observability (Low Memory Footprint)
Excludes Kafka and dependent async services (`accounting`, `fraud-detection`):

**Windows PowerShell:**
```powershell
docker compose --env-file .env --env-file .env.override `
  -f compose.yaml -f compose.observability.yaml up -d
```

**Linux / macOS:**
```bash
docker compose --env-file .env --env-file .env.override \
  -f compose.yaml -f compose.observability.yaml up -d
```

### 2.2 Verifying Demo Health

Check container status:
```bash
docker compose ps
```

Verify that key ports are accessible:
- Web Frontend: `http://localhost:8080/`
- Jaeger Traces: `http://localhost:16686/` (or via Envoy: `http://localhost:8080/jaeger/ui/`)
- Prometheus Metrics: `http://localhost:9090/`
- OpenSearch Logs: `http://localhost:9200/`
- Feature Flags UI: `http://localhost:4000/` (or via Envoy: `http://localhost:8080/feature/`)

### 2.3 Stopping the Demo

```bash
docker compose --env-file .env --env-file .env.override \
  -f compose.yaml -f compose.full.yaml -f compose.observability.yaml down --remove-orphans --volumes
```

---

## 3. Bosch Incident Zero Setup

The Bosch solution is executed independently of the demo containers.

### 3.1 Python Environment Setup

Navigate to the solution directory:
```bash
cd bosch-incident-zero
```

Create and activate a virtual environment:

**Windows PowerShell:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

### 3.2 Configuration

Create your `.env` from `.env.example`:

**Windows PowerShell:**
```powershell
Copy-Item .env.example .env
```

**Linux / macOS:**
```bash
cp .env.example .env
```

Key configuration parameters in `.env`:
- `KILL_SWITCH_ENABLED`: Set to `false` for normal operation; set to `true` to immediately block all remediation.
- `REQUIRE_HUMAN_APPROVAL`: Set to `true` to enforce manual confirmation before actions.
- `DRY_RUN_MODE`: Set to `true` to simulate actions without executing mutations.
- `JAEGER_URL`: Default `http://localhost:16686`.
- `PROMETHEUS_URL`: Default `http://localhost:9090`.
- `OPENSEARCH_URL`: Default `http://localhost:9200`.

### 3.3 Diagnostic Environment Verification

Run the verification script to confirm connectivity to the environment:

**Cross-Platform Python:**
```bash
python scripts/verify_environment.py
```

**Windows PowerShell Script:**
```powershell
.\scripts\verify_environment.ps1
```

The script verifies:
1. Python version ($\ge 3.11$).
2. Required Python packages.
3. Docker daemon connectivity.
4. Reachability of telemetry endpoints (`localhost:16686`, `localhost:9090`, `localhost:9200`).
5. Kill-switch status and safety configuration.

### 3.4 Running Unit Tests

Run the test suite to verify configuration loading, data models, kill-switch behavior, and approval gate:

```bash
pytest tests/
```

---

## 4. Emergency Kill-Switch Instructions

To instantly disengage the Incident Zero agent and block all remediation actions:

### Method 1: Environment Variable
Set `KILL_SWITCH_ENABLED=true` in `.env` and restart the agent.

### Method 2: Sentinel File (Zero-Downtime Trigger)
Touch the `.kill_switch` file in the solution root:

**Windows PowerShell:**
```powershell
New-Item -ItemType File -Path .kill_switch -Force
```

**Linux / macOS:**
```bash
touch .kill_switch
```

Any pending or subsequent remediation call will immediately abort with a `KillSwitchEngagedException` and record the kill-switch activation in `audit_logs/audit.jsonl`.

---

## 5. End-to-End Demonstration Execution

To demonstrate the full incident diagnosis and safety-governed remediation workflow:

### Option A: Turnkey Automated Demonstration (Recommended for Judges)
Runs multi-signal investigation against live telemetry (Prometheus, Jaeger, OpenSearch, Docker), performs root-cause analysis, evaluates human approval gate, executes safe dry-run remediation, and verifies recovery:

```powershell
python scripts/run_demo.py
```

### Option B: Interactive Human Approval Demonstration
Prompts the human operator in the terminal to explicitly approve or reject the proposed remediation action:

```powershell
python scripts/run_demo.py --interactive
```

### Option C: Emergency Kill-Switch Demonstration
Demonstrates instantaneous fail-closed halting of all remediation actions when the emergency kill-switch is engaged:

```powershell
python scripts/run_demo.py --test-kill-switch
```

### Option D: Direct Investigation by Alert String
Pass any custom incident alert directly to the agent:

```powershell
python -m src.agent --alert "Elevated p95 latency on checkout service"
```

### Option E: Live Telemetry Tools Smoke Test
Directly exercises all 7 observability tools against the live demo stack without running diagnosis:

```powershell
python -m src.agent --tools-only
```
