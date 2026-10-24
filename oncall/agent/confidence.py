"""Confidence and escalation rules (F15): deterministic caps on the LLM's estimate.

Signals come only from the run log's tool results, so every adjustment can be
explained in the report. Run after the evidence validator (F13).
"""

import re
from dataclasses import dataclass, field

from oncall.agent.evidence import service_of, tool_of
from oncall.agent.runlog import RunLog
from oncall.agent.taxonomy import CLIENT_SERVICES
from oncall.config import load_settings
from oncall.models import Diagnosis

MAX_REASONING_CHARS = 800
MAX_CONFIDENCE = 0.95
ERROR_RATE_FACTOR = 3.0
P95_FACTOR = 2.0
CPU_RISE_FACTOR = 1.5
MEM_RISE_POINTS = 10.0
NO_INCIDENT_CONFIDENCE = 0.85
# "Healthy" may only be claimed after these all-service checks.
FULL_TRIAGE = frozenset({"error_rate", "containers"})
TRIAGE_GAP_CAP = 0.4
# get_metrics evidence text: "<svc>[/<span>] <metric> <now> (baseline <b>, delta <d>)"
# or "... (baseline unavailable)".
METRIC_TEXT = re.compile(
    r"^(?P<key>\S+) (?P<metric>error_rate|latency_p95|rps|top_errors) "
    r"(?P<now>[\d.]+) \((?:baseline (?P<base>[\d.]+),|baseline unavailable)"
)
# container_health evidence usage: "cpu=12.5% of one core" / "mem=40.0% of limit".
USAGE = re.compile(r"(?P<kind>cpu|mem)=(?P<pct>[\d.]+)% of (?P<of>limit|one core)")
CONTAINER_FAULTS = ("not running", "restarted", "OOM-killed", "healthcheck unhealthy")


@dataclass
class Signals:
    """What the run log says about each service."""

    regressions: dict[str, list[str]] = field(default_factory=dict)
    no_baseline: dict[str, list[str]] = field(default_factory=dict)
    container_faults: dict[str, list[str]] = field(default_factory=dict)
    cpu_limit_hit: set[str] = field(default_factory=set)
    usage: dict[str, list[dict[str, float]]] = field(default_factory=dict)
    triage: set[str] = field(default_factory=set)
    trace_or_log: set[str] = field(default_factory=set)

    def unhealthy(self) -> set[str]:
        return {
            s
            for s in {*self.regressions, *self.container_faults}
            if s not in CLIENT_SERVICES
        }


def _metric_signal(text: str, signals: Signals, error_floor: float, p95_floor: float):
    m = METRIC_TEXT.match(text)
    if not m or m["metric"] not in ("error_rate", "latency_p95"):
        return
    service = m["key"].split("/", 1)[0]
    now = float(m["now"])
    if m["base"] is None:
        if now > 0:
            signals.no_baseline.setdefault(service, []).append(text)
        return
    base = float(m["base"])
    if m["metric"] == "error_rate":
        regressed = now >= error_floor and now >= ERROR_RATE_FACTOR * base
    else:
        regressed = base > 0 and now >= p95_floor and now >= P95_FACTOR * base
    if regressed:
        signals.regressions.setdefault(service, []).append(text)


def _container_signal(text: str, service: str, signals: Signals) -> None:
    problems = text.partition(" | FLAGGED: ")[2]
    faults = [f for f in CONTAINER_FAULTS if f in problems]
    if faults:
        signals.container_faults.setdefault(service, []).extend(faults)
    if "% of limit" in problems and "CPU" in problems:
        signals.cpu_limit_hit.add(service)
    sample = {u["kind"]: float(u["pct"]) for u in USAGE.finditer(text)}
    if sample:
        signals.usage.setdefault(service, []).append(sample)


def collect(run: RunLog) -> Signals:
    settings = load_settings()
    signals = Signals()
    for event in run.events("tool_result"):
        result = event.get("result") or {}
        if not result.get("ok"):
            continue
        query = result.get("query") or {}
        tool = result.get("tool") or event.get("name")
        if tool == "get_metrics" and not query.get("service"):
            signals.triage.add(query.get("metric", "error_rate"))
        if tool == "container_health" and not query.get("service"):
            signals.triage.add("containers")
        for ev in result.get("evidence") or []:
            service = service_of(ev)
            if not service:
                continue
            kind = tool_of(ev["id"])
            if kind == "metric":
                _metric_signal(
                    ev.get("text") or "",
                    signals,
                    settings.ALERT_ERROR_RATE,
                    settings.ALERT_P95_MS,
                )
            elif kind == "container":
                _container_signal(ev.get("text") or "", service, signals)
            elif kind in ("trace", "log"):
                signals.trace_or_log.add(service)
    return signals


def _usage_rose(samples: list[dict[str, float]], kind: str) -> bool:
    values = [s[kind] for s in samples if kind in s]
    if len(values) < 2:
        return False
    first, last = values[0], max(values[1:])
    if kind == "cpu":
        return first > 0 and last >= CPU_RISE_FACTOR * first
    return last - first >= MEM_RISE_POINTS


