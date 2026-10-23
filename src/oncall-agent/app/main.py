from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from app.approval import ApprovalStore, IncidentState, approval_store
from app.config import DATA_DIR
from app.detector import Detector, Alert, detector
from app.evidence import EvidenceLedger
from app.executor import dry_run_action, execute_action, rollback_action, verify_recovery, ONCALL_SETTLE_S
from app.investigator import Investigator, investigator
from app.proposer import Proposer, proposer
from app.reporter import write_report
from app.validator import validate_diagnosis

logger = logging.getLogger("oncall-agent.main")

EVAL_AUTO_APPROVE = os.environ.get("EVAL_AUTO_APPROVE", "false").lower() == "true"
ONCALL_POLL_INTERVAL_S = int(os.environ.get("ONCALL_POLL_INTERVAL_S", 30))
ONCALL_CONFIDENCE_THRESHOLD = float(os.environ.get("ONCALL_CONFIDENCE_THRESHOLD", 0.70))

KILLSWITCH_FILE = DATA_DIR / "killswitch.json"


def _killswitch_engaged() -> bool:
    try:
        import json
        if KILLSWITCH_FILE.exists():
            return json.loads(KILLSWITCH_FILE.read_text()).get("engaged", False)
    except Exception:
        pass
    return False


def _set_killswitch(engaged: bool) -> None:
    import json
    KILLSWITCH_FILE.parent.mkdir(parents=True, exist_ok=True)
    KILLSWITCH_FILE.write_text(json.dumps({"engaged": engaged}))


def _run_incident_pipeline(alert: Alert, auto_approve: bool = False) -> None:
    """Background thread: investigate → diagnose → propose → optionally execute."""
    inc_id = alert.incident_id
    store = approval_store

    # Create incident record
    rec = store.create(
        incident_id=inc_id,
        fingerprint=alert.fingerprint,
        symptoms=[s.model_dump() for s in alert.symptoms],
    )

    store.transition(rec, IncidentState.INVESTIGATING, "Starting LLM investigation")

    # Investigate
    ledger = EvidenceLedger(inc_id)
    try:
        inv_result = investigator.investigate(alert, ledger=ledger)
    except Exception as e:
        logger.error("Investigation failed for %s: %s", inc_id, e)
        rec = store.get(inc_id) or rec
        rec.escalation = {"reason": f"Investigation error: {e}", "findings": ""}
        store.transition(rec, IncidentState.ESCALATED, f"Investigation exception: {e}")
        write_report(rec)
        return

    diag = inv_result.diagnosis
    val = inv_result.validation
    rec = store.get(inc_id) or rec
    rec.diagnosis = diag
    rec.validation = val.model_dump() if val else {}
    store.transition(rec, IncidentState.DIAGNOSED, f"Diagnosis: {diag.get('component')} / {diag.get('cause_category')} @ conf={getattr(val, 'calibrated_confidence', 0)}")

    # Escalate if confidence too low or category unknown
    if getattr(val, "escalate_required", False):
        rec = store.get(inc_id) or rec
        rec.escalation = {
            "reason": getattr(val, "reason", "Low confidence"),
            "findings": str(diag),
        }
        store.transition(rec, IncidentState.ESCALATED, "Confidence too low — escalating")
        write_report(rec, diag, val.model_dump() if val else {})
        return

    # Propose
    try:
        proposals = proposer.propose(diag, inc_id)
    except Exception as e:
        proposals = []
        logger.error("Proposer failed for %s: %s", inc_id, e)

    if not proposals:
        rec = store.get(inc_id) or rec
        rec.escalation = {
            "reason": "No matching runbook found for diagnosis",
            "findings": str(diag),
        }
        store.transition(rec, IncidentState.ESCALATED, "No runbook match — escalating")
        write_report(rec, diag, val.model_dump() if val else {})
        return

    rec = store.get(inc_id) or rec
    rec.proposals = [p.model_dump() for p in proposals]
    store.transition(rec, IncidentState.AWAITING_APPROVAL, f"Proposed {len(proposals)} action(s). Awaiting human approval.")

    if auto_approve:
        logger.warning("EVAL_AUTO_APPROVE=true for incident %s — auto-approving without human consent!", inc_id)
        _execute_approved(inc_id, auto_approve=True)


