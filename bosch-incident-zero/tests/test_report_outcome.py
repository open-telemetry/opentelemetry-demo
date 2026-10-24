from src.agent.presenter import format_incident_brief
from src.agent.report import attach_action_outcome, build_report, render_report_markdown, validate_report
from src.agent.transcript import Transcript
from src.models.action import ActionType, ApprovalStatus, RemediationAction
from src.remediation.verifier import (NO_DATA, NOT_RECOVERED, NOT_VERIFIED_DRY_RUN, RECOVERED,
                                      VerificationResult)

TRACE = "abcdef0123456789abcdef0123456789"
AUDIT = "logs/audit.jsonl"


def transcript(escalate=False):
    t = Transcript(incident_id="INC-OUT-1", alert="checkout error rate high")
    t.diagnosis = {
        "root_cause": {"service": "payment", "category": "errors_on_operation", "summary": "Charge fails"},
        "severity": "HIGH", "impacted_services": ["checkout", "payment"],
        "evidence": [{"kind": "metric", "ref": "metric:payment:error_rate"}],
        "recommended_next_step": "Restart payment",
    }
    t.gate = {"escalate": escalate, "final_confidence": "low" if escalate else "high"}
    t.citations = [{"kind": "trace", "ref": TRACE, "valid": True},
                   {"kind": "metric", "ref": "metric:payment:error_rate", "valid": True}]
    t.tool_calls = [{"n": 1, "tool": "system_overview", "arguments": {}, "result": {
        "evidence": [{"ref": "metric:payment:error_rate", "kind": "metric", "value": 0.4}]}}]
    t.report = build_report(t)
    return t


def action(dry_run=False, approval=ApprovalStatus.APPROVED, executed=True):
    return RemediationAction(action_id="ACT-1", action_type=ActionType.RESTART_SERVICE, target_service="payment",
                             description="Restart payment", dry_run=dry_run, approval_status=approval,
                             approver="operator" if approval == ApprovalStatus.APPROVED else None,
                             executed_at="2026-10-24T05:00:00+00:00" if executed else None,
                             execution_result="accepted" if executed else None)


def verification(status):
    snap = {"service": "payment", "error_rate": 0.4, "p95_ms": 900.0, "rps": 5.0, "container_state": "running",
            "metric_source": "system_overview", "missing": {}}
    after = dict(snap, error_rate=0.0 if status == RECOVERED else 0.5)
    return VerificationResult(status=status, recovered=status == RECOVERED, before=snap, after=after,
                              reasons=[f"test {status}"],
                              evidence=[{"ref": "metric:payment:error_rate", "kind": "metric", "value": 0.0,
                                         "phase": "after"}])


TIMELINE = [{"at": "2026-10-24T04:59:00+00:00", "event": "alert", "detail": "checkout error rate high"},
            {"at": "2026-10-24T04:59:30+00:00", "event": "approval", "status": "APPROVED",
             "detail": {"approver": "operator"}}]


def test_existing_report_still_validates():
    t = transcript()
    ok, errors = validate_report(t.report)
    assert ok, errors
    assert t.report["root_cause_category"] == "errors_on_operation"


def test_recovered_outcome_is_resolved_and_validates():
    rep = attach_action_outcome(transcript().report, action(), verification(RECOVERED), TIMELINE, AUDIT)
    ok, errors = validate_report(rep)
    assert ok, errors
    assert rep["status"] == "RESOLVED"
    assert rep["action_taken"]["type"] == "RESTART_SERVICE"
    assert rep["action_taken"]["approval_status"] == "APPROVED"
    assert rep["action_taken"]["approver"] == "operator"
    assert rep["action_taken"]["rollback"] is None
    assert rep["remediation"]["recovery_verified"] is True
    assert rep["timeline"][1]["detail"] == {"approver": "operator"}
    assert rep["audit_log"] == AUDIT
    assert rep["prevention"]["category"] == "errors_on_operation"
    assert all("payment" in r or "release" in r for r in rep["prevention"]["recommendations"])


