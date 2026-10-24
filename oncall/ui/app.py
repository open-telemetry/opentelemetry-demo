"""Demo UI: watch the agent investigate an alert, live or replayed from a run log.

Run from the repo root: streamlit run oncall/ui/app.py
Read-only: it calls the agent and the read-only tools, and reads RUNS_DIR/*.jsonl.
No action is ever executed from here.
"""

import json
import os
import re
import sys
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

# `streamlit run` puts only this file's folder on sys.path, so add the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import httpx
import pandas as pd
import streamlit as st

from oncall.agent.loop import investigate_and_diagnose
from oncall.agent.runlog import RunLog
from oncall.agent.taxonomy import CLIENT_SERVICES
from oncall.config import Settings, load_settings
from oncall.endpoints import resolve_endpoints
from oncall.main import _manual_alert
from oncall.models import MAX_EVIDENCE_ITEMS, ToolResult, scrub_flags
from oncall.platform.containers import (
    DockerError,
    check_containers,
    compose_container_ids,
    inspect_containers,
)
from oncall.report.output import report_run
from oncall.safety.exclusions import EXCLUDED_SERVICES
from oncall.tools import TOOLS
from oncall.tools.backends import BackendError, LiveBackend, get_backend
from oncall.tools.metrics import _build_promql, _extract_vector_results

DEFAULT_ALERT = "users report errors when shopping"
ANY_SERVICE = "(any service)"
ENV_KEYS = {
    "prometheus": "PROM_URL",
    "jaeger": "JAEGER_URL",
    "opensearch": "OPENSEARCH_URL",
}
MAX_PAST_RUNS = 30
NO_ACTION_CAPTION = "Approval gate + Action API land on Day 2 (F19/F22)"

# container_health evidence text: "<name>: state=<state>, health=<health>, ..."
CONTAINER_TEXT = re.compile(r"^(?P<name>[^:]+): state=(?P<state>[^,]+),")
HEALTH_METRICS = ("error_rate", "latency_p95", "rps")
HEALTH_WINDOW = "5m"
BASELINE_OFFSETS_MIN = (30, 15, 10)
# metric -> (regression factor vs baseline, label)
REGRESSION_FACTORS = {
    "error_rate": (3.0, "errors"),
    "latency_p95": (2.0, "p95"),
    "rps": (2.0, "rps"),
}
FLAGGED = " | FLAGGED: "


def fetch_metrics(backend) -> tuple[dict[str, dict], int | None]:
    """({service: {metric: (now, baseline or None)}}, baseline offset used).

    Same PromQL as get_metrics, but for all services (get_metrics keeps only its
    top 5 as evidence). The baseline is the first of BASELINE_OFFSETS_MIN with
    data, so the panel still compares after Prometheus restarts.
    """
    now_ts = datetime.now(UTC).timestamp()
    values: dict[str, dict] = {}
    used = None
    for metric in HEALTH_METRICS:
        promql = _build_promql(metric, None, HEALTH_WINDOW)
        now = _extract_vector_results(backend.prom_query(promql))
        base: dict[str, float] = {}
        for offset in BASELINE_OFFSETS_MIN if used is None else (used,):
            at = str(int(now_ts - offset * 60))
            base = _extract_vector_results(backend.prom_query(promql, at=at))
            if base:
                used = offset
                break
        for service, value in now.items():
            values.setdefault(service, {})[metric] = (
                value,
                base.get(service, 0.0) if base else None,
            )
    for metrics in values.values():
        # The error-rate ratio has no series when a service had no errors at all.
        if "rps" in metrics and "error_rate" not in metrics:
            metrics["error_rate"] = (0.0, 0.0 if used is not None else None)
    return values, used


def regressions(values: dict, error_floor: float) -> list[str]:
    """Which of a service's metrics regressed against an existing baseline."""
    found = []
    for metric, (factor, label) in REGRESSION_FACTORS.items():
        now, base = values.get(metric, (None, None))
        if now is None or base is None:
            continue
        floor = error_floor if metric == "error_rate" else 0.0
        if base > 0 and now >= factor * base and now >= floor:
            found.append(f"{label} {now / base:.1f}x")
        elif base == 0 and metric == "error_rate" and now >= error_floor:
            found.append(f"{label} new")
    return found


