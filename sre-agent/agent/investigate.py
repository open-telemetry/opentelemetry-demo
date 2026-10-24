"""BRAIN: investigate an alert with tools, then produce a checked, calibrated diagnosis.

  LLM path      : tool-calling loop. The model chooses the next tool from what it has found so far
                  (no "paste everything into one prompt"), then calls submit_diagnosis.
  Fallback path : deterministic investigator (rules.py + targeted drill-down) - used with --no-llm,
                  or when the LLM fails / returns invalid output 3 times.
  Finalise      : schema validation -> evidence check -> confidence calibration against the rules
                  (a second, independent "reviewer") -> escalate if not confident.
"""
import json
import time

from pydantic import ValidationError

from agent import config, evidence_check, llm, rules, toolbox
from agent.schema import FAULT_TYPES, Diagnosis

SYSTEM = f"""You are the on-call Site Reliability Engineer for the OpenTelemetry Astronomy Shop, a microservice
e-commerce app (frontend-proxy -> frontend -> cart/checkout/product-catalog/recommendation/ad/currency/shipping;
checkout -> payment/email/cart/currency/shipping/product-catalog/kafka; kafka -> accounting/fraud-detection;
cart -> valkey-cart; product-catalog -> astronomy-db; shipping -> quote).

An alert fired. Investigate with the tools, ONE step at a time, choosing each next tool based on what you
found so far. A good order: get_service_health -> get_error_origins / get_slow_operations -> drill into the
suspect (get_service_detail, search_logs, get_container_health, get_trace on an example trace id,
get_dependencies) -> check the suspect's own downstream dependencies before blaming it.

Reasoning rules:
- Errors and latency PROPAGATE UPSTREAM. The root cause is the most DOWNSTREAM component with its OWN
  evidence (error span with no failing child, its own error logs, container stopped/restarting/OOM, CPU or
  memory far above baseline, a dependency it cannot reach). Upstream services are affected_services.
- If a caller's span fails with "unavailable / connection refused / timeout" when calling X, suspect X
  (check X's container state).
- Infrastructure faults exist: stopped or crash-looping containers, cache/database down, network latency or
  packet loss between two services, CPU/memory starvation. Combinations are possible: if two independent
  causes exist, report the dominant one and name the other in alternative_hypotheses.
- Evidence MUST come from tool results. For each evidence item put the exact trace ID, log line or metric
  value in `reference`, copied verbatim, and the tool call number in `tool_call`. Invented evidence is
  detected automatically and penalised.
- Be honest: if evidence is weak or conflicting, give low confidence (<0.5) and fault_type "unknown" if
  needed. Escalating to a human with findings is BETTER than a confident wrong answer.
- You have a budget of about {config.MAX_TOOL_CALLS} tool calls. Finish by calling submit_diagnosis.
fault_type must be one of: {", ".join(FAULT_TYPES)}."""

SUBMIT = {"type": "function", "function": {
    "name": "submit_diagnosis",
    "description": "Submit the final diagnosis (call exactly once, at the end).",
    "parameters": {"type": "object", "required": ["root_cause", "confidence", "evidence", "reasoning"],
                   "properties": {
                       "root_cause": {"type": "object", "required": ["service", "fault_type", "summary"],
                                      "properties": {
                                          "service": {"type": "string"},
                                          "component": {"type": "string",
                                                        "description": "operation / endpoint / 'a -> b' link"},
                                          "fault_type": {"type": "string", "enum": FAULT_TYPES},
                                          "summary": {"type": "string"}}},
                       "confidence": {"type": "number", "description": "0..1"},
                       "evidence": {"type": "array", "items": {
                           "type": "object", "required": ["source", "signal", "reference"],
                           "properties": {
                               "source": {"type": "string", "enum": ["metrics", "traces", "logs", "runtime"]},
                               "signal": {"type": "string"},
                               "reference": {"type": "string"},
                               "supports": {"type": "string"},
                               "tool_call": {"type": "integer"}}}},
                       "affected_services": {"type": "array", "items": {"type": "string"}},
                       "alternative_hypotheses": {"type": "array", "items": {"type": "string"}},
                       "reasoning": {"type": "string", "description": "2-4 sentences: how the evidence connects"}}}}}


def _alert_text(alert: dict) -> str:
    return (f"ALERT {alert.get('alert_id', '')} fired at {alert.get('fired_at', '')}: "
            f"{'; '.join(alert.get('reasons', [])) or 'manual investigation requested'}. "
            f"Symptomatic services: {', '.join(alert.get('services', [])) or 'unknown'}. Investigate.")


