# Shared interfaces (contracts between modules)

> Changing anything here needs an `interface-change` issue and a 👍 from every affected module owner (see AGENTS.md §4).
> These are **drafts** — fill in real shapes once we've read the template repo and the organisers' JSON schema.

## Tool return envelope (all read-only tools)
```python
{
  "tool": "get_metrics",          # tool name
  "ok": True,                     # False on error
  "query": "...",                 # the exact query/args used (for evidence citation)
  "summary": "short human-readable finding",
  "evidence": [                   # concrete, citable items copied verbatim from the source
    {"kind": "metric|trace|log|container|deploy", "ref": "<query|trace_id|log ts>", "value": "..."}
  ],
  "error": None
}
```

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
