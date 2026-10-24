"""Acceptance orchestration using the unchanged F01 detector and F03 investigator."""
from datetime import timedelta
import json
from pathlib import Path
import time
from xml.sax.saxutils import escape

from incident_tools.eyes.core import Detector, Investigator
from incident_tools.eyes.runtime import export
from incident_tools.f02.boundary import iso, utc_now, timestamp
from .practice import write_json

DEPENDENCY_RULE = '''
For every tool choice after receiving observations, also return based_on_evidence_ids:
a nonempty list of specific evidence IDs whose observations justify this next query.
Explain that connection in rationale. Choose at least two distinct useful read queries,
then finish with evidence-backed symptom interpretations. Missing observations are gaps;
never invent a dependency or evidence. Do not request practice controls or injection records.
'''


class EvidenceModel:
    def __init__(self, router):
        self.router = router
        self.public_configuration = router.public_configuration

    def decide(self, messages, remaining):
        known = set()
        for message in messages[2:]:
            if message["role"] == "user":
                item = json.loads(message["content"])
                if item.get("observations") and item.get("status") in ("ok", "partial"):
                    known.add(item["evidence_id"])
        extended = [dict(message) for message in messages]
        extended[0]["content"] += DEPENDENCY_RULE
        choice, identity = self.router.decide(extended, remaining)
        if choice.get("action") == "tool":
            references = choice.get("based_on_evidence_ids", [])
            if not isinstance(references, list) or not all(isinstance(x, str) for x in references):
                raise ValueError("Invalid evidence dependency")
            if not set(references) <= known or (known and not references):
                raise ValueError("Subsequent tool choice must cite observed evidence")
        identity = dict(identity)
        slot = identity.get("slot")
        cfg = getattr(self.router, "cfg", {}).get(slot, {})
        endpoint = cfg.get("endpoint", "")
        if endpoint.startswith("https://api.openai.com/"):
            identity["provider"] = "OpenAI"
        elif cfg.get("backend") == "ollama":
            identity["provider"] = "Ollama"
        else:
            identity["provider"] = "operator-configured compatible provider"
        return choice, identity


def assess(run, incidents, polls, reset_record, origin):
    evidence = run.get("evidence", []) if run else []
    known, dependent, successful = set(), 0, 0
    tool_decisions = [d for d in (run or {}).get("decisions", []) if d["decision"].get("action") == "tool"]
    for decision, item in zip(tool_decisions, evidence):
        refs = decision["decision"].get("based_on_evidence_ids", [])
        if item.get("observations") and item.get("status") in ("ok", "partial"):
            successful += 1
            if refs and set(refs) <= known and decision["decision"].get("rationale", "").strip():
                dependent += 1
            known.add(item["evidence_id"])
    claims = (run or {}).get("interpretations", [])
    identities = [d["model"] for d in (run or {}).get("decisions", [])]
    dedup = [p for p in polls if p["phase"] == "dedup" and
             any(c["quality"] == "breach" for c in p["result"]["checks"])]
    alerts = incidents[0].get("alerts", []) if len(incidents) == 1 else []
    stored_ids = {p["result"]["created_incidents"][0] for p in polls if p["result"]["created_incidents"]}
    checks = {
        "one_automatic_incident": len(incidents) == 1 and stored_ids == {incidents[0]["id"]},
        "measured_alert_with_provenance": bool(alerts) and all(
            all(a.get(k) is not None for k in ("value", "threshold", "timestamp", "source_time",
                                              "query", "evidence_id", "freshness_evidence_id", "coverage_evidence_id"))
            and a["value"] > a["threshold"] for a in alerts),
        "repeated_breach_deduplicated": len(dedup) >= 2 and all(not p["result"]["created_incidents"] for p in dedup),
        "investigation_finished": bool(run) and run["stop_reason"] == "model_finished",
        "two_successful_queries_with_explicit_dependency": successful >= 2 and dependent >= 1,
        "interpretations_reference_observations": bool(claims) and all(
            c.get("evidence_ids") and set(c["evidence_ids"]) <= known for c in claims),
        "model_identity_recorded": bool(identities) and all(
            i.get("model") and i.get("slot") and i.get("backend") for i in identities),
        "practice_reset_verified": reset_record.get("status") == "reset_verified",
        "incident_detected_during_practice": len(incidents) == 1 and reset_record.get("paused_at") is not None
            and reset_record.get("reset_at") is not None and reset_record["paused_at"] <=
            timestamp(incidents[0]["detected_at"]).timestamp() <= reset_record["reset_at"],
        "real_backend_evidence": origin == "backend" and bool(run) and run.get("origin") == "backend"
            and all(e.get("origin") == "backend" for e in evidence),
    }
    return {"checks": checks, "automated_checks_passed": all(checks.values()),
            "live_acceptance_complete": False, "semantic_review": "pending",
            "note": "An operator must review whether cited observations support the tool choices and interpretations. Static fixtures never establish live acceptance."}