def health_rows(
    containers: ToolResult, metrics: dict, error_floor: float
) -> list[dict]:
    """One row per service from container_health output + fetch_metrics() values."""
    rows: dict[str, dict] = {}

    def row(service: str) -> dict:
        return rows.setdefault(
            service, {"service": service, "status": "no container data", "metrics": {}}
        )

    for ev in containers["evidence"] if containers["ok"] else []:
        m = CONTAINER_TEXT.match(ev["text"])
        if m:
            problems = ev["text"].partition(FLAGGED)[2]
            row(m["name"])["status"] = (
                f"unhealthy: {problems}" if problems else m["state"]
            )
    for service, values in metrics.items():
        row(service)["metrics"] = values

    result = []
    for r in rows.values():
        if r["service"] in EXCLUDED_SERVICES:
            continue
        r["client"] = r["service"] in CLIENT_SERVICES
        r["regressions"] = [] if r["client"] else regressions(r["metrics"], error_floor)
        r["unhealthy"] = not r["client"] and (
            r["status"].startswith("unhealthy") or bool(r["regressions"])
        )
        result.append(r)
    return sorted(result, key=lambda r: (not r["unhealthy"], r["client"], r["service"]))


def with_dropped_containers(
    result: ToolResult, infos: list[dict], now: datetime
) -> ToolResult:
    """Add the containers container_health left out once it hit MAX_EVIDENCE_ITEMS.

    It lists flagged containers first, so the dropped ones were healthy.
    """
    if not result["ok"]:
        return result
    seen = {e["id"] for e in result["evidence"]}
    dropped = [
        i for i in infos if f"container:{(i.get('Name') or '').lstrip('/')}" not in seen
    ]
    evidence = list(result["evidence"])
    for start in range(0, len(dropped), MAX_EVIDENCE_ITEMS):
        chunk = dropped[start : start + MAX_EVIDENCE_ITEMS]
        evidence += check_containers(chunk, [], None, now, max_healthy=None)["evidence"]
    return {**result, "evidence": evidence}


def all_container_health(settings: Settings) -> ToolResult:
    result = TOOLS["container_health"]()
    if settings.TELEMETRY_BACKEND == "offline":
        return result
    try:
        infos = inspect_containers(compose_container_ids(settings.COMPOSE_PROJECT_NAME))
    except DockerError:
        return result
    return with_dropped_containers(result, infos, datetime.now(UTC))


def tool_steps(events: list[dict]) -> list[dict]:
    """Pair each tool_call event with the tool_result that follows it."""
    steps: list[dict] = []
    for e in events:
        if e["event"] == "tool_call":
            steps.append(
                {
                    "step": e.get("step"),
                    "name": e.get("name"),
                    "args": e.get("args"),
                    "result": None,
                }
            )
        elif e["event"] == "tool_result" and steps and steps[-1]["result"] is None:
            steps[-1]["result"] = e.get("result")
    return steps


def list_runs(runs_dir: str) -> list[Path]:
    """Run logs, newest first."""
    return sorted(
        Path(runs_dir).glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True
    )


def run_label(path: Path) -> str:
    alerts = RunLog(run_id=path.stem, runs_dir=str(path.parent)).events("alert")
    description = (
        (alerts[0].get("alert") or {}).get("description", "") if alerts else ""
    )
    return f"{path.stem} · {description[:40]}" if description else path.stem


@st.cache_resource
def configure() -> tuple[Settings, dict]:
    """Load settings and the endpoints the tools' backends resolve the same way."""
    settings = load_settings()
    if settings.TELEMETRY_BACKEND == "offline":
        return settings, {}
    return settings, resolve_endpoints(settings)


@st.cache_data(ttl=30, show_spinner=False)
def jaeger_v3_services(jaeger_url: str) -> list[str]:
    """Services from Jaeger's v3 API; JAEGER_URL is e.g. http://127.0.0.1:8080/jaeger/ui."""
    res = httpx.get(f"{jaeger_url.rstrip('/')}/api/v3/services", timeout=3)
    res.raise_for_status()
    return res.json().get("services") or []


def probe(endpoints: dict) -> tuple[dict[str, str | None], list[str]]:
    """Reachability per backend (None when reachable, else the error) and Jaeger's services."""
    backend = LiveBackend(
        prom_url=endpoints.get("prometheus"),
        jaeger_url=endpoints.get("jaeger"),
        opensearch_url=endpoints.get("opensearch"),
        timeout=3,
    )
    checks = {
        "prometheus": lambda: backend.prom_query("vector(1)"),
        "jaeger": lambda: jaeger_v3_services(endpoints["jaeger"]),
        "opensearch": lambda: httpx.get(
            backend.opensearch_url, timeout=3
        ).raise_for_status(),
    }
    status: dict[str, str | None] = {}
    services: list[str] = []
    for name, check in checks.items():
        if not endpoints.get(name):
            status[name] = f"endpoint not found; set {ENV_KEYS[name]}"
            continue
        try:
            out = check()
        except (BackendError, httpx.HTTPError, ValueError) as exc:
            status[name] = str(exc)
            continue
        status[name] = None
        if name == "jaeger":
            services = list(out)
    return status, services


