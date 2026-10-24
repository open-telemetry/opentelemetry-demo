# oncall-agent Service

The `oncall-agent` service is the autonomous reasoning, detection, approval gate, and reporting engine of the AI On-Call Engineer.

---

## Service Overview

- **Port:** `8200`
- **Dashboard:** `http://localhost:8200/` (static HTML/CSS/JS dashboard)
- **Framework:** FastAPI with Python 3.12
- **Data Directory:** `/data` (persisted to host `./oncall-data/agent:/data`)
- **Memory Limits:** 400MB RAM limit enforced via Docker Compose

---

## Directory Structure

```
src/oncall-agent/
├── app/
│   ├── approval.py           # State machine, incident store, HMAC token minting
│   ├── config.py             # Environment configurations and service endpoints
│   ├── detector.py           # Anomaly detector polling Prometheus span metrics
│   ├── evidence.py           # Raw evidence ledger (/data/incidents/<id>/evidence.jsonl)
│   ├── executor.py           # Action API client, settle wait, verification, rollback
│   ├── investigator.py       # LLM tool-calling loop and prompt management
│   ├── llm.py                # Ollama/OpenAI-compatible LLM client
│   ├── main.py               # FastAPI application, REST endpoints, background loops
│   ├── memory.py             # SQLite incident memory engine & report re-indexing
│   ├── prevention.py         # Prevention engine & live PromQL validation
│   ├── proposer.py           # Runbook proposal selection and validation
│   ├── reporter.py           # JSON/Markdown report builder and schema validator
│   ├── runbook.py            # Runbook loader and param resolution
│   ├── runbook.yaml          # Allowlisted runbook catalog (least-invasive first)
│   ├── schemas/              # JSON Schemas (incident_report.schema.json, Draft 2020-12)
│   ├── static/               # Approval web dashboard (index.html)
│   └── tools/                # Read-only telemetry tool implementations
├── Dockerfile                # Python 3.12-slim container definition
├── requirements.txt          # Python dependencies (fastapi, httpx, jsonschema, etc.)
└── tests/                    # Pytest unit & integration test suites
```

---

## Running Locally for Development

```bash
cd src/oncall-agent
pip install -r requirements.txt
PYTHONPATH=. pytest tests/ -v
PYTHONPATH=. uvicorn app.main:app --host 0.0.0.0 --port 8200 --reload
```

---

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `ACTION_API_URL` | `http://action-api:8201` | URL of the Action API control plane |
| `ACTION_API_SECRET` | `change-me-locally` | Shared HMAC-SHA256 secret for approval tokens |
| `PROMETHEUS_URL` | `http://prometheus:9090` | Prometheus query API endpoint |
| `JAEGER_URL` | `http://jaeger:16686` | Jaeger REST API endpoint |
| `OPENSEARCH_URL` | `http://opensearch:9200` | OpenSearch logging endpoint |
| `ONCALL_LLM_PROVIDER` | `ollama` | LLM backend provider (`ollama`) |
| `ONCALL_LLM_BASE_URL` | `http://host.docker.internal:11434` | Ollama API base URL |
| `ONCALL_LLM_MODEL` | `qwen2.5:7b-instruct` | Instruct LLM model name |
| `ONCALL_POLL_INTERVAL_S` | `30` | Detector polling frequency in seconds |
| `EVAL_AUTO_APPROVE` | `false` | Headless evaluation mode only (loudly logged) |
