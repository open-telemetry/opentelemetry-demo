"""Build, validate, repair and write incident reports (F16).

Every run ends with a schema-valid JSON report and a markdown copy, even when
the investigation or diagnosis failed. Evidence text is copied verbatim from
the run log, never re-generated.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

import jsonschema

from oncall.agent.runlog import RunLog
from oncall.models import Alert, Diagnosis
from oncall.report.adapter import to_official

SCHEMA_PATH = Path(__file__).with_name("schema.json")
AGENT_VERSION = "oncall-0.2"
MAX_EVENT_CHARS = 200
EVIDENCE_SOURCES = {
    "metric": "get_metrics",
    "log": "search_logs",
    "trace": "search_traces",
    "container": "container_health",
    "deploy": "deploy_history",
}
PREVENTION = {
    "app_error": "Add a regression test and an error-rate alert for the failing operation.",
    "dependency_unavailable": "Add a healthcheck, restart policy and a fallback for the dependency.",
    "container_down": "Set a restart policy and alert on container state changes.",
    "resource_cpu": "Right-size the CPU limit and alert on throttling.",
    "resource_memory": "Right-size the memory limit and alert on usage near it.",
    "network_degradation": "Add timeouts, retries with backoff and latency alerts between the services.",
    "traffic_surge": "Add rate limiting and autoscaling at the entry point.",
    "upstream_propagation": "Find and fix the failing downstream dependency.",
    "unknown": "Escalated to a human; add the telemetry that was missing.",
    "no_incident": "None needed: no service regressed.",
}
BASE_LIMITATIONS = [
    "Diagnosis comes from telemetry only (metrics, traces, logs, container state).",
    "No action is executed without human approval through the Action API.",
]
ALERT_DEFAULTS = {
    "id": "unknown-alert",
    "ts": "",
    "service": None,
    "signal": "manual",
    "description": "",
    "source": "manual",
}


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _timeline(run: RunLog) -> list[dict]:
    events = []
    for e in run.events():
        kind = e.get("event")
        if kind == "alert":
            text = "alert received"
        elif kind == "tool_call":
            text = f"tool {e.get('name')}({json.dumps(e.get('args') or {})})"
        elif kind == "tool_result":
            result = e.get("result") or {}
            status = "ok" if result.get("ok") else f"error: {result.get('error')}"
            text = f"result {e.get('name')}: {status}"
        elif kind == "finish":
            text = f"investigation stopped ({e.get('stopped')}) after {e.get('steps')} steps"
        elif kind == "decision":
            d = e.get("diagnosis") or {}
            stage = e.get("stage") or "diagnosed"
            text = (
                f"{stage}: {d.get('decision')} {d.get('category')} {d.get('component')}"
            )
        elif kind == "error":
            text = f"error in {e.get('where')}: {e.get('error') or e.get('problems')}"
        else:
            continue
        events.append({"ts": e.get("ts"), "event": text[:MAX_EVENT_CHARS]})
    return events


def _problems(run: RunLog) -> list[str]:
    return [
        str(p)
        for e in run.events("decision")
        if e.get("stage") == "validated"
        for p in e.get("problems") or []
    ]


def build_report(
    alert: Alert,
    diagnosis: Diagnosis,
    run: RunLog,
    actions: list | None = None,
    verification: dict | None = None,
) -> dict:
    """The internal report; evidence text copied verbatim from the run log."""
    index = run.evidence_index()
    evidence = [
        {
            "id": eid,
            "source": EVIDENCE_SOURCES.get(eid.split(":", 1)[0], "unknown"),
            "text": index[eid].get("text") or "",
            "ts": index[eid].get("ts"),
        }
        for eid in diagnosis["evidence_ids"]
        if eid in index
    ]
    return {
        "incident_id": run.run_id,
        "detected_at": alert.get("ts") or _now(),
        "alert": {
            **ALERT_DEFAULTS,
            **{k: v for k, v in alert.items() if v is not None or k == "service"},
        },
        "root_cause": {
            "component": diagnosis["component"],
            "category": diagnosis["category"],
            "description": diagnosis["cause"],
        },
        "confidence": diagnosis["confidence"],
        "decision": diagnosis["decision"],
        "reasoning": diagnosis["reasoning"],
        "evidence": evidence,
        "affected_services": diagnosis["affected_services"],
        "alternatives": diagnosis["alternatives"],
        "timeline": _timeline(run),
        "actions": list(actions or []),
        "verification": dict(verification or {}),
        "prevention": PREVENTION.get(diagnosis["category"], PREVENTION["unknown"]),
        "limitations": BASE_LIMITATIONS + _problems(run),
        "agent_version": AGENT_VERSION,
        "llm_models": llm_models(run),
    }


def llm_models(run: RunLog) -> list[str]:
    """The LLM endpoints that served the run, in first-use order."""
    return list(
        dict.fromkeys(e["model"] for e in run.events("llm_call") if e.get("model"))
    )


def validate(report: dict, schema_path: str | Path = SCHEMA_PATH) -> list[str]:
    """Schema problems, one line each; empty when valid."""
    schema = json.loads(Path(schema_path).read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [
        f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}"
        for e in validator.iter_errors(report)
    ]


def repair(report: dict) -> dict:
    """One deterministic repair: drop unknown fields, fill required ones, coerce types."""
    schema = _schema()
    props = schema["properties"]
    fixed = {k: v for k, v in report.items() if k in props}
    defaults = {
        "incident_id": "unknown-run",
        "detected_at": _now(),
        "alert": dict(ALERT_DEFAULTS),
        "root_cause": {"component": None, "category": "unknown", "description": ""},
        "confidence": 0.0,
        "decision": "escalate",
        "evidence": [],
        "affected_services": [],
        "alternatives": [],
        "timeline": [],
        "actions": [],
        "verification": {},
        "prevention": PREVENTION["unknown"],
        "limitations": list(BASE_LIMITATIONS),
        "agent_version": AGENT_VERSION,
    }
    for key, value in defaults.items():
        if not isinstance(fixed.get(key), type(value)) and not (
            key == "confidence" and isinstance(fixed.get(key), (int, float))
        ):
            fixed[key] = value
    try:
        fixed["confidence"] = min(max(float(fixed["confidence"]), 0.0), 1.0)
    except (TypeError, ValueError):
        fixed["confidence"] = 0.0
    if fixed["decision"] not in props["decision"]["enum"]:
        fixed["decision"] = "escalate"
    rc = {**defaults["root_cause"], **fixed["root_cause"]}
    if rc["category"] not in props["root_cause"]["properties"]["category"]["enum"]:
        rc["category"] = "unknown"
    fixed["root_cause"] = {k: rc[k] for k in ("component", "category", "description")}
    fixed["alert"] = {
        k: v
        for k, v in {**ALERT_DEFAULTS, **fixed["alert"]}.items()
        if k in props["alert"]["properties"]
    }
    for key in ("affected_services", "limitations"):
        fixed[key] = [str(v) for v in fixed[key]]
    fixed["evidence"] = [
        {
            "id": str(e.get("id") or "unknown"),
            "source": str(e.get("source") or "unknown"),
            "text": str(e.get("text") or ""),
            "ts": e.get("ts") if isinstance(e.get("ts"), str) else None,
        }
        for e in fixed["evidence"]
        if isinstance(e, dict)
    ]
    return fixed


def fallback_report(alert: Alert, run: RunLog, error: str) -> dict:
    """A minimal valid escalate report for when anything else fails."""
    return {
        "incident_id": run.run_id,
        "detected_at": (alert or {}).get("ts") or _now(),
        "alert": {
            k: v
            for k, v in {**ALERT_DEFAULTS, **(alert or {})}.items()
            if k in _schema()["properties"]["alert"]["properties"]
        },
        "root_cause": {
            "component": None,
            "category": "unknown",
            "description": "Report could not be built; escalated to a human.",
        },
        "confidence": 0.0,
        "decision": "escalate",
        "reasoning": "",
        "evidence": [],
        "affected_services": [],
        "alternatives": [],
        "timeline": [],
        "actions": [],
        "verification": {},
        "prevention": PREVENTION["unknown"],
        "limitations": [*BASE_LIMITATIONS, f"report fallback: {error}"[:300]],
        "agent_version": AGENT_VERSION,
    }


def finalise_report(
    alert: Alert, diagnosis: Diagnosis | None, run: RunLog, **kwargs
) -> tuple[dict, list[str]]:
    """build -> validate -> one repair -> fallback. Returns (valid report, notes)."""
    notes: list[str] = []
    try:
        report = to_official(build_report(alert, diagnosis, run, **kwargs))
    except Exception as exc:  # noqa: BLE001
        notes.append(f"build failed: {type(exc).__name__}: {exc}")
        report = fallback_report(alert, run, notes[-1])
    problems = validate(report)
    if problems:
        notes.append(f"invalid, repaired: {problems[:3]}")
        report = repair(report)
        problems = validate(report)
    if problems:
        notes.append(f"still invalid, fallback: {problems[:3]}")
        report = fallback_report(alert, run, "; ".join(problems[:3]))
    return report, notes


def to_markdown(report: dict) -> str:
    rc = report["root_cause"]
    lines = [
        f"# Incident {report['incident_id']}",
        "",
        f"- Detected: {report['detected_at']}",
        (
            f"- Alert: {report['alert']['description']} "
            f"(service={report['alert']['service']}, signal={report['alert']['signal']})"
        ),
        f"- Decision: **{report['decision']}**, confidence {report['confidence']:.2f}",
        f"- Root cause: {rc['component'] or 'none identified'} ({rc['category']})",
        "",
        "## Cause",
        rc["description"] or "-",
        "",
        "## Reasoning",
        report.get("reasoning") or "-",
        "",
        "## Evidence",
        *(f"- `{e['id']}` ({e['source']}): {e['text']}" for e in report["evidence"]),
        *([] if report["evidence"] else ["- none"]),
        "",
        "## Affected services",
        ", ".join(report["affected_services"]) or "-",
        "",
        "## Alternatives considered",
        *(
            f"- {a['hypothesis']}: rejected because {a['rejected_because']}"
            for a in report["alternatives"]
        ),
        *([] if report["alternatives"] else ["- none"]),
        "",
        "## Timeline",
        *(f"- {t['ts']}: {t['event']}" for t in report["timeline"]),
        "",
        "## Prevention",
        report["prevention"],
        "",
        "## Limitations",
        *(f"- {item}" for item in report["limitations"]),
        "",
        (
            f"_agent {report['agent_version']}; LLM: "
            f"{', '.join(report.get('llm_models') or []) or 'none'}_"
        ),
        "",
    ]
    return "\n".join(lines)


def write(report: dict, out_dir: str | Path = "reports") -> tuple[Path, Path]:
    """reports/<incident_id>.json (must be valid) + reports/<incident_id>.md."""
    problems = validate(report)
    if problems:
        raise ValueError(f"refusing to write an invalid report: {problems[:3]}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / f"{report['incident_id']}.json"
    md_path = out / f"{report['incident_id']}.md"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    md_path.write_text(to_markdown(report), encoding="utf-8")
    return json_path, md_path


def report_run(
    alert: Alert,
    diagnosis: Diagnosis | None,
    run: RunLog,
    out_dir: str | Path = "reports",
) -> tuple[Path, Path]:
    """Finalise and write the run's report; record where it went in the run log."""
    report, notes = finalise_report(alert, diagnosis, run)
    json_path, md_path = write(report, out_dir)
    run.log(
        "decision",
        stage="report",
        json_path=str(json_path),
        md_path=str(md_path),
        notes=notes,
    )
    return json_path, md_path
