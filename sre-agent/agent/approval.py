"""Step 5 - ASK FOR HUMAN APPROVAL. Nothing changes without an explicit "yes".

Modes:
  cli    - prints diagnosis + plan, waits for the operator to type "yes" (default)
  web    - tiny local page http://localhost:8765 with Approve / Reject (stretch: chat-style approval)
  reject - never approve (safe default for unattended / hidden-test runs: diagnose + report only)
Timeout or anything other than "yes" = rejected -> escalate with findings.
"""
import html
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


def _record(decision, by, mode, note=""):
    return {"decision": decision, "by": by, "mode": mode, "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "note": note}


def describe(plan: dict) -> str:
    """Plain-English effect of the proposed action, shown to the human before they approve."""
    a, p = plan.get("action"), plan.get("params", {})
    return {"restart_service": f"restart the '{p.get('service')}' container (it is down for a few seconds)",
            "toggle_flag": f"set feature flag '{p.get('flag')}' to '{p.get('variant')}' (flagd reloads it live)",
            "throttle_load": f"set the load generator to {p.get('users')} users",
            "scale_service": f"scale '{p.get('service')}' to {p.get('replicas')} replicas"}.get(a, a)


def summary_text(diag: dict, plan: dict) -> str:
    rc = diag["root_cause"]
    lines = ["=" * 78, f"INCIDENT {diag['incident_id']}   status={diag['status']}   confidence={diag['confidence']}",
             f"ROOT CAUSE : {rc['service']}{' / ' + rc['component'] if rc.get('component') else ''} - {rc['fault_type']}",
             f"SUMMARY    : {rc['summary']}", "EVIDENCE   :"]
    for e in diag["evidence"]:
        mark = "ok " if e.get("verified") else "?? "
        lines.append(f"  [{mark}{e['source']:7}] {e['signal'][:150]}")
    if diag.get("alternative_hypotheses"):
        lines.append("ALTERNATIVES: " + " | ".join(diag["alternative_hypotheses"])[:300])
    lines.append("-" * 78)
    lines.append(f"PROPOSED ACTION: {plan['action']} {json.dumps(plan.get('params', {}))}")
    if plan.get("action") != "escalate":
        lines.append(f"WHAT HAPPENS   : {describe(plan)}, via the Action API")
    lines.append(f"REASON         : {plan.get('reason')}")
    lines.append(f"ROLLBACK       : {json.dumps(plan.get('rollback')) if plan.get('rollback') else 'none (escalate if not recovered)'}")
    if plan.get("action") != "escalate":
        lines.append("THEN           : watch error rate / p95 / container state until healthy for 2 polls; "
                     "roll back + escalate if not")
    lines.append("=" * 78)
    return "\n".join(lines)


def ask_cli(diag, plan, timeout=None) -> dict:
    print(summary_text(diag, plan))
    try:
        ans = input("Approve this action? Type 'yes' to execute, anything else rejects: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return _record("rejected", "operator", "cli", "no input")
    by = os.getenv("USER") or os.getenv("USERNAME") or "operator"
    if ans == "yes":
        return _record("approved", by, "cli")
    return _record("rejected", by, "cli", f"answer={ans!r}")


def ask_web(diag, plan, port=8765, timeout=600) -> dict:
    result = {}
    body = summary_text(diag, plan)

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            page = f"""<!doctype html><html><head><meta charset="utf-8"><title>Approve action</title>
<style>body{{font-family:system-ui;max-width:900px;margin:24px auto;padding:0 16px;background:#f6f7f9;color:#111}}
pre{{background:#fff;border:1px solid #ddd;padding:12px;white-space:pre-wrap;font-size:13px}}
button{{font-size:16px;padding:10px 22px;margin-right:10px;border:0;border-radius:6px;cursor:pointer}}
.y{{background:#1a7f37;color:#fff}}.n{{background:#cf222e;color:#fff}}</style></head><body>
<h2>On-call approval: {html.escape(diag['incident_id'])}</h2><pre>{html.escape(body)}</pre>
<form method="post"><input name="who" placeholder="your name" required>
<button class="y" name="d" value="approved">Approve</button><button class="n" name="d" value="rejected">Reject</button>
</form></body></html>"""
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(page.encode())

        def do_POST(self):
            from urllib.parse import parse_qs
            q = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", 0))).decode())
            result.update(_record(q.get("d", ["rejected"])[0], q.get("who", ["?"])[0], "web"))
            self.send_response(200)
            self.end_headers()
            self.wfile.write(f"Recorded: {result['decision']}. You can close this tab.".encode())

    srv = HTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(body)
    print(f"Waiting for approval at http://localhost:{port}  (timeout {timeout}s)")
    t = time.time()
    while not result and time.time() - t < timeout:
        time.sleep(0.5)
    srv.shutdown()
    return result or _record("rejected", "timeout", "web", f"no decision in {timeout}s")


def ask(diag, plan, mode="cli") -> dict:
    if mode == "reject":
        print(summary_text(diag, plan))
        return _record("rejected", "policy", "reject", "unattended mode: actions require a human")
    if mode == "web":
        return ask_web(diag, plan)
    return ask_cli(diag, plan)
