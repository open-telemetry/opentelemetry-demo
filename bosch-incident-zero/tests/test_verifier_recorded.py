import copy
import json
from pathlib import Path

from src.events import EventLog
from src.models.action import ActionType, RemediationAction
from src.remediation import verifier
from src.remediation.verifier import NO_DATA, NOT_RECOVERED, RECOVERED, capture_baseline, verify_recovery

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "verifier" / "frontend_latency_incident.json").read_text())
SVC = FIXTURE["service"]


def replay(monkeypatch, recorded):
    monkeypatch.setattr(verifier, "system_overview", lambda ctx, window_minutes=5: recorded["system_overview"])
    monkeypatch.setattr(verifier, "get_service_metrics",
                        lambda ctx, service, window_minutes=10: recorded["get_service_metrics"])
    monkeypatch.setattr(verifier, "container_health", lambda ctx, service=None: recorded["container_health"])


def healed(recorded):
    """The recorded incident with frontend back at its recorded 30m-earlier p95 and no anomaly flag."""
    out = copy.deepcopy(recorded)
    row = out["system_overview"]["data"]["services"][0]
    row.update(p95_ms=row["baseline_p95_ms"], flags=[])
    return out


def action():
    return RemediationAction(action_id="ACT-REC", action_type=ActionType.RESTART_SERVICE, target_service=SVC,
                             description="Restart frontend")


def baseline(monkeypatch):
    replay(monkeypatch, FIXTURE)
    return capture_baseline(None, SVC, window_minutes=2)


def test_recorded_baseline_matches_tool_values(monkeypatch):
    base = baseline(monkeypatch)
    row = FIXTURE["system_overview"]["data"]["services"][0]
    assert (base["error_rate"], base["p95_ms"], base["rps"]) == (row["error_rate"], row["p95_ms"], row["rps"])
    assert base["flags"] == ["latency_up"]
    assert base["container_state"] == "running"
    assert base["missing"] == {}


def test_recorded_incident_unchanged_is_not_recovered(monkeypatch):
    base = baseline(monkeypatch)
    log = EventLog(echo=False)
    res = verify_recovery(None, action(), base, settle_seconds=120, dry_run=False, sleep=lambda s: None, events=log)
    assert res.status == NOT_RECOVERED
    rec = log.records[-1]
    assert rec["event"] == "VERIFICATION" and rec["data"]["status"] == NOT_RECOVERED
    assert rec["summary"].startswith("NOT_RECOVERED: error_rate 0.00 -> 0.00, p95 ")


def test_recorded_incident_back_to_pre_incident_latency_is_recovered(monkeypatch):
    base = baseline(monkeypatch)
    replay(monkeypatch, healed(FIXTURE))
    log = EventLog(echo=False)
    res = verify_recovery(None, action(), base, settle_seconds=120, dry_run=False, sleep=lambda s: None, events=log)
    assert res.status == RECOVERED, res.reasons
    assert log.records[-1]["data"]["recovered"] is True
    assert set(log.records[-1]["data"]["after"]) == {"error_rate", "p95_ms", "request_rate", "container_state"}


def test_recorded_incident_with_no_traffic_is_no_data(monkeypatch):
    base = baseline(monkeypatch)
    quiet = healed(FIXTURE)
    quiet["system_overview"]["data"]["services"][0]["rps"] = 0.0
    for op in quiet["get_service_metrics"]["data"]["operations"]:
        op["rps"] = 0.0
    replay(monkeypatch, quiet)
    res = verify_recovery(None, action(), base, settle_seconds=120, dry_run=False, sleep=lambda s: None)
    assert res.status == NO_DATA


def test_dry_run_emits_verification_event(monkeypatch):
    base = baseline(monkeypatch)
    log = EventLog(echo=False)
    verify_recovery(None, action(), base, settle_seconds=120, dry_run=True, events=log)
    assert log.records[-1]["summary"] == "NOT_VERIFIED_DRY_RUN: dry run, nothing changed, recovery not claimed"