def test_dry_run_is_never_resolved():
    rep = attach_action_outcome(transcript().report, action(dry_run=True), verification(NOT_VERIFIED_DRY_RUN),
                                TIMELINE, AUDIT)
    ok, errors = validate_report(rep)
    assert ok, errors
    assert rep["status"] == "MITIGATION_UNVERIFIED"
    assert rep["remediation"]["dry_run"] is True
    assert rep["remediation"]["recovery_verified"] is False


def test_failed_and_no_data_outcomes():
    failed = attach_action_outcome(transcript().report, action(), verification(NOT_RECOVERED), TIMELINE, AUDIT)
    assert failed["status"] == "MITIGATION_FAILED"
    nodata = attach_action_outcome(transcript().report, action(), verification(NO_DATA), TIMELINE, AUDIT)
    assert nodata["status"] == "UNVERIFIED_ESCALATED"
    assert validate_report(failed)[0] and validate_report(nodata)[0]


def test_no_action_report_validates_and_escalates():
    rep = attach_action_outcome(transcript(escalate=True).report, None, None, TIMELINE[:1], AUDIT)
    ok, errors = validate_report(rep)
    assert ok, errors
    assert rep["action_taken"] is None
    assert rep["verification"] is None
    assert rep["status"] == "ESCALATED"


def test_rejected_action_is_escalated():
    rep = attach_action_outcome(transcript().report, action(approval=ApprovalStatus.REJECTED, executed=False),
                                None, TIMELINE, AUDIT)
    assert validate_report(rep)[0]
    assert rep["status"] == "ESCALATED"
    assert rep["remediation"]["approval_status"] == "REJECTED"


def test_schema_rejects_resolved_without_recovery():
    rep = attach_action_outcome(transcript().report, action(), verification(NOT_RECOVERED), TIMELINE, AUDIT)
    rep["status"] = "RESOLVED"
    assert not validate_report(rep)[0]


def test_presenter_labels_dry_run_and_not_verified():
    t = transcript()
    t.report = attach_action_outcome(t.report, action(dry_run=True), verification(NOT_VERIFIED_DRY_RUN),
                                     TIMELINE, AUDIT)
    brief = format_incident_brief(t, action=action(dry_run=True))
    assert "DRY RUN" in brief
    assert "NOT VERIFIED" in brief
    assert "ACTION LOG / TIMELINE" in brief
    assert "RECOVERY VERIFICATION (BEFORE / AFTER)" in brief
    assert "approval [APPROVED]" in brief
    assert AUDIT in brief


def test_presenter_labels_escalated_and_failed():
    t = transcript()
    ver = verification(NOT_RECOVERED)
    t.report = attach_action_outcome(t.report, action(), ver, TIMELINE, AUDIT)
    brief = format_incident_brief(t, action=action(), verification=ver, timeline=TIMELINE)
    assert "ESCALATED TO HUMAN" in brief
    assert "NOT RECOVERED" in brief
    assert "Recovery Status   : NOT_RECOVERED" in brief


def test_markdown_renders_resolved_outcome():
    md = render_report_markdown(attach_action_outcome(transcript().report, action(), verification(RECOVERED),
                                                      TIMELINE, AUDIT))
    assert "# Incident INC-OUT-1" in md
    assert "**Status:** RESOLVED" in md
    assert "DRY RUN" not in md
    assert "RESTART_SERVICE on payment" in md
    assert "| Error rate | 0.4 | 0 |" in md
    assert f"trace `{TRACE}`" in md
    assert "## Timeline" in md and "## Prevention" in md
    assert AUDIT in md


