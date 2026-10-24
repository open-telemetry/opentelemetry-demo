from src.models.action import ActionType, RemediationAction
from src.remediation import verifier
from src.remediation.verifier import (NO_DATA, NOT_RECOVERED, NOT_VERIFIED_DRY_RUN, RECOVERED,
                                      capture_baseline, verify_recovery)

SVC = "payment"


def install(monkeypatch, error_rate=0.0, p95=50.0, rps=5.0, flags=(), state="running", health="healthy",
            overview_status="ok", ops_status="ok", in_overview=True, docker_ok=True, ref_p95=None):
    def system_overview(ctx, window_minutes=5):
        if overview_status != "ok":
            return {"tool": "system_overview", "status": overview_status, "summary": "Prometheus unreachable",
                    "data": {}, "evidence": []}
        name = SVC if in_overview else "frontend"
        row = {"service": name, "rps": rps, "error_rate": error_rate, "p95_ms": p95, "flags": list(flags),
               "baseline_p95_ms": ref_p95}
        ev = [{"ref": f"metric:{name}:{k}", "kind": "metric", "value": row[k]}
              for k in ("error_rate", "p95_ms", "rps") if row[k] is not None]
        return {"tool": "system_overview", "status": "ok", "summary": "", "data": {"services": [row]},
                "evidence": ev}

    def get_service_metrics(ctx, service, window_minutes=10):
        if ops_status != "ok":
            return {"tool": "get_service_metrics", "status": ops_status, "summary": "no metrics",
                    "data": {}, "evidence": []}
        op = {"operation": "oteldemo.PaymentService/Charge", "kind": "server", "rps": rps,
              "error_rate": error_rate, "p95_ms": p95}
        ref = f"metric:{service}:server:{op['operation']}"
        return {"tool": "get_service_metrics", "status": "ok", "summary": "", "data": {"operations": [op]},
                "evidence": [{"ref": f"{ref}:error_rate", "kind": "metric", "value": error_rate},
                             {"ref": f"{ref}:p95_ms", "kind": "metric", "value": p95}]}

    def container_health(ctx, service=None):
        if not docker_ok:
            return {"tool": "container_health", "status": "source_unavailable", "summary": "Docker unavailable",
                    "data": {}, "evidence": []}
        row = {"name": service, "state": state, "restart_count": 0, "health": health}
        return {"tool": "container_health", "status": "ok", "summary": "", "data": {"containers": [row]},
                "evidence": [{"ref": f"container:{service}:state", "kind": "container", "value": state}]}

    monkeypatch.setattr(verifier, "system_overview", system_overview)
    monkeypatch.setattr(verifier, "get_service_metrics", get_service_metrics)
    monkeypatch.setattr(verifier, "container_health", container_health)


def action(dry_run=False):
    return RemediationAction(action_id="ACT-1", action_type=ActionType.RESTART_SERVICE, target_service=SVC,
                             description="Restart payment", dry_run=dry_run)


def incident_baseline(monkeypatch, **kw):
    params = {"error_rate": 0.4, "p95": 900.0, "rps": 5.0, "flags": ["error_rate_up"]}
    params.update(kw)
    install(monkeypatch, **params)
    return capture_baseline(None, SVC, window_minutes=5)


def test_baseline_uses_tool_values_and_evidence_refs(monkeypatch):
    base = incident_baseline(monkeypatch)
    assert (base["error_rate"], base["p95_ms"], base["rps"]) == (0.4, 900.0, 5.0)
    assert base["metric_source"] == "system_overview"
    assert base["container_state"] == "running"
    assert base["missing"] == {}
    refs = {e["ref"] for e in base["evidence"]}
    assert {"metric:payment:error_rate", "container:payment:state",
            "metric:payment:server:oteldemo.PaymentService/Charge:error_rate"} <= refs


def test_baseline_labels_missing_data_instead_of_inventing(monkeypatch):
    install(monkeypatch, overview_status="source_unavailable", ops_status="no_data", docker_ok=False)
    base = capture_baseline(None, SVC)
    assert base["error_rate"] is None and base["p95_ms"] is None and base["rps"] is None
    assert base["container_state"] is None
    assert set(base["missing"]) == {"error_rate", "p95_ms", "rps", "container_state"}
    assert base["evidence"] == []


def test_baseline_falls_back_to_operations_when_overview_omits_service(monkeypatch):
    install(monkeypatch, error_rate=0.1, in_overview=False)
    base = capture_baseline(None, SVC)
    assert base["metric_source"] == "get_service_metrics"
    assert base["error_rate"] == 0.1