# --------------------------------------------------------------------------- LLM path
def llm_investigate(session, alert: dict, chat=None, log=print) -> dict:
    chat = chat or llm.chat
    tools = toolbox.llm_specs([SUBMIT])
    msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": _alert_text(alert)}]
    bad_submits, steps = 0, 0
    while steps < config.MAX_TOOL_CALLS + 4:
        steps += 1
        if steps == config.MAX_TOOL_CALLS:
            msgs.append({"role": "user", "content": "Tool budget reached. Call submit_diagnosis now."})
        m = chat(msgs, tools=tools)
        calls = m.get("tool_calls") or []
        msgs.append({"role": "assistant", "content": m.get("content") or "", **({"tool_calls": calls} if calls else {})})
        if not calls:
            # model answered in text; try to read a diagnosis from it, else nudge it
            try:
                sub = llm.parse_json(m.get("content") or "")
                if "root_cause" in sub:
                    return sub
            except Exception:
                pass
            msgs.append({"role": "user", "content": "Use the tools, then call submit_diagnosis."})
            continue
        for tc in calls:
            name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            if name == "submit_diagnosis":
                problem = _submission_problem(args)
                if not problem:
                    return args
                bad_submits += 1
                if bad_submits > 2:
                    raise ValueError(f"LLM submission invalid 3x: {problem}")
                content = f"INVALID submission: {problem}. Fix and call submit_diagnosis again."
            else:
                log(f"  tool #{len(session.calls) + 1}: {name}({json.dumps(args)})")
                res = session.call(name, args)
                content = f"[tool_call {len(session.calls)}] " + toolbox.short(res)
            msgs.append({"role": "tool", "tool_call_id": tc.get("id", name), "name": name, "content": content})
    raise TimeoutError("LLM did not submit a diagnosis within the step budget")


def _submission_problem(sub: dict):
    try:
        Diagnosis.model_validate({"incident_id": "x", "detected_at": "x", **sub})
        return None
    except ValidationError as e:
        return str(e)[:600]


# --------------------------------------------------------------------------- deterministic path
def rule_investigate(session, ranked: list) -> dict:
    """Targeted drill-down on the top suspect, then a diagnosis built only from what was observed."""
    if not ranked:
        return {"root_cause": {"service": "unknown", "fault_type": "unknown",
                               "summary": "No service shows its own failure evidence."},
                "confidence": 0.1, "reasoning": "No ranked candidates.",
                "evidence": [{"source": "metrics", "signal": "no anomalies over baseline",
                              "reference": "anomalies: []"}]}
    top = ranked[0]
    s = top["service"]
    session.call("get_dependencies", {"service": s})
    cont = session.call("get_container_health", {"service": s})
    detail = session.call("get_service_detail", {"service": s})
    logs = session.call("search_logs", {"service": s})
    ev = []
    for sig in top["signals"]:
        if sig["source"] == "note":
            continue
        ref = None
        if "traces=" in sig["signal"]:
            ref = sig["signal"].split("traces=")[-1].split(",")[0].split(" ")[0]
        ev.append({"source": sig["source"], "signal": sig["signal"][:300], "reference": ref,
                   "supports": f"direct signal at {s}"})
    if ev and any(e["reference"] for e in ev):
        tid = next(e["reference"] for e in ev if e["reference"])
        tr = session.call("get_trace", {"trace_id": tid})
        err_lines = [l for l in tr.get("tree", []) if "ERROR" in l] if isinstance(tr, dict) else []
        if err_lines:
            deepest = max(err_lines, key=lambda l: len(l) - len(l.lstrip()))
            ev.append({"source": "traces", "signal": f"trace {tid} deepest failing span: {deepest.strip()[:200]}",
                       "reference": tid, "supports": "deepest failing span in an example trace"})
    for line in (logs.get("lines", []) if isinstance(logs, dict) else [])[:2]:
        ev.append({"source": "logs", "signal": f"{s} log: {line['body'][:200]}", "reference": line["body"][:120],
                   "supports": "service's own error log"})
    if isinstance(cont, dict) and cont.get("status") and cont.get("status") != "running":
        ev.append({"source": "runtime", "signal": f"{s} container status {cont['status']} exit {cont.get('exit_code')}",
                   "reference": f"\"status\": \"{cont['status']}\"",
                   "supports": "service is not running"})
    ops = detail.get("operations", []) if isinstance(detail, dict) else []
    if ops and ops[0]["error_rate"] > 0:
        ev.append({"source": "metrics", "signal": f"{s} op {ops[0]['operation']} error rate {ops[0]['error_rate']}",
                   "reference": str(ops[0]["error_rate"]), "supports": "failing operation of the suspect"})
    comp = top.get("component")
    return {"root_cause": {"service": s, "component": comp, "fault_type": top["fault_type_guess"],
                           "summary": f"{s}{' (' + comp + ')' if comp else ''}: {top['fault_type_guess']} - "
                                      f"evidence from {', '.join(top['evidence_sources'])}."},
            "confidence": top["evidence_confidence"],
            "evidence": ev[:7] or [{"source": "metrics", "signal": "weak signal", "reference": None}],
            "affected_services": [r["service"] for r in ranked[1:4]],
            "alternative_hypotheses": [f"{r['service']} ({r['fault_type_guess']}, score {r['score']})"
                                       for r in ranked[1:3]],
            "reasoning": f"Deterministic ranking: {s} scored {top['score']} from "
                         f"{', '.join(top['evidence_sources'])}; upstream services discounted as victims."}


