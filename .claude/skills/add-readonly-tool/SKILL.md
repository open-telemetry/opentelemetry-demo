---
name: add-readonly-tool
description: Add a new read-only telemetry or platform tool for the Incident Zero agent (for example get_metrics, search_traces, search_logs, container_health, deploy_history) using the shared return envelope in docs/hackathon/interfaces.md. Use when the user asks to add or scaffold a tool the agent can call.
---

# Add a read-only tool

Tools are the agent's eyes. Each one is read-only, compact, and returns the shared envelope.

## 1. Preconditions
- An issue exists with concrete acceptance criteria. Use `start-issue` if not.
- The signature matches `docs/hackathon/interfaces.md`. If it must differ, stop and open an `interface-change` issue first.
- You have read the real endpoint's response or can call it now. Do not guess the response shape.

## 2. Write the function
- Typed parameters and a return type. Use `dict` for the envelope.
- A docstring the LLM reads: what it does, when to use it, and what the fields mean. Keep it short.
- Return the envelope:
  ```python
  {
    "tool": "<name>",
    "ok": True,            # False on error
    "query": "...",        # exact query or args, for citation
    "summary": "...",      # short human-readable finding
    "evidence": [          # copied verbatim from the source
      {"kind": "metric|trace|log|container|deploy", "ref": "...", "value": "..."}
    ],
    "error": None
  }
  ```
- Return summaries, top-N, and deltas vs baseline. Never return raw megabytes.
- Read endpoints from environment variables. No hardcoded URLs or ports.
- Never call anything that changes state. Never read flagd.

## 3. Tests
In `tests/` mirroring the source path:
- Happy path with a recorded, real sample response.
- Failure: endpoint down returns `ok: False` with an `error` message, not an exception.
- Edge case: empty result returns `ok: True` with an empty `evidence` list.
- Compactness: a large fixture is truncated to the limit.

## 4. Verify
Use the `verify-change` skill. Then use the `check-rules` skill.

## Never
- Invent a field that the source does not return.
- Put a flag read in a tool "for context".
