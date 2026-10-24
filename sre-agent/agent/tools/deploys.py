"""EYES / runtime + deploy history from Docker (read-only).

* container state: running/exited, restarts, OOM kills, health checks
* deploy history: when each container was created / (re)started and with which image
* resource usage: CPU% / memory% of limit, compared with a HEALTHY BASELINE snapshot
  (some containers sit at 95% memory all the time - that is normal for them, not an incident)

NOTE: this module deliberately does NOT read feature-flag settings (flagd files / flag UI / flag API).
That is forbidden by the hackathon rules - diagnosis must come from telemetry.
"""
import json
import subprocess
from datetime import datetime, timezone

from agent import config

BASELINE_FILE = config.RUNS / "runtime_baseline.json"


def _run(args, timeout=20) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout).stdout
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _parse_ts(s: str):
    try:
        return datetime.fromisoformat(s[:26].rstrip("Z") + "+00:00")
    except Exception:
        return None


def _min_ago(ts, now):
    return round((now - ts).total_seconds() / 60, 1) if ts and ts.year > 1 else None


def containers() -> dict:
    names = _run(["docker", "ps", "-a", "--format", "{{.Names}}"]).split()
    if not names:
        raise RuntimeError("docker not reachable or no containers")
    data = json.loads(_run(["docker", "inspect", *names]) or "[]")
    now = datetime.now(timezone.utc)
    out = {}
    for c in data:
        st = c["State"]
        out[c["Name"].lstrip("/")] = {
            "status": st.get("Status"),
            "health": (st.get("Health") or {}).get("Status"),
            "restart_count": c.get("RestartCount", 0),
            "oom_killed": st.get("OOMKilled", False),
            "exit_code": st.get("ExitCode"),
            "error": st.get("Error") or None,
            "created_min_ago": _min_ago(_parse_ts(c.get("Created", "")), now),
            "started_min_ago": _min_ago(_parse_ts(st.get("StartedAt", "")), now),
            "finished_min_ago": _min_ago(_parse_ts(st.get("FinishedAt", "")), now),
            "image": c["Config"]["Image"].split("/")[-1],
            "mem_limit_mb": round(c["HostConfig"].get("Memory", 0) / 1e6) or None,
            "cpu_limit": (c["HostConfig"].get("NanoCpus") or 0) / 1e9 or None,
        }
    return out


def resource_usage() -> dict:
    out = {}
    for line in _run(["docker", "stats", "--no-stream", "--format", "{{json .}}"], timeout=40).splitlines():
        try:
            d = json.loads(line)
            out[d["Name"]] = {"cpu_pct": float(d["CPUPerc"].rstrip("%")),
                              "mem_pct": float(d["MemPerc"].rstrip("%")),
                              "mem_usage": d["MemUsage"].split("/")[0].strip()}
        except Exception:
            continue
    return out


def save_baseline(usage: dict = None) -> dict:
    usage = usage or resource_usage()
    BASELINE_FILE.write_text(json.dumps({"taken_at": datetime.now(timezone.utc).isoformat(), "usage": usage}), encoding="utf-8")
    return usage


def _baseline() -> dict:
    try:
        return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))["usage"]
    except Exception:
        return {}


def analyse(cs: dict = None, usage: dict = None) -> dict:
    """Facts that differ from normal. Each event is a short string starting with the container name."""
    cs = cs if cs is not None else containers()
    usage = usage if usage is not None else resource_usage()
    base = _baseline()
    events = []
    for name, c in sorted(cs.items()):
        if c["status"] != "running":
            events.append(f"{name} is {c['status']} (exit code {c['exit_code']}, "
                          f"stopped {c['finished_min_ago']} min ago)")
        if c["oom_killed"]:
            events.append(f"{name} was OOM-killed")
        if c["restart_count"]:
            events.append(f"{name} restarted {c['restart_count']}x (last start {c['started_min_ago']} min ago)")
        if c["health"] == "unhealthy":
            events.append(f"{name} healthcheck unhealthy")
        if c["status"] == "running" and c["started_min_ago"] is not None and c["started_min_ago"] < 15:
            events.append(f"{name} (re)started {c['started_min_ago']} min ago")
        u, b = usage.get(name), base.get(name)
        if not u:
            continue
        if b:  # compare with the healthy snapshot
            if u["cpu_pct"] > 60 and u["cpu_pct"] > 3 * max(b["cpu_pct"], 5):
                events.append(f"{name} CPU {u['cpu_pct']:.0f}% (baseline {b['cpu_pct']:.0f}%)")
            if u["mem_pct"] > 85 and u["mem_pct"] > b["mem_pct"] + 15:
                events.append(f"{name} memory {u['mem_pct']:.0f}% of limit (baseline {b['mem_pct']:.0f}%, "
                              f"{u['mem_usage']})")
        else:  # no baseline yet: only extreme values
            if u["cpu_pct"] > 150:
                events.append(f"{name} CPU {u['cpu_pct']:.0f}% (no baseline)")
    return {"events": events, "baseline_available": bool(base),
            "abnormal_containers": {k: v for k, v in cs.items()
                                    if v["status"] != "running" or v["restart_count"] or v["oom_killed"]
                                    or v["health"] == "unhealthy"}}


def container_health(service: str) -> dict:
    cs = containers()
    usage = resource_usage()
    c = cs.get(service)
    if c is None:
        return {"service": service, "error": f"no container named {service}",
                "known": sorted(cs)[:40]}
    return {"service": service, **c, "usage": usage.get(service), "baseline_usage": _baseline().get(service)}


def deploy_history(within_min: float = 60) -> list:
    """'Deploys' in this demo = containers created or (re)started recently, newest first."""
    rows = []
    for name, c in containers().items():
        for kind, ago in (("created", c["created_min_ago"]), ("started", c["started_min_ago"])):
            if ago is not None and ago <= within_min:
                rows.append({"container": name, "event": kind, "min_ago": ago, "image": c["image"],
                             "status": c["status"]})
    return sorted(rows, key=lambda r: r["min_ago"])[:25]
