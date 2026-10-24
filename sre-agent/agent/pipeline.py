"""One incident, end to end:
  alert -> investigate (tools) -> diagnose (checked, calibrated) -> propose -> approve -> act -> verify
        -> rollback/escalate if needed -> report.   Everything lands in runs/<incident_id>/.

Files written per incident:
  alert.json            what fired
  tool_calls.jsonl      every tool call (name, args, result, time)  - investigation audit trail
  snapshot.json         recorded tool results (replay offline with --replay)
  diagnosis.json        internal diagnosis (with per-evidence verified flags)
  output.json           OFFICIAL output in the organisers' JSON schema   <- scored
  action_plan.json      proposed allowlisted action + reason + rollback
  approval.json         human decision
  actions.jsonl         every Action API call / dry run / refusal
  verification.json     recovery check timeline
  incident_report.json  everything above in one file
  report.md             readable incident report
"""
import json
import shutil

from agent import actions, approval as approval_mod, config, memory, recovery, report, runbook, toolbox
from agent.investigate import investigate
from agent.schema import to_official, validate_official


def _w(path, obj):
    path.write_text(json.dumps(obj, indent=1, default=str), encoding="utf-8")


def run_incident(alert: dict, use_llm=True, mode="diagnose", approve_mode="cli", replay=None,
                 chat=None, verify_fn=None, log=print) -> dict:
    """mode: diagnose (stop after proposing) | dry-run (log the action, change nothing) | act (full loop)."""
    d_dir = config.RUNS / alert["incident_id"]
    d_dir.mkdir(parents=True, exist_ok=True)
    _w(d_dir / "alert.json", alert)
    log(f"[{alert['incident_id']}] investigating: {'; '.join(alert.get('reasons', []))[:200]}")

    session = toolbox.Session(d_dir, replay=replay)
    res = investigate(session, alert, use_llm=use_llm, chat=chat, log=log)
    diag, meta = res["diagnosis"], res["meta"]
    _w(d_dir / "diagnosis.json", diag)
    _w(d_dir / "meta.json", meta)
    _w(d_dir / "snapshot.json", session.snapshot())

    plan = runbook.propose(diag)
    _w(d_dir / "action_plan.json", plan)
    appr = act_res = verification = rollback = None

    if plan["action"] == "escalate":
        outcome = "no_incident" if diag["status"] == "no_incident" else "escalated"
        log(approval_mod.summary_text(diag, plan))
    elif mode == "diagnose":
        outcome = "proposed"
        log(approval_mod.summary_text(diag, plan))
    elif mode == "dry-run":
        log(approval_mod.summary_text(diag, plan))
        act_res = actions.execute(plan["action"], plan["params"], dry_run=True, incident_dir=d_dir)
        log(f"DRY RUN - would send: {json.dumps(act_res['would_send'])}")
        outcome = "dry_run"
    elif actions.kill_engaged():
        log(approval_mod.summary_text(diag, plan))
        log("KILL SWITCH ENGAGED - not asking for approval, nothing will be executed.")
        outcome = "killed"
    else:
        appr = approval_mod.ask(diag, plan, approve_mode)
        _w(d_dir / "approval.json", appr)
        if appr["decision"] != "approved":
            outcome = "rejected"
            log("Rejected - nothing changed. Escalating with findings.")
        else:
            watch = sorted(set(alert.get("services", [])) | {plan["target_service"]})
            # health BEFORE acting (during the incident), for the before/after comparison in the report
            before = (session.call("get_service_health") or {}).get("services", {})
            try:
                act_res = actions.execute(plan["action"], plan["params"], approval=appr, incident_dir=d_dir)
            except actions.KillSwitchEngaged:
                act_res, outcome = {"result": "refused", "why": "kill switch"}, "killed"
            else:
                if act_res["result"] != "ok":
                    outcome = "action_failed"
                    log(f"Action failed: {act_res}")
                else:
                    log(f"Executed {plan['action']} - verifying recovery (up to {config.VERIFY_SECONDS}s)")
                    ft = diag["root_cause"].get("fault_type")
                    vf = verify_fn or (lambda w, before=None, log=log: recovery.verify(w, before=before, log=log,
                                                                                      fault_type=ft))
                    verification = vf(watch, before={s: before.get(s) for s in watch}, log=log)
                    _w(d_dir / "verification.json", verification)
                    if verification["recovered"]:
                        outcome = "resolved"
                    else:
                        outcome = "not_recovered"
                        rb = plan.get("rollback")
                        if rb:
                            log(f"Not recovered -> rollback {rb}")
                            rb_appr = approval_mod.ask(diag, {**rb, "reason": "ROLLBACK: previous action did not help"},
                                                       approve_mode)
                            try:
                                rollback = actions.execute(rb["action"], rb["params"], approval=rb_appr,
                                                           incident_dir=d_dir)
                            except actions.KillSwitchEngaged:
                                rollback = {"result": "refused", "why": "kill switch"}
                        log("Not recovered -> escalating to a human with findings.")

    extra = {"proposed_action": {k: plan.get(k) for k in ("action", "params", "reason")},
             "action_taken": (act_res or {}).get("result") if act_res else None,
             "recovery_verified": verification["recovered"] if verification else None,
             "outcome": outcome}
    official = to_official(diag, extra)
    problems = validate_official(official)
    if problems:
        log("!! official output does not match config/output_schema.json:\n   " + "\n   ".join(problems[:10]))
    _w(d_dir / "output.json", official)
    rep = report.build(alert, diag, meta, plan, appr, act_res, verification, rollback, outcome, official)
    rep["schema_problems"] = problems
    _w(d_dir / "incident_report.json", rep)
    (d_dir / "report.md").write_text(report.markdown(rep, session.calls), encoding="utf-8")
    memory.remember(rep)
    latest = config.RUNS / "latest"
    shutil.rmtree(latest, ignore_errors=True)
    shutil.copytree(d_dir, latest)
    log(f"[{alert['incident_id']}] outcome={outcome}  ->  {d_dir}/report.md")
    return rep