def test_baseline_window_never_below_two_minutes(monkeypatch):
    install(monkeypatch)
    assert capture_baseline(None, SVC, window_minutes=1)["window_minutes"] == 2


def test_dry_run_never_claims_recovery(monkeypatch):
    base = incident_baseline(monkeypatch)
    install(monkeypatch, error_rate=0.0, p95=40.0)
    slept = []
    res = verify_recovery(None, action(dry_run=True), base, settle_seconds=120, dry_run=True, sleep=slept.append)
    assert res.status == NOT_VERIFIED_DRY_RUN
    assert res.recovered is False
    assert "dry run: nothing changed, recovery not claimed" in res.reasons
    assert slept == []


def test_recovered_when_after_metrics_improve(monkeypatch):
    base = incident_baseline(monkeypatch)
    install(monkeypatch, error_rate=0.002, p95=60.0)
    slept = []
    res = verify_recovery(None, action(), base, settle_seconds=180, dry_run=False, sleep=slept.append)
    assert res.status == RECOVERED and res.recovered is True
    assert slept == [180]
    assert res.after["window_minutes"] == 3
    assert any(e["phase"] == "after" and e["ref"] == "metric:payment:error_rate" for e in res.evidence)


def test_not_recovered_when_after_metrics_get_worse(monkeypatch):
    base = incident_baseline(monkeypatch)
    install(monkeypatch, error_rate=0.6, p95=1500.0, flags=["error_rate_up"])
    res = verify_recovery(None, action(), base, settle_seconds=120, dry_run=False, sleep=lambda s: None)
    assert res.status == NOT_RECOVERED and res.recovered is False
    assert any("error rate 0.4 -> 0.6" in r for r in res.reasons)


def test_not_recovered_when_container_not_running(monkeypatch):
    base = incident_baseline(monkeypatch)
    install(monkeypatch, error_rate=0.0, p95=40.0, state="exited")
    res = verify_recovery(None, action(), base, settle_seconds=120, dry_run=False, sleep=lambda s: None)
    assert res.status == NOT_RECOVERED and res.recovered is False


def test_latency_incident_must_improve_not_just_hold(monkeypatch):
    base = incident_baseline(monkeypatch, error_rate=0.0, p95=2000.0, flags=["latency_up"])
    install(monkeypatch, error_rate=0.0, p95=1950.0)
    res = verify_recovery(None, action(), base, settle_seconds=120, dry_run=False, sleep=lambda s: None)
    assert res.status == NOT_RECOVERED


def test_fast_failing_errors_recover_to_pre_incident_latency(monkeypatch):
    base = incident_baseline(monkeypatch, error_rate=0.9, p95=5.0, ref_p95=50.0)
    install(monkeypatch, error_rate=0.0, p95=55.0)
    res = verify_recovery(None, action(), base, settle_seconds=120, dry_run=False, sleep=lambda s: None)
    assert res.status == RECOVERED


def test_latency_regression_without_reference_is_not_recovered(monkeypatch):
    base = incident_baseline(monkeypatch, error_rate=0.9, p95=5.0)
    install(monkeypatch, error_rate=0.0, p95=55.0)
    res = verify_recovery(None, action(), base, settle_seconds=120, dry_run=False, sleep=lambda s: None)
    assert res.status == NOT_RECOVERED


def test_no_data_when_fresh_telemetry_missing(monkeypatch):
    base = incident_baseline(monkeypatch)
    install(monkeypatch, overview_status="source_unavailable", ops_status="source_unavailable")
    res = verify_recovery(None, action(), base, settle_seconds=120, dry_run=False, sleep=lambda s: None)
    assert res.status == NO_DATA and res.recovered is False


def test_no_data_when_no_traffic_after_action(monkeypatch):
    base = incident_baseline(monkeypatch)
    install(monkeypatch, error_rate=0.0, p95=None, rps=0.0)
    res = verify_recovery(None, action(), base, settle_seconds=120, dry_run=False, sleep=lambda s: None)
    assert res.status == NO_DATA and res.recovered is False


def test_short_settle_is_flagged_in_reasons(monkeypatch):
    base = incident_baseline(monkeypatch)
    install(monkeypatch, error_rate=0.0, p95=40.0)
    res = verify_recovery(None, action(), base, settle_seconds=30, dry_run=False, sleep=lambda s: None)
    assert any("pre-action samples may be included" in r for r in res.reasons)


def test_to_dict_shape(monkeypatch):
    base = incident_baseline(monkeypatch)
    res = verify_recovery(None, action(dry_run=True), base, settle_seconds=0, dry_run=True)
    assert set(res.to_dict()) == {"status", "recovered", "before", "after", "reasons", "evidence", "checked_at"}