def test_markdown_labels_dry_run_and_escalation():
    dry = render_report_markdown(attach_action_outcome(transcript().report, action(dry_run=True),
                                                       verification(NOT_VERIFIED_DRY_RUN), TIMELINE, AUDIT))
    assert "DRY RUN - nothing was changed" in dry
    assert "Recovery NOT verified" in dry
    esc = render_report_markdown(attach_action_outcome(transcript(escalate=True).report, None, None, [], AUDIT))
    assert "**Status:** ESCALATED" in esc
    assert "No action taken." in esc
    assert "Not verified - no verification was run." in esc


def test_markdown_handles_plain_diagnosis_report():
    md = render_report_markdown(transcript().report)
    assert "**Status:** DIAGNOSED" in md
    assert "## Timeline" not in md and "## Recovery verification" not in md


def test_presenter_without_outcome_is_unchanged_for_old_callers():
    t = transcript(escalate=True)
    brief = format_incident_brief(t)
    assert "ESCALATED TO HUMAN" in brief
    assert "ACTION LOG / TIMELINE" not in brief
    assert "RECOVERY VERIFICATION" not in brief


def test_write_report_files_emits_event_and_scrubs_secrets(tmp_path):
    from src.agent.report import write_report_files
    from src.events import EventLog

    rep = attach_action_outcome(transcript().report, action(), verification(RECOVERED), TIMELINE, AUDIT)
    rep["action_taken"]["parameters"] = {"api_key": "sk-or-v1-abcdefghijklmnopqrstuvwxyz"}
    log = EventLog(echo=False)
    paths = write_report_files(rep, tmp_path, events=log)
    for p in paths.values():
        text = open(p).read()
        assert "sk-or-v1-abcdefghijklmnop" not in text
    assert paths["json"].endswith("INC-OUT-1/report.json") and paths["md"].endswith("report.md")
    assert [r["event"] for r in log.records] == ["REPORT_WRITTEN"]
    assert log.records[0]["data"] == paths


def test_rollback_and_event_log_are_shown():
    from src.events import EventLog

    act = action()
    act.rollback = RemediationAction(action_id="ACT-1-RB", action_type=ActionType.RESTART_SERVICE,
                                     target_service="payment", description="Roll back payment restart",
                                     executed_at="2026-10-24T05:03:00+00:00")
    rep = attach_action_outcome(transcript().report, act, verification(NOT_RECOVERED), TIMELINE, AUDIT)
    assert validate_report(rep)[0]
    assert rep["action_taken"]["rollback"]["ran"] is True
    assert rep["action_taken"]["rollback"]["action_id"] == "ACT-1-RB"
    t = transcript()
    t.report = rep
    log = EventLog(echo=False, incident_id="INC-OUT-1")
    log.emit("VERIFICATION", "NOT_RECOVERED: error_rate 0.40 -> 0.50", {"status": NOT_RECOVERED})
    brief = format_incident_brief(t, action=act, events=log)
    assert "EVENT LOG (last 1 of 1)" in brief
    assert "NOT_RECOVERED: error_rate 0.40 -> 0.50" in brief


def test_escalated_report_without_traces_validates_but_diagnosed_does_not():
    rep = attach_action_outcome(transcript(escalate=True).report, None, None, [], AUDIT)
    rep["evidence"]["trace_ids"] = []
    for status in ("ESCALATED", "DETECTED", "UNVERIFIED_ESCALATED"):
        ok, errors = validate_report(dict(rep, status=status))
        assert ok, errors
    assert not validate_report(dict(rep, status="DIAGNOSED"))[0]


def test_timeline_reads_event_record_ts_and_summary():
    t = transcript()
    rec = {"ts": "2026-10-24T05:00:08.782+00:00", "event": "PLAN", "summary": "no action: escalated", "data": {}}
    t.report = attach_action_outcome(t.report, None, None, [rec], AUDIT)
    brief = format_incident_brief(t)
    assert "2026-10-24T05:00:08.782+00:00" in brief and "no action: escalated" in brief
    md = render_report_markdown(t.report)
    assert "| 2026-10-24T05:00:08.782+00:00 | PLAN |" in md
