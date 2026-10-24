"""Step 7 - REPORT: incident_report.json (official schema + full trail) and a readable report.md.

Includes: timeline, root cause, evidence, action taken, verification, and what would prevent a repeat
(stretch goal 5: prevention - code/config/alerting change).
"""
import json

PREVENTION = {
    "service_down": ["Add a liveness probe + restart policy (restart: unless-stopped) for the service.",
                     "Alert on 'request rate < 20% of baseline' per service, not only on error rate."],
    "crash_loop": ["Alert on container restart count > 2 in 10 min.",
                   "Add startup checks for required config/dependencies and fail with a clear log line."],
    "dependency_unavailable": ["Health-check the cache/DB and alert on it directly.",
                               "Add retries with backoff + a circuit breaker in callers; degrade gracefully."],
    "memory_leak": ["Alert on memory > 85% of limit and on memory growth slope.",
                    "Bound in-memory caches (max size / TTL); add a heap-usage metric and a load test."],
    "high_cpu": ["Alert on CPU > 3x baseline for 5 min; add a CPU limit + HPA where available.",
                 "Profile the hot path; guard expensive features behind flags with safe defaults."],
    "gc_pressure": ["Alert on JVM GC time ratio; size the heap; remove explicit System.gc() calls."],
    "application_error": ["Add an error-rate SLO alert per operation (not only per service).",
                          "Add a regression test for the failing operation; require flag changes via review."],
    "cache_failure": ["Alert on cache hit ratio drop; bound cache growth; fall back to the source on miss."],
    "db_contention": ["Alert on DB lock wait / query latency; shorten transactions; add indexes/timeouts."],
    "queue_backlog": ["Alert on Kafka consumer lag; autoscale consumers; add dead-letter handling."],
    "latency": ["Alert on p95 per operation vs baseline; add timeouts and budgets to outgoing calls."],
    "network_fault": ["Alert on client-span latency per dependency link; add timeouts/retries with jitter."],
    "traffic_flood": ["Rate-limit at frontend-proxy (Envoy local rate limit); autoscale frontend.",
                      "Alert on request rate > 3x baseline."],
    "readiness_failure": ["Fix the readiness probe; alert on unhealthy containers."],
    "resource_starvation": ["Set CPU/memory requests and limits from measured usage; alert on throttling."],
    "unknown": ["Add the missing telemetry that would have made this diagnosable (see escalation reason)."],
}


def build(alert, diagnosis, meta, plan, approval, action_result, verification, rollback, outcome, official) -> dict:
    return {"incident_id": diagnosis["incident_id"], "detected_at": diagnosis["detected_at"], "alert": alert,
            "outcome": outcome, "official_output": official, "diagnosis": diagnosis,
            "action_plan": plan, "approval": approval, "action_result": action_result,
            "verification": verification, "rollback": rollback,
            "prevention": PREVENTION.get(diagnosis["root_cause"]["fault_type"], PREVENTION["unknown"]),
            "agent": {"llm_used": meta.get("llm_used"), "tool_calls": meta.get("tool_calls"),
                      "investigation_seconds": meta.get("seconds"), "review": meta.get("review"),
                      "llm_errors": meta.get("llm_errors")}}


def markdown(r: dict, tool_calls: list) -> str:
    d, rc = r["diagnosis"], r["diagnosis"]["root_cause"]
    out = [f"# Incident report - {r['incident_id']}", "",
           f"**Outcome:** {r['outcome']}  |  **Status:** {d['status']}  |  **Confidence:** {d['confidence']}", "",
           "## Root cause",
           f"**{rc['service']}**{' (' + rc['component'] + ')' if rc.get('component') else ''} - `{rc['fault_type']}`  ",
           rc["summary"], ""]
    if d.get("escalation_reason"):
        out += [f"> **Escalated to a human:** {d['escalation_reason']}", ""]
    if d.get("reasoning"):
        out += ["**Reasoning:** " + d["reasoning"], ""]
    out += ["## Evidence", "| # | Source | Signal | Reference | Checked |", "|---|---|---|---|---|"]
    for i, e in enumerate(d["evidence"], 1):
        out.append(f"| {i} | {e['source']} | {e['signal'][:160].replace('|', '/')} | "
                   f"`{(e.get('reference') or '')[:60].replace('|', '/')}` | {'yes' if e.get('verified') else 'NOT FOUND'} |")
    out += ["", f"**Affected services:** {', '.join(d.get('affected_services') or []) or '-'}  ",
            f"**Alternative hypotheses:** {'; '.join(d.get('alternative_hypotheses') or []) or '-'}", "",
            "## Timeline"]
    a = r["alert"]
    out.append(f"- {a.get('fired_at')} - alert `{a.get('alert_id')}` ({a.get('source')}): "
               + "; ".join(a.get("reasons", []))[:300])
    out.append(f"- investigation: {len(tool_calls)} tool calls, {r['agent']['investigation_seconds']}s, "
               f"LLM {'used' if r['agent']['llm_used'] else 'not used (rule-based)'}")
    for c in tool_calls:
        out.append(f"  - #{c['n']} `{c['name']}({json.dumps(c['args'])})`{'' if c['ok'] else ' - FAILED'}")
    p = r["action_plan"] or {}
    out.append(f"- proposed: **{p.get('action')}** {json.dumps(p.get('params', {}))} - {p.get('reason')}")
    if r["approval"]:
        ap = r["approval"]
        out.append(f"- approval: **{ap['decision']}** by {ap['by']} ({ap['mode']}) at {ap['at']}")
    if r["action_result"]:
        ar = r["action_result"]
        out.append(f"- action: {ar.get('result')}{' (dry run)' if ar.get('dry_run') else ''} at {ar.get('at')}")
    v = r["verification"]
    if v:
        out.append(f"- verification: {'RECOVERED' if v['recovered'] else 'NOT recovered'} after {v['after_seconds']}s")
        if v.get("warnings"):
            out.append(f"- verification warnings (not blocking): {'; '.join(v['warnings'])}")
    if r["rollback"]:
        out.append(f"- rollback: {r['rollback'].get('result')} {json.dumps(r['rollback'].get('params', {}))}")
    out += ["", "## Action taken",
            {"resolved": "Approved action executed and recovery verified.",
             "dry_run": "Dry run only - nothing was changed.",
             "rejected": "Human rejected the proposed action - nothing was changed.",
             "escalated": "Escalated to a human with the findings above - nothing was changed.",
             "not_recovered": "Action executed but the system did not recover; rolled back if possible and escalated.",
             "action_failed": "The Action API call failed; escalated.",
             "killed": "Kill switch engaged - no action executed.",
             "no_incident": "No incident confirmed - nothing was changed."}.get(r["outcome"], r["outcome"]), "",
            "## What would prevent a repeat"] + [f"- {x}" for x in r["prevention"]]
    return "\n".join(out) + "\n"
