# Incident agent (Day 1): how it works and how to run it

Code lives in `src/agent/`. Day 1 scope: investigate and diagnose only. The agent never changes the system.

| File | Purpose |
|---|---|
| `llm.py` | The only provider-specific file. `anthropic`, `openai` or `gemini` (OpenAI-compatible endpoint), with retry and exponential backoff on rate limits, 5xx and network errors (honours `retry-after`) |
| `tools.py` | The 8 observability tools (tool interface): `system_overview`, `get_service_metrics`, `dependency_map`, `search_traces`, `get_trace`, `search_logs`, `container_health`, `deploy_history` |
| `agent.py` | Phase 1: bounded tool-calling loop (max 12 tool calls). Phase 2: one diagnosis call from the stored transcript, plus one retry if output or citations are invalid |
| `transcript.py` | Stored record of every tool call and result; builds the index of citable evidence |
| `guards.py` | Diagnosis JSON shape, citation validator, deterministic confidence gate |
| `report.py` | Maps the diagnosis to `config/incident_schema.json` and validates it |
| `eval_harness.py` | Runs practice incidents (via `FAULTCTL_CMD`) and prints a pass/fail table |

## Setup

```bash
cd bosch-incident-zero
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt anthropic openai
```

`.env` (git-ignored) needs `LLM_PROVIDER`, `LLM_MODEL`, `LLM_API_KEY` and, for Gemini, `LLM_BASE_URL`.
`JAEGER_URL` defaults to `http://localhost:8080` (the demo's proxy). OpenSearch's host port is random, so the
tools discover it with `docker port opensearch 9200` when the configured URL does not answer.

## Run

```bash
.venv/bin/python -m src.agent --tools-only                      # every tool once against the live stack, no LLM
.venv/bin/python -m src.agent --alert "Error rate above 5% on checkout"
.venv/bin/python -m pytest tests/ -q
```

Each run writes `incident_output/<incident-id>/transcript.json` and `report.json`.

## Guards

- **Tool status**: every result is `ok`, `no_data`, `source_unavailable` or `error`. Missing data is never reported as healthy.
- **Citations**: every cited trace ID, `span:` ref, `log:` ref (and quoted text), `metric:` ref (and value, ±2%) and
  `container:` ref must appear in a stored tool result. Trace-like IDs in the prose are checked too. On failure the
  model is re-asked once; anything still invalid is dropped and confidence is capped.
- **Confidence gate**: high = two validated signal types + one alternative ruled out + no invalid citations;
  medium = one validated signal type + at least one more validated item; otherwise low, which escalates.
  The report never gets a placeholder trace ID: with no validated trace, `evidence.trace_ids` stays empty and the
  schema check reports it.
- **Rules**: no tool reads flagd or flag state. Flag services, flag-related span attributes, events, log lines and
  metric names are stripped from every tool result (`strip_flag_data`). Nothing writes to the system.

## Status of API assumptions (2026-10-23)

- verified-live: Prometheus span-metrics and container metrics, Jaeger v3 search and single-trace endpoints,
  OpenSearch log fields, `docker ps` / `docker inspect`, Gemini tool calling (`gemini-3.5-flash`), one full agent run.
- pending: error-path shapes during a real injected incident (failing spans with status code 2, error logs, a
  stopped container). No official `faultctl` has been available yet, so no practice incident has been scored.
- unavailable: deploy history (no source provided; the tool returns `source_unavailable`).

## Known limitations

- `system_overview` compares against the same window 30 minutes earlier; right after a stack restart there is no baseline.
- `dependency_map` is the static demo topology, not live-observed.
- The report follows the team schema in `config/incident_schema.json`; swap `report.build_report` when the organisers' template schema is available.
