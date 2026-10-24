# Architecture (1 page)

```
 OpenTelemetry Astronomy Shop (docker compose, own laptop)          faultctl (organisers) injects faults
 frontend-proxy → frontend → checkout → payment / cart → valkey-cart / product-catalog → astronomy-db ...
 all services ──OTLP──► otel-collector ──► Prometheus (span metrics) · Jaeger (traces) · OpenSearch (logs)
        │ PromQL                 │ Jaeger API             │ _search / docker logs        │ docker ps/inspect/stats (read-only)
        ▼                        ▼                        ▼                              ▼
 ┌──────────────────────────────────── TOOLS (agent/toolbox.py, 14 read-only tools) ───────────────────────────┐
 │ get_service_health · get_failing_operations · get_service_detail · query_prometheus                         │
 │ get_error_origins · get_slow_operations · get_trace(id) · get_error_log_summary · search_logs(svc)          │
 │ get_runtime_events · get_container_health(svc) · get_deploy_history · get_dependencies(svc) ·               │
 │ similar_past_incidents          every call logged → runs/<id>/tool_calls.jsonl; failures returned, never crash│
 └─────────────────────────────────────────────────────────────────────────────────────────────────────────────┘
 1 DETECT   detect.py: every 20 s, rules on error rate / p95 / traffic vs 30-min baseline + container state;
            fires after 2 bad polls → alert {services, reasons}
 2 INVESTIGATE  investigate.py: LLM tool-calling loop (≤14 calls). The model picks the next tool from what it has
            found (health → error origins → drill into suspect → check its dependencies) and calls submit_diagnosis.
            No LLM / LLM fails 3× → deterministic investigator (rules.py ranking + targeted drill-down).
 3 DIAGNOSE pydantic schema check → evidence_check.py (every cited trace ID / log line / number must exist in
            tool results; unverified items flagged, dropped, −0.1 confidence each) → reviewer: telemetry-only
            rules ranking; disagreement ×0.8 → confidence = ½ LLM + ½ evidence strength
            → status: diagnosed | escalated (conf < 0.6, unknown, nothing verified) | no_incident
 4 PROPOSE  runbook.py: one allowlisted action for (service, fault_type) + reason + rollback, else escalate
 5 APPROVE  approval.py: CLI "yes" / web page / reject-mode. Dry-run mode skips the action entirely.
 6 ACT      actions.py → Action API only. Checks allowlist, approval record and kill switch (runs/KILL) before
            every call; logs to actions.jsonl. The approval record is sent with the request.
            action_api/server.py (separate process, :8000) re-checks approval + kill switch + allowlist,
            then docker restart | flagd defaultVariant | Locust /swarm | kubectl scale.
                                                   VERIFY recovery.py: 1-min metrics until 2 healthy polls
            (≤4 min) → resolved, else rollback (if reversible, approved) + escalate
 7 REPORT   report.py: output.json (official schema) + report.md (timeline, root cause, evidence, action,
            verification, prevention) → memory.py stores it for repeat incidents
```

**How it decides the root cause.** Errors and latency propagate *upstream*, so the root cause is the most
*downstream* component with its *own* evidence: an error span with no failing child; a failing call to a
dependency that is unreachable (the callee is blamed, e.g. checkout → payment "Unavailable" + payment
container exited); its own error logs; CPU/memory far above its healthy baseline; restarts/OOM; high
*self* time on a span (latency spent in that service or on the wire to its callee). Upstream services
with a failing dependency are discounted as victims (`config/services.yaml` dependency graph).

**Safety controls.** Read-only tools · allowlist · human approval for every change · dry run · kill switch ·
confidence gate with escalation · evidence verification against raw data · recovery verification with rollback ·
complete audit trail (alert, tool calls, approval, action log, verification) per incident. Feature-flag settings
are never read for diagnosis.

**Stretch goals implemented.** Incident memory (`similar_past_incidents`) · reviewer (independent rules ranking
cross-checks the LLM) · calibrated confidence (`eval` prints a calibration table) · chat-style approval
(`--approve web`) · prevention suggestions in every report.
