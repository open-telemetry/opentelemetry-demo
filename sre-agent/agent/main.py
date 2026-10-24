"""SRE agent CLI.

  python -m agent.main check                     # CP0: Prometheus / Jaeger / OpenSearch / Docker / LLM / Action API
  python -m agent.main baseline                  # snapshot healthy CPU/memory per container (run when healthy)
  python -m agent.main see                       # CP1: symptom summary (Eyes)
  python -m agent.main diagnose                  # CP2: investigate now -> diagnosis + proposed action (no change)
  python -m agent.main run                       # CP3: watch -> alert -> diagnose -> approve -> act -> verify -> report
  python -m agent.main run --dry-run             #      same, but only logs what it WOULD do
  python -m agent.main respond                   #      full loop now, without waiting for the watcher
  python -m agent.main kill | unkill | status    # kill switch
  python -m agent.main eval                      # practice-set accuracy + confidence calibration table
  python -m agent.main export                    # copy runs/* reports into incident_reports/ (deliverable)
Options: --no-llm  --approve cli|web|reject  --expect <service>[:<fault_type>]  --replay runs/<id>/snapshot.json
"""
import argparse
import json
import sys
import time

import requests

from agent import config


def _log(*a):
    print(*a, file=sys.stderr, flush=True)


def cmd_check(_):
    from agent import llm
    from agent.actions import api_cfg, kill_engaged
    from agent.tools import deploys, logs, metrics, traces

    def probe(name, fn):
        try:
            print(f"  [OK]   {name}: {fn()}")
        except Exception as e:
            print(f"  [FAIL] {name}: {type(e).__name__}: {str(e)[:160]}")

    print("Connectivity:")
    probe("prometheus", lambda: f"{len(metrics.list_metric_names('traces_span_metrics'))} span-metric names")
    probe("jaeger", lambda: f"{len(traces.services())} services: {', '.join(traces.services()[:8])}...")
    probe("opensearch", lambda: requests.get(logs._opensearch_url() + "/_cat/indices/otel-logs-*",
                                             timeout=5).text.strip()[:100] or "no index yet")
    probe("docker", lambda: f"{len(deploys.containers())} containers")
    probe("llm", lambda: llm.ping() if llm.available() else "no LLM_API_KEY set (agent will run rule-based)")
    probe("action api", lambda: f"{api_cfg()['base_url']} -> HTTP "
                                f"{requests.get(api_cfg()['base_url'], timeout=5).status_code} (mode={config.ACTION_API_MODE})")
    print(f"  kill switch: {'ENGAGED' if kill_engaged() else 'off'}")
    from agent.tools.metrics import HEALTH_BASELINE_FILE
    ok = deploys.BASELINE_FILE.exists() and HEALTH_BASELINE_FILE.exists()
    print(f"  healthy baseline: {'yes' if ok else 'NO - run `baseline` while healthy'}")


def cmd_baseline(_):
    from agent.tools import deploys, metrics
    u = deploys.save_baseline()
    print(f"saved healthy runtime baseline for {len(u)} containers -> {deploys.BASELINE_FILE}")
    m = metrics.save_health_baseline()
    print(f"saved healthy metrics baseline for {len(m)} services -> {metrics.HEALTH_BASELINE_FILE}")
    busy = sorted(((v["p95_ms"], s) for s, v in m.items() if v["p95_ms"] > 1000), reverse=True)[:5]
    if busy:
        print("  note: already slow while 'healthy' (laptop under load?): "
              + ", ".join(f"{s} p95 {int(p)}ms" for p, s in busy))


def cmd_see(a):
    from agent import toolbox
    from agent.collector import symptom_summary
    s = toolbox.Session(replay=_replay(a))
    print(symptom_summary(s))
    if a.json:
        print(json.dumps(s.snapshot(), indent=1, default=str))


def _replay(a):
    if getattr(a, "replay", None):
        return json.loads(open(a.replay, encoding="utf-8").read())
    return None