def _note(d: Diagnosis, notes: list[str]) -> None:
    if not notes:
        return
    tail = " [confidence: " + "; ".join(notes) + "]"
    room = max(MAX_REASONING_CHARS - len(tail), 0)
    d["reasoning"] = (d["reasoning"][:room] + tail)[:MAX_REASONING_CHARS]


def _no_incident(d: Diagnosis, signals: Signals, notes: list[str]) -> Diagnosis:
    confidence = NO_INCIDENT_CONFIDENCE
    if signals.no_baseline:
        confidence = min(confidence, 0.5)
        notes.append("some baselines unavailable: cap 0.5")
    if "latency_p95" not in signals.triage:
        confidence -= 0.15
        notes.append("triage did not check latency_p95: -0.15")
    notes.append("no regression in any service: no_incident / no_action")
    d.update(
        component=None,
        category="no_incident",
        decision="no_action",
        confidence=round(max(confidence, 0.0), 3),
    )
    if d["cause"] and "healthy" not in d["cause"].lower():
        d["cause"] = "No incident: no service regressed against its baseline."
    _note(d, notes)
    return d


def assess(d: Diagnosis, run: RunLog) -> Diagnosis:
    """Final confidence and decision for a (validated) diagnosis."""
    settings = load_settings()
    signals = collect(run)
    out: Diagnosis = {**d}
    notes: list[str] = []
    unhealthy = signals.unhealthy()

    full_triage = FULL_TRIAGE <= signals.triage
    if full_triage and not unhealthy:
        return _no_incident(out, signals, notes)
    if not unhealthy:
        missing = ", ".join(sorted(FULL_TRIAGE - signals.triage))
        notes.append(
            f"triage incomplete (no all-service {missing}): cannot claim healthy"
        )
        out.update(
            component=out["component"] if out["category"] != "no_incident" else None,
            category="unknown" if out["category"] == "no_incident" else out["category"],
        )
        out["confidence"] = min(float(out["confidence"]), TRIAGE_GAP_CAP)

    confidence = float(out["confidence"])

    def cap(value: float, why: str) -> None:
        nonlocal confidence
        if confidence > value:
            confidence = value
            notes.append(f"{why}: cap {value}")

    if out["category"] == "no_incident":
        out["category"] = "unknown"
        cap(
            0.3,
            f"claimed no incident but {', '.join(sorted(unhealthy)) or 'triage incomplete'}",
        )

    component = out["component"]
    index = run.evidence_index()
    cited = [index[i] for i in out["evidence_ids"] if i in index]
    own = [e for e in cited if service_of(e) == component]

    if (
        component in signals.container_faults
        and component in signals.trace_or_log
        and confidence < MAX_CONFIDENCE
    ):
        confidence = min(confidence + 0.1, MAX_CONFIDENCE)
        notes.append("container and trace/log signals agree: +0.1")
    if len({tool_of(e["id"]) for e in cited}) == 1:
        cap(0.55, "evidence from one tool only")
    if component and len(own) < 2:
        cap(0.5, f"fewer than 2 evidence items for {component}")
    faulted = {s for s in signals.container_faults if s not in CLIENT_SERVICES}
    if len(faulted) > 1:
        cap(0.5, f"more than one unhealthy container ({', '.join(sorted(faulted))})")
    if out["category"] in ("unknown", "upstream_propagation"):
        cap(0.3, f"category {out['category']}")
    if out["category"] in ("resource_cpu", "resource_memory") and component:
        kind = "cpu" if out["category"] == "resource_cpu" else "mem"
        limit_hit = (
            component in signals.cpu_limit_hit
            if kind == "cpu"
            else "OOM-killed" in signals.container_faults.get(component, [])
        )
        if not (limit_hit or _usage_rose(signals.usage.get(component, []), kind)):
            cap(0.3, f"no {kind} limit hit or rise for {component}")
    has_regression = bool(
        component
        and (component in signals.regressions or component in signals.container_faults)
    )
    if component and not has_regression:
        notes.append(f"no regression signal for {component}: act not allowed")
        if component in signals.no_baseline:
            cap(0.5, f"{component} evidence has no baseline")
        else:
            cap(settings.CONFIDENCE_MIN - 0.05, "no regression")
    if not out["alternatives"]:
        confidence -= 0.1
        notes.append("no alternatives falsified: -0.1")

    confidence = round(min(max(confidence, 0.0), MAX_CONFIDENCE), 3)
    if component is None or component in CLIENT_SERVICES:
        decision = "escalate"
        notes.append("no root-cause component: escalate")
    elif confidence >= settings.CONFIDENCE_MIN and has_regression:
        decision = "act"
    else:
        decision = "escalate"
    if decision != out["decision"]:
        notes.append(f"decision {out['decision']} -> {decision}")
    out.update(confidence=confidence, decision=decision)
    _note(out, notes)
    return out
