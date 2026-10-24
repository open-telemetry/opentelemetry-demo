"""Before/after telemetry snapshots and recovery verification for remediation actions.

Snapshots are built only from the agent's observability tools, so every number carries the
evidence ref the tool returned. Missing telemetry stays None and is labelled in ``missing``;
recovery is claimed only when fresh data shows it.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ..agent.tools import OK, ToolContext, container_health, get_service_metrics, system_overview
from ..agent.transcript import utc_now

RECOVERED = "RECOVERED"
NOT_RECOVERED = "NOT_RECOVERED"
NOT_VERIFIED_DRY_RUN = "NOT_VERIFIED_DRY_RUN"
NO_DATA = "NO_DATA"

ERROR_RATE_FLOOR = 0.01
ERROR_RATE_RECOVERY_FACTOR = 0.5
P95_REGRESSION_FACTOR = 1.2
LATENCY_IMPROVEMENT_FACTOR = 0.8
# Span metrics reach Prometheus about once a minute, so a 1m rate() window is usually empty.
MIN_RATE_WINDOW_MINUTES = 2
ANOMALY_FLAGS = ("error_rate_up", "latency_up", "container_not_running")
OVERVIEW = "system_overview"
OPERATIONS = "get_service_metrics"


@dataclass
class VerificationResult:
    status: str
    recovered: bool
    before: Dict[str, Any] = field(default_factory=dict)
    after: Dict[str, Any] = field(default_factory=dict)
    reasons: List[str] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    checked_at: str = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {"status": self.status, "recovered": self.recovered, "before": self.before,
                "after": self.after, "reasons": list(self.reasons), "evidence": list(self.evidence),
                "checked_at": self.checked_at}


def _call(tool: Callable[..., Dict[str, Any]], *args: Any, **kwargs: Any) -> Dict[str, Any]:
    try:
        return tool(*args, **kwargs)
    except Exception as e:  # a crashed tool is missing data, never a healthy reading
        return {"tool": tool.__name__, "status": "error", "summary": f"{type(e).__name__}: {str(e)[:200]}",
                "data": {}, "evidence": []}


def _operations_aggregate(ops: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Request-weighted error rate and worst p95 over the server/consumer operations returned."""
    served = [o for o in ops if o.get("kind") in ("server", "consumer") and o.get("rps") is not None]
    if not served:
        return None
    rps = sum(o["rps"] for o in served)
    err = sum((o.get("error_rate") or 0.0) * o["rps"] for o in served) / rps if rps > 0 else None
    p95s = [o["p95_ms"] for o in served if o.get("p95_ms") is not None]
    return {"rps": round(rps, 3), "error_rate": None if err is None else round(err, 4),
            "p95_ms": max(p95s) if p95s else None, "operations": len(served),
            "note": "derived from the server/consumer operations get_service_metrics returned; "
                    "p95_ms is the worst operation p95"}