def _manual_alert(a, source="manual"):
    from agent import detect
    if _replay(a):
        ev = {"reasons": ["replayed bundle"], "services": []}
    else:
        ev = detect.snapshot()["eval"]
        if not ev["firing"]:
            ev["reasons"] = ev["reasons"] or ["manual trigger (no alert rule firing right now)"]
    return detect.new_alert(ev, source)


def _record_practice(rep, expect):
    if not expect:
        return
    svc, _, ft = expect.partition(":")
    rc = rep["diagnosis"]["root_cause"]
    row = {"incident_id": rep["incident_id"], "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "expected": svc,
           "expected_fault": ft or None, "got": rc["service"], "got_fault": rc["fault_type"],
           "status": rep["diagnosis"]["status"], "confidence": rep["diagnosis"]["confidence"],
           "outcome": rep["outcome"], "correct": rc["service"] == svc,
           "fault_correct": (rc["fault_type"] == ft) if ft else None}
    with open(config.RUNS / "practice_results.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    _log(f"\n{'CORRECT' if row['correct'] else 'WRONG'} service (expected {svc}, got {rc['service']})")


def cmd_diagnose(a):
    from agent.pipeline import run_incident
    rep = run_incident(_manual_alert(a), use_llm=not a.no_llm, mode="diagnose", replay=_replay(a), log=_log)
    print(json.dumps(rep["official_output"], indent=1))
    _record_practice(rep, a.expect)


def cmd_respond(a):
    from agent.pipeline import run_incident
    rep = run_incident(_manual_alert(a), use_llm=not a.no_llm, mode="dry-run" if a.dry_run else "act",
                       approve_mode=a.approve, replay=_replay(a), log=_log)
    print(json.dumps(rep["official_output"], indent=1))
    _record_practice(rep, a.expect)


def cmd_run(a):
    from agent import detect
    from agent.pipeline import run_incident
    while True:
        alert = detect.watch(log=_log)
        rep = run_incident(alert, use_llm=not a.no_llm, mode="dry-run" if a.dry_run else "act",
                           approve_mode=a.approve, log=_log)
        print(json.dumps(rep["official_output"], indent=1))
        _record_practice(rep, a.expect)
        if a.once:
            return
        _log(f"cooldown {a.cooldown}s before watching again...")
        time.sleep(a.cooldown)


def cmd_kill(a):
    from agent import actions
    actions.engage_kill(a.reason)
    print(f"KILL SWITCH ENGAGED ({config.KILL_FILE}). No action will execute until `unkill`.")


def cmd_unkill(_):
    from agent import actions
    actions.release_kill()
    print("kill switch released")


def cmd_status(_):
    from agent import actions
    print(f"kill switch: {'ENGAGED' if actions.kill_engaged() else 'off'}")
    p = config.RUNS / "action_log.jsonl"
    rows = p.read_text(encoding="utf-8").splitlines()[-5:] if p.exists() else []
    print("last actions:" if rows else "no actions yet")
    for r in rows:
        print("  " + r[:200])


def cmd_action(a):
    """Manual Action API test: python -m agent.main action restart_service service=ad [--dry-run]"""
    from agent import actions, approval
    params = dict(kv.split("=", 1) for kv in a.params)
    if a.dry_run:
        print(json.dumps(actions.execute(a.name, params, dry_run=True), indent=1))
        return
    appr = approval.ask_cli({"incident_id": "manual", "status": "manual", "confidence": 1.0,
                             "root_cause": {"service": params.get("service", "-"), "fault_type": "unknown",
                                            "summary": "manual action test"}, "evidence": []},
                            {"action": a.name, "params": params, "reason": "manual test"})
    print(json.dumps(actions.execute(a.name, params, approval=appr), indent=1))


def cmd_eval(_):
    p = config.RUNS / "practice_results.jsonl"
    if not p.exists():
        print("no practice results yet - run `diagnose --expect <service>` after injecting each incident")
        return
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"| incident | expected | got | fault | status | conf | correct |\n|---|---|---|---|---|---|---|")
    for r in rows:
        print(f"| {r['incident_id']} | {r['expected']} | {r['got']} | {r['got_fault']} | {r['status']} | "
              f"{r['confidence']} | {'yes' if r['correct'] else 'no'} |")
    n = len(rows)
    acc = sum(r["correct"] for r in rows) / n
    print(f"\nservice accuracy: {sum(r['correct'] for r in rows)}/{n} = {acc:.0%}")
    print("\ncalibration (stated confidence vs how often it was right):")
    for lo, hi in ((0, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)):
        b = [r for r in rows if lo <= r["confidence"] < hi]
        if b:
            print(f"  conf {lo:.1f}-{min(hi, 1):.1f}: {len(b)} runs, right {sum(r['correct'] for r in b) / len(b):.0%}")
    wrong_conf = [r for r in rows if not r["correct"] and r["status"] == "diagnosed"]
    esc = [r for r in rows if r["status"] != "diagnosed"]
    print(f"\nconfident-and-wrong: {len(wrong_conf)}   escalated: {len(esc)}")


