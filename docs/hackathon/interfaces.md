# Shared interfaces (contracts between modules)

> Changing anything here needs an `interface-change` issue and a 👍 from every affected module owner (see AGENTS.md §4).
> These are **drafts** — fill in real shapes once we've read the template repo and the organisers' JSON schema.

## Tool return envelope (all read-only tools)
Defined in `oncall/models.py` (F01). Build it with `make_result()` / `make_error()`; tools never raise.
```python
{
  "tool": "get_metrics",          # tool name
  "query": {...},                 # the exact args used (dict, for evidence citation)
  "summary": "short human-readable finding",   # <= 1500 chars
  "evidence": [                   # <= 20 items, copied verbatim from the source
    {"id": "<see formats below>", "text": "...", "ts": "<iso ts> | None"}
  ],
  "ok": True,                     # False on error
  "error": None
}
```
Evidence id formats: `metric:<metric>:<series>@<iso_ts>` (series = `<service>` or `<service>/<span>`; the PromQL is in `query["promql"]`), `trace:<trace_id>/span:<span_name>`,
`log:<service>@<iso_ts>`, `container:<name>`, `deploy:<id>`.

## Alert
```python
{"id": str, "ts": str, "service": str | None,
 "signal": "error_rate" | "latency" | "container" | "manual",
 "value": float | None, "threshold": float | None,
 "description": str, "source": "detector" | "manual"}
```

## Diagnosis (owner: brain, F12)
Defined in `oncall/models.py`. Produced by `oncall.agent.diagnosis.diagnose(run, alert, llm)`;
consumed by F13 (evidence validator), F15 (confidence) and F16 (report).
```python
{"component": str | None,            # root-cause service/container; never a client (load-generator)
 "category": Category,               # app_error | dependency_unavailable | container_down |
                                     # resource_cpu | resource_memory | network_degradation |
                                     # traffic_surge | upstream_propagation | unknown |
                                     # no_incident (healthy system)
 "cause": str,                       # one-sentence specific cause
 "confidence": float,                # 0..1, LLM estimate (F15 adjusts)
 "evidence_ids": list[str],          # ids from the run log (F13 drops unknown ones)
 "affected_services": list[str],     # symptoms / blast radius
 "alternatives": [{"hypothesis": str, "rejected_because": str}],
 "decision": "act" | "escalate" | "no_action",   # no_action = healthy, nothing to do
 "reasoning": str}                   # <= 800 chars, cites evidence ids
```
On invalid LLM output (after one retry) or an LLM error, `diagnose()` returns an escalate
Diagnosis with `category="unknown"` and `component=None`; it never raises.

## Tool registry
`@register_tool(name, description, params)` in `oncall/tools/registry.py`, where `params` holds JSON-schema
`properties` and `required`. It fills `TOOLS[name]` and `TOOL_SCHEMAS[name]`
(`{"name", "description", "input_schema"}`). Each tool module adds one import line under
`# --- tool imports ---` in `oncall/tools/__init__.py`.

## Tools (owner: tools / platform)
- `get_metrics(service: str, metric: str, window_min: int = 15) -> dict`
- `search_traces(service: str, only_errors: bool = True, limit: int = 20) -> dict`
- `search_logs(service: str, level: str = "error", window_min: int = 15, limit: int = 50) -> dict`
- `container_health(service: str | None = None) -> dict`
- `deploy_history(window_min: int = 60) -> dict`

## Safety / action (owner: safety)
- `propose_action(action: str, target: str, params: dict, reason: str) -> Proposal`  — validates against allowlist
- `request_approval(proposal: Proposal, diagnosis: dict) -> bool`
- `execute(proposal: Proposal, dry_run: bool) -> dict`
- `verify_recovery(service: str, baseline: dict, timeout_s: int) -> dict`
- `kill_switch_engaged() -> bool`

## Incident report
Must validate against the organisers' JSON schema in the template (path: `TBD`). Never edit that schema.