def capture_baseline(ctx: ToolContext, service: str, window_minutes: int = 5) -> Dict[str, Any]:
    """Snapshot error rate, p95 latency, request rate and container state for one service."""
    window = min(60, max(MIN_RATE_WINDOW_MINUTES, int(window_minutes)))
    snap: Dict[str, Any] = {
        "service": service, "window_minutes": window, "captured_at": utc_now(),
        "error_rate": None, "p95_ms": None, "rps": None, "metric_source": None, "flags": None,
        "reference_p95_ms": None,
        "operations_aggregate": None, "container_state": None, "container_health": None,
        "restart_count": None, "tool_status": {}, "missing": {}, "evidence": [],
    }

    def keep(res: Dict[str, Any], prefix: str) -> None:
        snap["tool_status"][res.get("tool") or "?"] = res.get("status")
        snap["evidence"].extend(dict(e, tool=res.get("tool")) for e in res.get("evidence", []) or []
                                if str(e.get("ref", "")).startswith(prefix))

    overview = _call(system_overview, ctx, window_minutes=window)
    keep(overview, f"metric:{service}:")
    row = next((r for r in (overview.get("data") or {}).get("services", []) or []
                if r.get("service") == service), None) if overview.get("status") == OK else None
    if row is not None:
        snap["flags"] = list(row.get("flags") or [])
        if row.get("rps") is not None:
            snap.update(error_rate=row.get("error_rate"), p95_ms=row.get("p95_ms"), rps=row.get("rps"),
                        reference_p95_ms=row.get("baseline_p95_ms"), metric_source=OVERVIEW)

    ops = _call(get_service_metrics, ctx, service, window_minutes=window)
    keep(ops, f"metric:{service}:")
    if ops.get("status") == OK:
        snap["operations_aggregate"] = _operations_aggregate((ops.get("data") or {}).get("operations") or [])
    agg = snap["operations_aggregate"]
    if snap["metric_source"] is None and agg is not None:
        snap.update(error_rate=agg["error_rate"], p95_ms=agg["p95_ms"], rps=agg["rps"], metric_source=OPERATIONS)

    health = _call(container_health, ctx, service)
    keep(health, f"container:{service}:")
    containers = (health.get("data") or {}).get("containers") or [] if health.get("status") == OK else []
    c = next((x for x in containers if x.get("name") == service), None)
    if c is not None:
        snap.update(container_state=c.get("state"), container_health=c.get("health"),
                    restart_count=c.get("restart_count"))

    for key in ("error_rate", "p95_ms", "rps"):
        if snap[key] is None:
            snap["missing"][key] = (f"no {key} for '{service}' in the {window}m window "
                                    f"(system_overview: {overview.get('status')}, "
                                    f"get_service_metrics: {ops.get('status')})")
    if snap["container_state"] is None:
        snap["missing"]["container_state"] = (f"container_health: {health.get('status')}: "
                                              f"{health.get('summary', '')}"[:240])
    return snap


def _after_window(baseline: Dict[str, Any], settle_seconds: int) -> int:
    settle_minutes = math.ceil(max(0, settle_seconds) / 60)
    return min(int(baseline.get("window_minutes") or MIN_RATE_WINDOW_MINUTES),
               max(MIN_RATE_WINDOW_MINUTES, settle_minutes))


def _comparable(before: Dict[str, Any], after: Dict[str, Any]) -> Tuple[Optional[Dict], Optional[Dict], str]:
    """Pick metric values for before and after that come from the same tool."""
    keys = ("error_rate", "p95_ms", "rps", "reference_p95_ms")
    if before.get("metric_source") == OVERVIEW and after.get("metric_source") == OVERVIEW:
        return {k: before.get(k) for k in keys}, {k: after.get(k) for k in keys}, OVERVIEW
    if before.get("operations_aggregate") and after.get("operations_aggregate"):
        return before["operations_aggregate"], after["operations_aggregate"], OPERATIONS
    return None, None, ""


def _evaluate(before: Dict[str, Any], after: Dict[str, Any]) -> Tuple[str, List[str]]:
    service = after.get("service")
    failed: List[str] = []
    missing: List[str] = []
    passed: List[str] = []

    state, health = after.get("container_state"), after.get("container_health")
    if state is None:
        missing.append(f"container state for '{service}' unavailable after the action")
    elif state != "running":
        failed.append(f"container '{service}' is {state}, not running")
    elif health == "unhealthy":
        failed.append(f"container '{service}' health check reports unhealthy")
    else:
        passed.append(f"container '{service}' running (health: {health or 'n/a'})")
    if (before.get("restart_count") is not None and after.get("restart_count") is not None
            and after["restart_count"] > before["restart_count"]):
        passed.append(f"note: restart_count rose from {before['restart_count']} to {after['restart_count']}")

    b, a, source = _comparable(before, after)
    if b is None or a is None:
        missing.append(f"no comparable request metrics for '{service}' before and after the action")
    elif a.get("rps") is None or a["rps"] <= 0:
        missing.append(f"no requests to '{service}' after the action, so its error rate proves nothing")
    elif b.get("error_rate") is None or a.get("error_rate") is None:
        missing.append(f"error rate for '{service}' missing before or after the action")
    else:
        limit = max(ERROR_RATE_FLOOR, ERROR_RATE_RECOVERY_FACTOR * b["error_rate"])
        msg = f"error rate {b['error_rate']} -> {a['error_rate']} (must be < {round(limit, 4)}; source {source})"
        (passed if a["error_rate"] < limit else failed).append(msg)

        bp, ap = b.get("p95_ms"), a.get("p95_ms")
        if ap is None and bp is not None:
            missing.append(f"p95 latency for '{service}' missing after the action")
        elif ap is not None and bp is not None:
            ref = b.get("reference_p95_ms")
            if "latency_up" in (before.get("flags") or []):
                limit, rule = LATENCY_IMPROVEMENT_FACTOR * bp, "baseline was flagged latency_up, must improve"
            elif ref:
                limit = P95_REGRESSION_FACTOR * max(bp, ref)
                rule = f"no regression vs the action baseline or the pre-incident {ref}ms (30m earlier)"
            else:
                limit, rule = P95_REGRESSION_FACTOR * bp, "no regression vs the action baseline"
            msg = f"p95 {bp}ms -> {ap}ms (must be <= {round(limit, 1)}ms; {rule})"
            (passed if ap <= limit else failed).append(msg)
        else:
            passed.append("note: p95 latency unavailable before and after; latency not compared")

    still = [f for f in (after.get("flags") or []) if f in ANOMALY_FLAGS]
    if still:
        failed.append(f"system_overview still flags '{service}': {', '.join(still)}")

    if failed:
        return NOT_RECOVERED, failed + missing + passed
    if missing:
        return NO_DATA, missing + passed
    return RECOVERED, passed


