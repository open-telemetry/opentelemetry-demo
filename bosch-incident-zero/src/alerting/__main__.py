"""Run the incident hub and the alert watcher together; Ctrl+C stops both.

    python -m src.alerting [--interval 30] [--error-rate 0.05] [--p95-ms 5000] [--max-runs-per-day 4]
"""
from __future__ import annotations

import argparse
import threading
import time
from datetime import datetime

from ..config import Settings
from ..telemetry.prometheus_client import PrometheusClient
from .watcher import AgentLauncher, AlertWatcher, mac_notify, rules_with


def log(text: str) -> None:
    print(f"{datetime.now():%H:%M:%S} [ALERTS] {text}", flush=True)


def start_hub(settings: Settings) -> None:
    from ..approval.chat_ui.hub import Hub

    try:
        hub = Hub(settings, port=settings.chat_ui_port)
    except OSError:
        log(f"port {settings.chat_ui_port} is in use; assuming the hub is already running there")
        return
    threading.Thread(target=hub.serve_forever, daemon=True).start()
    log(f"incident hub at {hub.url}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--interval", type=float, default=30, help="seconds between checks")
    parser.add_argument("--error-rate", type=float, help="error-rate threshold (default 0.05)")
    parser.add_argument("--min-errors", type=float, help="failed requests in the window to count (default 3)")
    parser.add_argument("--p95-ms", type=float, help="p95 latency threshold in ms, 0 disables (default 5000)")
    parser.add_argument("--consecutive", type=int, help="checks in a row before firing (default 2)")
    parser.add_argument("--max-runs-per-day", type=int, help="agent runs per UTC day (default 4: free LLM quota)")
    parser.add_argument("--approval-timeout", type=int, default=900, help="seconds a human has to decide")
    parser.add_argument("--no-hub", action="store_true", help="do not start the hub in this process")
    args = parser.parse_args()

    settings = Settings()
    rules = rules_with(error_rate=args.error_rate, min_errors=args.min_errors, p95_ms=args.p95_ms,
                       consecutive=args.consecutive, max_runs_per_day=args.max_runs_per_day)
    prometheus = PrometheusClient(settings.prometheus_url)
    launcher = AgentLauncher(settings.root_dir, settings.root_dir / "audit_logs" / "auto_runs",
                             approval_timeout=args.approval_timeout, notify=mac_notify)
    watcher = AlertWatcher(lambda: prometheus.get_services_overview(rules.window_seconds),
                           launcher, launcher.running, rules=rules, log=log)
    if not args.no_hub:
        start_hub(settings)
    log(f"watching every {args.interval:.0f}s: error rate >= {rules.error_rate:.0%} "
        f"(at least {rules.min_errors:.0f} failures in {rules.window_seconds}s), p95 >= {rules.p95_ms:.0f} ms; "
        f"{rules.consecutive} checks in a row; max {rules.max_runs_per_day} runs/day")
    active = False
    try:
        while True:
            if active and not launcher.running():
                log(f"agent run finished (exit {launcher.proc.returncode}); report in incident_output/")
            if watcher.poll():
                log(f"agent started (pid {launcher.proc.pid}); approve or reject at http://localhost:8799")
            active = launcher.running()
            time.sleep(args.interval)
    except KeyboardInterrupt:
        log("stopped")


if __name__ == "__main__":
    main()