def render_header(settings: Settings, endpoints: dict) -> list[str]:
    st.title("AI On-Call Engineer")
    if settings.TELEMETRY_BACKEND == "offline":
        scenario = os.environ.get("OFFLINE_SCENARIO", "baseline")
        st.caption(f"Offline replay of scenario `{scenario}`")
        try:
            return get_backend().jaeger_services()
        except BackendError:
            return []
    status, services = probe(endpoints)
    st.markdown(
        " &nbsp; ".join(
            f"{'🟢' if err is None else '🔴'} {name}" for name, err in status.items()
        )
    )
    errors = {name: err for name, err in status.items() if err}
    if errors:
        with st.expander("Backend errors"):
            for name, err in errors.items():
                st.text(f"{name}: {err}")
    return services


def _fmt_rate(value: float | None) -> str:
    return "—" if value is None else f"{value:.2%}"


def _fmt_ms(value: float | None) -> str:
    return "—" if value is None else f"{value:.0f}"


def _fmt_rps(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}"


def _pair(row: dict, metric: str, fmt) -> str:
    now, base = row["metrics"].get(metric, (None, None))
    return f"{fmt(now)} / {fmt(base)}"


def render_health(settings: Settings) -> None:
    st.subheader("System health")
    if st.button("Refresh"):
        with st.spinner("Checking containers, errors, latency and traffic…"):
            try:
                (values, offset), error = fetch_metrics(get_backend()), None
            except BackendError as exc:
                (values, offset), error = ({}, None), str(exc)
            st.session_state.health = (
                all_container_health(settings),
                values,
                offset,
                error,
            )
    if "health" not in st.session_state:
        st.caption("Press Refresh to check containers, errors, latency and traffic.")
        return
    containers, metrics, offset, error = st.session_state.health
    st.caption(
        f"Now = last {HEALTH_WINDOW}; base = same window {offset} min ago."
        if offset
        else "No baseline yet (Prometheus history too short): no regressions marked."
    )
    if not containers["ok"]:
        st.warning(f"container_health: {containers['error']}")
    if error:
        st.warning(f"metrics: {error}")
    rows = health_rows(containers, metrics, settings.ALERT_ERROR_RATE)
    if not rows:
        st.info("No container or metric data.")
        return
    df = pd.DataFrame(
        [
            {
                "service": r["service"] + (" (client)" if r["client"] else ""),
                "status": r["status"],
                "errors now / base": _pair(r, "error_rate", _fmt_rate),
                "p95 ms now / base": _pair(r, "latency_p95", _fmt_ms),
                "rps now / base": _pair(r, "rps", _fmt_rps),
                "regression": ", ".join(r["regressions"]),
            }
            for r in rows
        ]
    )

    def style(line: pd.Series) -> list[str]:
        r = rows[line.name]
        if r["client"]:
            css = "color: gray"
        elif r["unhealthy"]:
            css = "background-color: rgba(220, 38, 38, 0.25)"
        else:
            css = ""
        return [css] * len(line)

    st.dataframe(df.style.apply(style, axis=1), hide_index=True, width="stretch")


def start_run(settings: Settings, description: str, service: str | None) -> None:
    run_id = f"{datetime.now(UTC):%Y%m%d_%H%M%S}_ui{uuid.uuid4().hex[:4]}"
    runlog = RunLog(run_id=run_id, runs_dir=settings.RUNS_DIR)
    alert = _manual_alert(service, description)

    def work() -> None:
        diagnosis = None
        try:
            diagnosis = investigate_and_diagnose(alert, runlog=runlog)["diagnosis"]
        except Exception as exc:  # noqa: BLE001
            runlog.log("error", where="ui", error=f"{type(exc).__name__}: {exc}")
        report_run(alert, diagnosis, runlog)

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    st.session_state.live = (run_id, thread)
    st.session_state.view_run = run_id
    st.rerun()


def render_alert_form(settings: Settings, services: list[str], running: bool) -> None:
    st.subheader("Alert")
    description = st.text_input("What is wrong?", DEFAULT_ALERT)
    options = [ANY_SERVICE, *sorted(s for s in services if s not in EXCLUDED_SERVICES)]
    service = st.selectbox("Service (optional)", options)
    if st.button("Investigate", type="primary", disabled=running):
        start_run(settings, description, None if service == ANY_SERVICE else service)


