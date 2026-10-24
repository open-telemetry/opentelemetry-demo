"""Checkpoint 1 'Eyes': run the broad tools and print what is wrong in plain words (no diagnosis yet)."""
from agent import rules


def symptom_summary(session) -> str:
    b = rules.build_bundle(session)
    L = []
    h = b["health"]
    if "error" in h:
        L.append(f"METRICS: could not read ({h['error']})")
    else:
        L.append(f"METRICS (last {h['window']} vs {h['baseline_offset']} ago):")
        L += [f"  - {a['service']}: {a['detail']}" for a in h["anomalies"][:8]] or ["  - no metric anomalies"]
    fo = b["failing_ops"]
    for op in (fo if isinstance(fo, list) else [])[:4]:
        L.append(f"  - failing operation {op['service']} / {op['operation']}: {op['errors_per_s']}/s")
    t = b["origins"]
    if "error" in t:
        L.append(f"TRACES: could not read ({t['error']})")
    else:
        L.append(f"TRACES: {t['traces_sampled']} traces sampled")
        for o in t["error_origins"][:5]:
            msg = f' "{o["top_messages"][0]}"' if o["top_messages"] else ""
            to = f" calling {o['calls_to'][0]}" if o.get("calls_to") else ""
            L.append(f"  - errors originate at {o['where']}{to} ({o['count']} spans){msg} "
                     f"e.g. trace {o['example_trace_ids'][0] if o['example_trace_ids'] else '-'}")
    s = b["slow"]
    if "error" not in s:
        for x in s["slowest_by_self_time"][:3]:
            L.append(f"  - slowest self-time: {x['where']} {x['max_self_ms']}ms")
    lg = b["logs"]
    if "error" in lg:
        L.append(f"LOGS: could not read ({lg['error']})")
    else:
        L.append(f"LOGS ({lg['source']}, {lg['log_lines_scanned']} lines):")
        for svc, v in list(lg["error_logs_by_service"].items())[:5]:
            L.append(f"  - {svc}: {v['error_lines']} error lines, e.g. {v['top_messages'][0][:130]}")
        if not lg["error_logs_by_service"]:
            L.append("  - no error logs")
    rt = b["runtime"]
    if "error" in rt:
        L.append(f"RUNTIME: could not read ({rt['error']})")
    else:
        L.append("RUNTIME / DEPLOYS:" + ("" if rt["baseline_available"] else " (no healthy baseline yet - run `baseline`)"))
        L += [f"  - {e}" for e in rt["events"][:8]] or ["  - nothing unusual"]
    L.append("VERDICT: " + ("looks healthy - no incident" if rules.is_quiet(b) else "something is wrong - run `diagnose`"))
    return "\n".join(L)