def cmd_export(_):
    """Copy every practice incident's official output + readable report into incident_reports/ (committed)."""
    import shutil
    dest = config.ROOT / "incident_reports"
    dest.mkdir(exist_ok=True)
    n = 0
    for d in sorted(config.RUNS.glob("inc-*")):
        if (d / "output.json").exists():
            shutil.copy(d / "output.json", dest / f"{d.name}.json")
            shutil.copy(d / "report.md", dest / f"{d.name}.md")
            n += 1
    print(f"exported {n} incidents -> {dest}")


def cmd_schema_check(a):
    from agent.schema import validate_official
    obj = json.loads(open(a.file, encoding="utf-8").read())
    probs = validate_official(obj)
    if not config.OUTPUT_SCHEMA_FILE.exists():
        print("config/output_schema.json not found - copy the organisers' schema there first")
    print("VALID" if not probs else "INVALID:\n  " + "\n  ".join(probs))


def main():
    p = argparse.ArgumentParser(prog="sre-agent", description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check").set_defaults(fn=cmd_check)
    sub.add_parser("baseline").set_defaults(fn=cmd_baseline)
    s = sub.add_parser("see")
    s.add_argument("--json", action="store_true")
    s.add_argument("--replay")
    s.set_defaults(fn=cmd_see)

    def common(x):
        x.add_argument("--no-llm", action="store_true", help="rule-based only")
        x.add_argument("--expect", help="practice: expected root-cause service[:fault_type]")
        return x

    d = common(sub.add_parser("diagnose"))
    d.add_argument("--replay", help="replay a recorded snapshot.json instead of live telemetry")
    d.set_defaults(fn=cmd_diagnose)
    for name, fn in (("respond", cmd_respond), ("run", cmd_run)):
        r = common(sub.add_parser(name))
        r.add_argument("--dry-run", action="store_true", help="log the action, change nothing")
        r.add_argument("--approve", default="cli", choices=["cli", "web", "reject"])
        if name == "run":
            r.add_argument("--once", action="store_true")
            r.add_argument("--cooldown", type=int, default=180)
        else:
            r.add_argument("--replay")
        r.set_defaults(fn=fn)
    k = sub.add_parser("kill")
    k.add_argument("--reason", default="manual")
    k.set_defaults(fn=cmd_kill)
    sub.add_parser("unkill").set_defaults(fn=cmd_unkill)
    sub.add_parser("status").set_defaults(fn=cmd_status)
    ac = sub.add_parser("action")
    ac.add_argument("name")
    ac.add_argument("params", nargs="*")
    ac.add_argument("--dry-run", action="store_true")
    ac.set_defaults(fn=cmd_action)
    sub.add_parser("eval").set_defaults(fn=cmd_eval)
    sub.add_parser("export").set_defaults(fn=cmd_export)
    sc = sub.add_parser("schema-check")
    sc.add_argument("file")
    sc.set_defaults(fn=cmd_schema_check)
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