def verify_recovery(ctx: ToolContext, action: Any, baseline: Dict[str, Any], settle_seconds: int,
                    dry_run: bool, sleep: Callable[[float], None] = time.sleep,
                    events: Any = None) -> VerificationResult:
    """Compare a fresh snapshot with the pre-action baseline after the settle time."""
    service = baseline.get("service") or getattr(action, "target_service", None)
    if dry_run:
        after = capture_baseline(ctx, service, int(baseline.get("window_minutes") or 5))
        result = VerificationResult(
            status=NOT_VERIFIED_DRY_RUN, recovered=False, before=baseline, after=after,
            reasons=["dry run: nothing changed, recovery not claimed",
                     "after snapshot is informational only (taken without a settle wait)"],
            evidence=_phase_evidence(baseline, after))
    else:
        if settle_seconds > 0:
            sleep(settle_seconds)
        window = _after_window(baseline, settle_seconds)
        after = capture_baseline(ctx, service, window)
        status, reasons = _evaluate(baseline, after)
        if window * 60 > settle_seconds:
            reasons.append(f"note: the {window}m after-window starts {window * 60 - settle_seconds}s before "
                           f"the action settled, so pre-action samples may be included")
        result = VerificationResult(status=status, recovered=status == RECOVERED, before=baseline, after=after,
                                    reasons=reasons, evidence=_phase_evidence(baseline, after))
    if events is not None:
        events.emit("VERIFICATION", verification_summary(result), verification_event_data(result))
    return result


def _event_snapshot(snap: Dict[str, Any]) -> Dict[str, Any]:
    return {"error_rate": snap.get("error_rate"), "p95_ms": snap.get("p95_ms"), "request_rate": snap.get("rps"),
            "container_state": snap.get("container_state")}


def verification_event_data(result: VerificationResult) -> Dict[str, Any]:
    return {"status": result.status, "recovered": result.recovered, "before": _event_snapshot(result.before),
            "after": _event_snapshot(result.after), "reasons": list(result.reasons)}


def _fmt(value: Any, digits: int, unit: str = "") -> str:
    return "n/a" if value is None else f"{value:.{digits}f}{unit}"


def verification_summary(result: VerificationResult) -> str:
    if result.status == NOT_VERIFIED_DRY_RUN:
        return f"{result.status}: dry run, nothing changed, recovery not claimed"
    b, a = result.before, result.after
    line = (f"{result.status}: error_rate {_fmt(b.get('error_rate'), 2)} -> {_fmt(a.get('error_rate'), 2)}, "
            f"p95 {_fmt(b.get('p95_ms'), 0, 'ms')} -> {_fmt(a.get('p95_ms'), 0, 'ms')}")
    if result.status != RECOVERED and result.reasons:
        line += f" ({result.reasons[0]})"
    return line


def _phase_evidence(before: Dict[str, Any], after: Dict[str, Any]) -> List[Dict[str, Any]]:
    return ([dict(e, phase="before") for e in before.get("evidence", []) or []]
            + [dict(e, phase="after") for e in after.get("evidence", []) or []])