def render_steps(events: list[dict]) -> None:
    for s in tool_steps(events):
        with st.container(border=True):
            st.markdown(f"**Step {s['step']}** · `{s['name']}`")
            st.code(json.dumps(s["args"]), language="json")
            result = s["result"]
            if result is None:
                st.caption("running…")
                continue
            st.text(result.get("summary") or f"error: {result.get('error')}")
            with st.expander("Full ToolResult"):
                st.json(result, expanded=True)
    for e in events:
        if e["event"] == "error":
            st.error(
                f"{e.get('where', 'error')}: {e.get('error') or e.get('problems')}"
            )


def render_diagnosis(runlog: RunLog, d: dict) -> None:
    with st.container(border=True):
        left, right = st.columns(2)
        left.metric("Component", d.get("component") or "unknown")
        right.metric("Category", d.get("category") or "unknown")
        badge = {
            "act": ":green-background[**ACT**]",
            "no_action": ":blue-background[**NO ACTION**]",
        }.get(d.get("decision"), ":orange-background[**ESCALATE**]")
        st.markdown(f"Decision: {badge}")
        confidence = min(max(float(d.get("confidence") or 0), 0.0), 1.0)
        st.progress(confidence, text=f"Confidence {confidence:.0%}")
        st.markdown("**Cause**")
        st.text(d.get("cause", ""))
        st.markdown("**Reasoning**")
        st.text(d.get("reasoning", ""))
        if d.get("alternatives"):
            st.markdown("**Alternatives considered**")
            for a in d["alternatives"]:
                st.text(
                    f"- {a.get('hypothesis')}: rejected because {a.get('rejected_because')}"
                )

    st.markdown("**Evidence**")
    index = runlog.evidence_index()
    if not d.get("evidence_ids"):
        st.caption("No evidence cited.")
    for eid in d.get("evidence_ids", []):
        with st.expander(eid):
            item = index.get(eid)
            if item:
                st.text(item.get("text", ""))
                if item.get("ts"):
                    st.caption(item["ts"])
            else:
                st.warning("Not found in this run's evidence index.")


def render_action(events: list[dict]) -> None:
    st.subheader("Action")
    actions = [e for e in events if e["event"] == "action"]
    if actions:
        st.json(actions[-1])
    else:
        st.caption("No action proposed.")
    left, right = st.columns(2)
    left.button("Approve", disabled=True, width="stretch")
    right.button("Reject", disabled=True, width="stretch")
    st.caption(NO_ACTION_CAPTION)


def render_run(settings: Settings, run_id: str, running: bool) -> None:
    runlog = RunLog(run_id=run_id, runs_dir=settings.RUNS_DIR)
    events = [scrub_flags(e) for e in runlog.events()]
    st.subheader("Investigation")
    tokens = runlog.token_usage()["total_tokens"]
    st.caption(
        f"run `{run_id}` · {'running…' if running else 'done'} · tokens so far: {tokens}"
    )
    render_steps(events)

    finishes = [e for e in events if e["event"] == "finish"]
    decisions = [e for e in events if e["event"] == "decision" and "diagnosis" in e]
    reports = [e for e in events if e.get("stage") == "report"]
    if not finishes:
        return
    st.subheader("Result")
    st.markdown("**Symptom summary**")
    st.text(finishes[-1].get("summary") or "(no summary)")
    if not decisions:
        st.caption(
            "Waiting for the diagnosis…" if running else "No diagnosis in this run."
        )
        return
    render_diagnosis(runlog, decisions[-1]["diagnosis"])
    if reports:
        st.caption(f"Report: `{reports[-1]['json_path']}` + `{reports[-1]['md_path']}`")
    render_action(events)


@st.fragment(run_every=1)
def live_view(settings: Settings, run_id: str, thread: threading.Thread) -> None:
    running = thread.is_alive()
    render_run(settings, run_id, running)
    if not running:
        st.rerun()


def render_sidebar(settings: Settings) -> None:
    st.sidebar.header("Past runs")
    runs = list_runs(settings.RUNS_DIR)
    if not runs:
        st.sidebar.caption("No runs yet.")
    for path in runs[:MAX_PAST_RUNS]:
        if st.sidebar.button(run_label(path), key=f"run-{path.stem}", width="stretch"):
            st.session_state.view_run = path.stem


def main() -> None:
    st.set_page_config(page_title="AI On-Call Engineer", layout="wide")
    settings, endpoints = configure()
    services = render_header(settings, endpoints)
    render_sidebar(settings)
    render_health(settings)

    live_id, thread = st.session_state.get("live", (None, None))
    running = thread is not None and thread.is_alive()
    render_alert_form(settings, services, running)

    run_id = st.session_state.get("view_run")
    if not run_id:
        return
    if running and run_id == live_id:
        live_view(settings, run_id, thread)
    else:
        render_run(settings, run_id, running=False)


if __name__ == "__main__":
    main()