def _execute_approved(incident_id: str, auto_approve: bool = False) -> None:
    """Execute the approved proposal, verify, and rollback on failure."""
    store = approval_store
    rec = store.get(incident_id)
    if not rec:
        return

    proposals = rec.proposals
    if not proposals:
        return

    proposal = proposals[0]
    component = (rec.diagnosis or {}).get("component", "unknown")

    # Mint approval token
    token = store.mint_approval_token(
        incident_id=incident_id,
        action=proposal["action"],
        params=proposal["params"],
    )
    rec = store.get(incident_id) or rec
    rec.approval_token = token
    store.update(rec)

    store.transition(rec, IncidentState.EXECUTING, f"Executing {proposal['action']} on {proposal['params']}")

    # Dry run first
    dry_result = dry_run_action(incident_id, proposal["action"], proposal["params"], token)
    logger.info("Dry run result for %s: %s", incident_id, dry_result)

    # Execute live
    exec_result = execute_action(incident_id, proposal["action"], proposal["params"], token)
    action_id = exec_result.get("action_id")

    rec = store.get(incident_id) or rec
    auto_approve_note = "AUTO_APPROVED via EVAL_AUTO_APPROVE=true — NOT for production use" if auto_approve else ""
    rec.execution_results.append({
        "action": proposal["action"],
        "params": proposal["params"],
        "dry_run_result": dry_result,
        "result": exec_result,
        "action_id": action_id,
        "auto_approve_note": auto_approve_note,
    })
    store.transition(rec, IncidentState.VERIFYING, f"Action executed (id={action_id}). Verifying recovery...")

    # Verify recovery
    verification = verify_recovery(component, settle_s=ONCALL_SETTLE_S)
    rec = store.get(incident_id) or rec
    rec.verification = verification
    store.update(rec)

    if verification.get("passed"):
        store.transition(rec, IncidentState.RESOLVED, "Recovery verified — incident resolved")
        detector.mark_resolved(rec.fingerprint)
    else:
        logger.warning("Recovery verification FAILED for %s — rolling back", incident_id)
        if action_id and proposal.get("rollback_plan") == "rollback":
            rb_result = rollback_action(incident_id, action_id, token)
            rec = store.get(incident_id) or rec
            rec.execution_results.append({"action": "rollback", "result": rb_result})
            store.update(rec)

        rec = store.get(incident_id) or rec
        rec.escalation = {
            "reason": "Recovery verification failed after action execution",
            "findings": str(verification),
        }
        store.transition(rec, IncidentState.ROLLED_BACK, "Rollback executed. Escalating.")

    # Write report
    rec = store.get(incident_id) or rec
    diag = rec.diagnosis or {}
    val_data = rec.validation or {}
    json_path, md_path = write_report(rec, diag, val_data)
    rec = store.get(incident_id) or rec
    rec.report_path = str(json_path)
    store.update(rec)


def _detector_loop() -> None:
    """Background detector loop."""
    logger.info("Detector loop started (poll interval: %ds)", ONCALL_POLL_INTERVAL_S)
    while True:
        try:
            alert = detector.evaluate_once()
            if alert:
                logger.info("Alert fired: %s (%d symptoms)", alert.incident_id, len(alert.symptoms))
                t = threading.Thread(
                    target=_run_incident_pipeline,
                    args=(alert, EVAL_AUTO_APPROVE),
                    daemon=True,
                )
                t.start()
        except Exception as e:
            logger.error("Detector loop error: %s", e)
        time.sleep(ONCALL_POLL_INTERVAL_S)


# ── FastAPI app ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    t = threading.Thread(target=_detector_loop, daemon=True)
    t.start()
    yield


app = FastAPI(title="AI On-Call Engineer", lifespan=lifespan)

STATIC_DIR = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", include_in_schema=False)
def root():
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/health")
def health():
    return {"status": "ok", "service": "oncall-agent"}