# --------------------------------------------------------------------------- finalise
def finalise(sub: dict, ranked: list, quiet: bool, session, incident_id: str, detected_at: str,
             used_llm: bool) -> dict:
    d = Diagnosis.model_validate({"incident_id": incident_id, "detected_at": detected_at, **sub}).model_dump()
    chk = evidence_check.check(d, session.corpus())
    svc = d["root_cause"]["service"]
    match = next((r for r in ranked if r["service"] == svc), None)
    rule_conf = match["evidence_confidence"] if match else 0.25
    agrees = bool(ranked) and ranked[0]["service"] == svc
    conf = 0.5 * d["confidence"] + 0.5 * rule_conf if used_llm else rule_conf
    if used_llm and ranked and not agrees:
        conf *= 0.8
    conf -= 0.1 * chk["unverified"]
    d["confidence"] = round(max(0.05, min(0.95, conf)), 2)
    review = {"rules_top": ranked[0]["service"] if ranked else None, "agrees_with_rules": agrees,
              "evidence_verified": chk["verified"], "evidence_unverified": chk["unverified"]}
    if quiet:
        d["alternative_hypotheses"] = [f"weak signal only: {svc} ({d['root_cause']['fault_type']})"] + d["alternative_hypotheses"]
        d["root_cause"] = {"service": "none", "component": None, "fault_type": "unknown",
                           "summary": "No incident confirmed: telemetry is within baseline."}
        d["status"] = "no_incident"
        d["escalation_reason"] = "No clear incident: no metric anomaly, no error origin, no runtime event."
        d["confidence"] = min(d["confidence"], 0.3)
    elif chk["verified"] == 0:
        d["status"] = "escalated"
        d["escalation_reason"] = "None of the cited evidence could be found in the telemetry."
    elif d["confidence"] < config.CONFIDENCE_TO_ACT or d["root_cause"]["fault_type"] == "unknown":
        d["status"] = "escalated"
        d["escalation_reason"] = (f"Confidence {d['confidence']} below action threshold {config.CONFIDENCE_TO_ACT}"
                                  + ("" if agrees or not ranked else f"; rule-based reviewer suspects {ranked[0]['service']}"))
    return {"diagnosis": d, "review": review}


def investigate(session, alert: dict, use_llm: bool = True, chat=None, log=print) -> dict:
    t0 = time.time()
    incident_id = alert["incident_id"]
    detected_at = alert.get("fired_at") or time.strftime("%Y-%m-%dT%H:%M:%S%z")
    meta = {"llm_used": False, "llm_errors": []}
    sub = None
    if use_llm and (chat or llm.available()):
        try:
            sub = llm_investigate(session, alert, chat=chat, log=log)
            meta["llm_used"] = True
        except Exception as e:
            meta["llm_errors"].append(f"{type(e).__name__}: {str(e)[:300]}")
            log(f"  LLM path failed ({type(e).__name__}: {str(e)[:300]}) -> deterministic fallback")
    bundle = rules.build_bundle(session)            # cached if the LLM already called these tools
    ranked = rules.rank(bundle)
    quiet = rules.is_quiet(bundle)
    if sub is None:
        sub = rule_investigate(session, ranked)
    try:
        out = finalise(sub, ranked, quiet, session, incident_id, detected_at, meta["llm_used"])
    except ValidationError as e:   # should not happen (validated in loop) - be safe anyway
        meta["llm_errors"].append(f"final validation: {str(e)[:300]}")
        out = finalise(rule_investigate(session, ranked), ranked, quiet, session, incident_id, detected_at, False)
        meta["llm_used"] = False
    meta.update(ranking=ranked, review=out["review"], tool_calls=len(session.calls),
                seconds=round(time.time() - t0, 1))
    return {"diagnosis": out["diagnosis"], "meta": meta}
