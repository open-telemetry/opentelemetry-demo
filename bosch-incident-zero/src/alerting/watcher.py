"""Alert watcher: polls Prometheus, and when a service stays unhealthy starts one agent run with that alert.

It only automates detection and the start of an investigation. Every proposed action still waits for a human
decision on the approval page; the watcher never approves anything.
"""
from __future__ import annotations

import dataclasses
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List, Optional


@dataclass(frozen=True)
class Rules:
    error_rate: float = 0.05
    min_errors: float = 3.0
    p95_ms: float = 5000.0
    min_rps: float = 0.01
    window_seconds: int = 300
    consecutive: int = 2
    refire_seconds: float = 3600.0
    max_runs_per_day: int = 4


@dataclass(frozen=True)
class Alert:
    service: str
    text: str
    severity: float


@dataclass
class _State:
    firing_polls: Dict[str, int] = field(default_factory=dict)
    fired_at: Dict[str, float] = field(default_factory=dict)
    runs_today: int = 0
    day: str = ""


def evaluate(overview: Dict[str, Dict[str, float]], rules: Rules) -> List[Alert]:
    """Alerts for services breaching a rule right now, worst first. Alert text names the symptom only."""
    alerts = []
    for service, m in overview.items():
        rps = m.get("requests_per_second") or 0.0
        if rps < rules.min_rps:
            continue
        err = m.get("error_rate_ratio") or 0.0
        failures = err * rps * rules.window_seconds
        p95 = m.get("p95_latency_ms") or 0.0
        if err >= rules.error_rate and failures >= rules.min_errors:
            alerts.append(Alert(service, f"Error rate above {rules.error_rate:.0%} on {service}", 1.0 + err))
        elif rules.p95_ms and p95 >= rules.p95_ms:
            alerts.append(Alert(service, f"p95 latency above {rules.p95_ms:.0f} ms on {service}",
                                p95 / rules.p95_ms - 1.0))
    return sorted(alerts, key=lambda a: (-a.severity, a.service))


class AlertWatcher:
    """One incident at a time: debounce, fire once per firing period, re-arm after recovery, daily run cap."""

    def __init__(self, overview: Callable[[], Dict[str, Dict[str, float]]], launch: Callable[[Alert], object],
                 running: Callable[[], bool], rules: Rules = Rules(), clock: Callable[[], float] = time.time,
                 log: Callable[[str], None] = print) -> None:
        self.overview, self.launch, self.running = overview, launch, running
        self.rules, self.clock, self.log = rules, clock, log
        self.state = _State()

    def poll(self) -> Optional[Alert]:
        """Evaluate once; return the alert that started a run, if any."""
        now = self.clock()
        day = datetime.fromtimestamp(now, timezone.utc).strftime("%Y-%m-%d")
        if day != self.state.day:
            self.state.day, self.state.runs_today = day, 0
        try:
            alerts = evaluate(self.overview(), self.rules)
        except Exception as exc:
            self.log(f"metrics unavailable: {exc}")
            return None
        firing = {a.service for a in alerts}
        for service in list(self.state.firing_polls):
            if service not in firing:
                del self.state.firing_polls[service]
                if self.state.fired_at.pop(service, None) is not None:
                    self.log(f"resolved: {service}")
        for service in firing:
            self.state.firing_polls[service] = self.state.firing_polls.get(service, 0) + 1
        ready = [a for a in alerts
                 if self.state.firing_polls[a.service] >= self.rules.consecutive
                 and now - self.state.fired_at.get(a.service, float("-inf")) >= self.rules.refire_seconds]
        if not ready:
            return None
        if self.running():
            for a in ready:
                self.state.fired_at[a.service] = now
            return None
        if self.state.runs_today >= self.rules.max_runs_per_day:
            self.log(f"daily cap of {self.rules.max_runs_per_day} runs reached; not starting: {ready[0].text}")
            for a in ready:
                self.state.fired_at[a.service] = now
            return None
        alert = ready[0]
        for service in firing:
            self.state.fired_at[service] = now
        self.state.runs_today += 1
        self.log(f"FIRING: {alert.text} (also firing: {', '.join(sorted(firing - {alert.service})) or 'none'})")
        self.launch(alert)
        return alert


class AgentLauncher:
    """Starts `python -m src.agent` for an alert, chat approval, dry run, one run at a time."""

    def __init__(self, root_dir: Path, log_dir: Path, approval_timeout: int, dry_run: bool = True,
                 notify: Callable[[str], None] = lambda text: None) -> None:
        self.root_dir, self.log_dir = root_dir, log_dir
        self.approval_timeout, self.dry_run, self.notify = approval_timeout, dry_run, notify
        self.proc: Optional[subprocess.Popen] = None

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def __call__(self, alert: Alert) -> subprocess.Popen:
        import os

        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.log_dir / f"auto-{datetime.now():%Y%m%d-%H%M%S}-{alert.service}.log"
        env = {**os.environ, "APPROVAL_TIMEOUT_SECONDS": str(self.approval_timeout)}
        cmd = [sys.executable, "-m", "src.agent", "--alert", alert.text, "--approve-via", "chat",
               "--dry-run" if self.dry_run else "--no-dry-run"]
        with open(log_path, "w", encoding="utf-8") as out:
            self.proc = subprocess.Popen(cmd, cwd=self.root_dir, env=env, stdout=out, stderr=subprocess.STDOUT,
                                         stdin=subprocess.DEVNULL)
        self.notify(alert.text)
        return self.proc


def mac_notify(text: str) -> None:
    if sys.platform != "darwin":
        return
    message = text.replace("\\", "").replace('"', "'")
    script = f'display notification "{message}" with title "Incident Zero" subtitle "Review at http://localhost:8799"'
    try:
        subprocess.run(["osascript", "-e", script], timeout=5, check=False, capture_output=True)
    except (OSError, subprocess.SubprocessError):
        pass


def rules_with(**overrides: object) -> Rules:
    return dataclasses.replace(Rules(), **{k: v for k, v in overrides.items() if v is not None})