# ── Kill switch ───────────────────────────────────────────────────────────────

class KillSwitchBody(BaseModel):
    engaged: bool


@app.get("/killswitch")
def get_killswitch():
    return {"engaged": _killswitch_engaged()}


@app.post("/killswitch")
def set_killswitch(body: KillSwitchBody):
    _set_killswitch(body.engaged)
    logger.warning("Kill switch set to engaged=%s", body.engaged)
    return {"engaged": body.engaged}


# ── Incidents ─────────────────────────────────────────────────────────────────

@app.get("/incidents")
def list_incidents():
    records = approval_store.list_all()
    return [r.model_dump() for r in records]


@app.get("/incidents/{incident_id}")
def get_incident(incident_id: str):
    rec = approval_store.get(incident_id)
    if not rec:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return rec.model_dump()


class ApproveBody(BaseModel):
    approved_by: str = "dashboard-user"


class RejectBody(BaseModel):
    reason: str = ""


@app.post("/incidents/{incident_id}/dry-run")
def incident_dry_run(incident_id: str):
    rec = approval_store.get(incident_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Incident not found")
    if not rec.proposals:
        raise HTTPException(status_code=400, detail="No proposals to dry-run")

    proposal = rec.proposals[0]
    token = approval_store.mint_approval_token(
        incident_id=incident_id,
        action=proposal["action"],
        params=proposal["params"],
    )
    result = dry_run_action(incident_id, proposal["action"], proposal["params"], token)
    return {"dry_run_result": result, "proposal": proposal}


@app.post("/incidents/{incident_id}/approve")
def approve_incident(incident_id: str, body: ApproveBody):
    rec = approval_store.get(incident_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Incident not found")
    if rec.state != IncidentState.AWAITING_APPROVAL:
        raise HTTPException(status_code=400, detail=f"Incident is in state {rec.state}, not AWAITING_APPROVAL")
    if not rec.proposals:
        raise HTTPException(status_code=400, detail="No proposals to approve")

    rec.approved_by = body.approved_by
    from datetime import datetime, timezone
    rec.approved_at = datetime.now(timezone.utc).isoformat()
    approval_store.transition(rec, IncidentState.APPROVED, f"Approved by {body.approved_by}")

    # Execute in background
    t = threading.Thread(target=_execute_approved, args=(incident_id,), daemon=True)
    t.start()

    return {"status": "approved", "detail": f"Incident {incident_id} approved by {body.approved_by}. Execution started."}


@app.post("/incidents/{incident_id}/reject")
def reject_incident(incident_id: str, body: RejectBody):
    rec = approval_store.get(incident_id)
    if not rec:
        raise HTTPException(status_code=404, detail="Incident not found")
    if rec.state != IncidentState.AWAITING_APPROVAL:
        raise HTTPException(status_code=400, detail=f"Incident is in state {rec.state}, not AWAITING_APPROVAL")

    rec.rejection_reason = body.reason or "No reason provided"
    approval_store.transition(rec, IncidentState.REJECTED, f"Rejected: {rec.rejection_reason}")
    write_report(rec, rec.diagnosis, rec.validation)
    return {"status": "rejected", "detail": f"Incident {incident_id} rejected."}


# ── Manual investigation trigger (eval harness) ───────────────────────────────

class InvestigateBody(BaseModel):
    symptoms: list[dict[str, Any]] | None = None
    auto_approve: bool = False


@app.post("/incidents/investigate")
def manual_investigate(body: InvestigateBody):
    """Manually trigger a detection + investigation cycle (eval harness)."""
    det = Detector()
    det._consecutive_error_polls = {}
    alert = det.evaluate_once(force_single_poll_trigger=True)
    if not alert:
        return {"status": "no_alert", "detail": "No anomalies detected on current telemetry"}

    auto = body.auto_approve or EVAL_AUTO_APPROVE
    t = threading.Thread(target=_run_incident_pipeline, args=(alert, auto), daemon=True)
    t.start()
    return {"status": "started", "incident_id": alert.incident_id, "symptoms": len(alert.symptoms)}