def sketch(run):
    providers = (run or {}).get("model_configuration", {}).get("providers", {})
    model = "; ".join(slot + ": " + cfg.get("model", "unconfigured") for slot, cfg in providers.items())
    rows = [
        "Existing demo + load generator -> OpenTelemetry Collector",
        "Collector -> Prometheus (metrics), OpenSearch (logs), Jaeger (traces)",
        "F02 constrained read tools: telemetry + Docker health/events + optional deployment audit",
        "F01 deterministic thresholds + freshness + SQLite incident deduplication",
        "One F03 investigator -> evidence-dependent read queries -> evidence store",
        "Configured inference: " + (model or "not called / unavailable"),
        "Model routing: " + (run or {}).get("model_configuration", {}).get("route", "not exercised"),
        "Outputs: incident report, execution log, model identity, evidence, acceptance checks",
        "Separate operator path: readiness -> shipping pause lease -> independent reset watchdog",
        "Operator controls and injection journal are never registered as agent tools",
        "Deployment history is unavailable unless an audit feed is configured; root cause unproven",
        "Proposed later: diagnosis ranking, approval-gated remediation, recovery verification",
    ]
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="840" viewBox="0 0 1200 840">',
           '<rect width="1200" height="840" fill="white"/>',
           '<text x="25" y="30" font-family="sans-serif" font-size="20">Eyes acceptance architecture - configuration and execution status are recorded in artifacts</text>']
    for index, row in enumerate(rows):
        y = 50 + index * 64
        svg.append(f'<rect x="20" y="{y}" width="1160" height="48" rx="6" fill="#eef6fc" stroke="#174466"/>')
        svg.append(f'<text x="32" y="{y+29}" font-family="sans-serif" font-size="14">{escape(row)}</text>')
        if index < 7:
            svg.append(f'<path d="M600 {y+48}v16" stroke="#174466"/>')
    svg.append("</svg>")
    return "\n".join(svg)


def execute(tools, settings, store, model, practice, output, duration=240,
            baseline_seconds=300, detect_only=False, clock=utc_now, sleep=time.sleep):
    output = Path(output)
    detector = Detector(tools, store, settings, clock=clock)
    polls, run, reset_record = [], None, {}
    failure = None
    started = False

    def poll(phase):
        entry = {"at": iso(clock()), "phase": phase, "result": detector.poll()}
        polls.append(entry)
        write_json(output / ("poll-%04d.json" % len(polls)), entry)
        return entry["result"]

    try:
        if store.incidents():
            raise ValueError("FRESH_INCIDENT_STORE_REQUIRED")
        until = clock() + timedelta(seconds=baseline_seconds)
        normals = 0
        while clock() <= until:
            result = poll("baseline")
            qualities = [c["quality"] for c in result["checks"]]
            if store.incidents() or "breach" in qualities:
                raise ValueError("BASELINE_ALREADY_BREACHING")
            if qualities and all(q == "normal" for q in qualities):
                normals += 1
            elif not qualities or any(q != "duplicate_source_sample" for q in qualities):
                normals = 0
            if normals >= 2:
                break
            sleep(settings["poll_seconds"])
        else:
            raise ValueError("BASELINE_NOT_ESTABLISHED")
        started = True
        practice.start()
        until = clock() + timedelta(seconds=duration - 10)
        incident = None
        while clock() < until:
            sleep(settings["poll_seconds"])
            result = poll("detection")
            if result["created_incidents"]:
                incident = store.incidents()[0]
                break
        if incident is None:
            raise ValueError("NO_SUSTAINED_BREACH_DETECTED")
        for _ in range(2):
            sleep(settings["poll_seconds"])
            poll("dedup")
        if len(store.incidents()) != 1:
            raise ValueError("EXPECTED_ONE_INCIDENT")
    except BaseException as exc:
        failure = str(exc) if isinstance(exc, ValueError) and str(exc).isupper() else type(exc).__name__
    finally:
        if started:
            try:
                reset_record = practice.reset()
            except Exception:
                failure = "RESET_NOT_VERIFIED"
                reset_record = {"status": "reset_failed"}
    if failure is None and not detect_only:
        try:
            run = Investigator(tools, store, EvidenceModel(model), settings).run(incident)
            export(run, output / "report")
            (output / "report" / "checkpoint1_architecture.svg").write_text(sketch(run), encoding="utf-8")
        except BaseException as exc:
            failure = type(exc).__name__
    summary = assess(run, store.incidents(), polls, reset_record, tools.config.origin)
    summary.update(origin=tools.config.origin, failure=failure, detect_only=detect_only,
                   incident_ids=[i["id"] for i in store.incidents()],
                   injection_attempted=started, injection_started=reset_record.get("paused_at") is not None, reset=reset_record,
                   live_incident_executed=tools.config.origin == "backend" and reset_record.get("paused_at") is not None and bool(store.incidents()),
                   real_llm_called=tools.config.origin == "backend" and run is not None,
                   baseline_poll_count=sum(p["phase"] == "baseline" for p in polls))
    if failure:
        summary["automated_checks_passed"] = False
    write_json(output / "acceptance.json", summary)
    lines = ["# Eyes acceptance", "", "Origin: " + tools.config.origin,
             "Automated checks passed: " + str(summary["automated_checks_passed"]),
             "Live acceptance complete: False; semantic review required.",
             "Failure: " + str(failure), ""]
    lines += ["- " + name + ": " + ("PASS" if passed else "NOT PASSED") for name, passed in summary["checks"].items()]
    lines += ["", "Review the report and execution log. Confirm the second useful query follows from its cited evidence and every interpretation is supported.",
              "The operator journal records injection/reset separately; it is not model input.",
              "Reset verification checks container running/unpaused state, not service recovery or F09."]
    (output / "acceptance.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary
