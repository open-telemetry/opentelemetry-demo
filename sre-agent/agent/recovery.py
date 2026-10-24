"""Step 6b - VERIFY recovery after an approved action; roll back + escalate if it did not recover.

Recovered = for 2 consecutive polls, none of the alert rules fire for the root-cause service or the
services that were symptomatic in the alert (their error rate / p95 / traffic back near baseline and the
container running). Waits up to VERIFY_SECONDS.

A Docker healthcheck that still says "unhealthy" while the container runs and its metrics are back to
normal does NOT block recovery (the demo's healthchecks lag or can be flaky on a busy laptop); it is
reported as a warning. Exception: if the diagnosed fault IS a readiness/health failure, it blocks.
"""
import time

from agent import config, detect


def _relevant(ev: dict, watch: set) -> list:
    return [r for r in ev["reasons"] if any(r.startswith(s + " ") or f" {s} " in r for s in watch)]


def _healthcheck_only(reason: str) -> bool:
    return reason.startswith("container ") and reason.endswith(" unhealthy")


def verify(watch_services: list, before: dict = None, log=print, snapshot=None,
           seconds: int = None, poll: int = None, fault_type: str = None) -> dict:
    snapshot = snapshot or (lambda: detect.snapshot(config.VERIFY_WINDOW))
    seconds = config.VERIFY_SECONDS if seconds is None else seconds
    poll = config.VERIFY_POLL if poll is None else poll
    watch = set(watch_services)
    timeline, good, warnings = [], 0, set()
    t0 = time.time()
    if poll:
        time.sleep(poll)  # give span metrics time to reflect the change
    while True:
        snap = snapshot()
        bad = _relevant(snap["eval"], watch)
        if fault_type != "readiness_failure":
            soft = [r for r in bad if _healthcheck_only(r)]
            bad = [r for r in bad if not _healthcheck_only(r)]
            warnings.update(soft)
        else:
            soft = []
        row = {"t_plus_s": round(time.time() - t0), "still_failing": bad, "warnings": soft,
               "metrics": {s: snap["health"].get(s) for s in watch if snap["health"].get(s)}}
        timeline.append(row)
        log(f"  verify t+{row['t_plus_s']}s: " + ("healthy" if not bad else "; ".join(bad[:3]))
            + (f"   (warning, not blocking: {'; '.join(soft)})" if soft else ""))
        good = good + 1 if not bad and not snap["errors"] else 0
        if good >= 2:
            return {"recovered": True, "after_seconds": row["t_plus_s"], "timeline": timeline,
                    "before": before, "after": row["metrics"], "warnings": sorted(warnings)}
        if time.time() - t0 >= seconds:
            return {"recovered": False, "after_seconds": row["t_plus_s"], "timeline": timeline,
                    "before": before, "after": row["metrics"], "still_failing": bad,
                    "warnings": sorted(warnings)}
        time.sleep(poll)
