import os
import time
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.allowlist import (
    get_action_service,
    is_flag_allowed,
    is_service_restart_allowed,
    is_throttle_allowed,
)
from app.audit import audit_logger, killswitch
from app.docker_ops import docker_manager
from app.flags import rollback_flag, set_flag
from app.throttle import rollback_throttle, throttle_load_generator
from app.token_auth import verify_approval_token

ACTION_API_SECRET = os.environ.get("ACTION_API_SECRET", "change-me-locally")

app = FastAPI(title="Action API", version="1.0.0")

_service_last_action_time: dict[str, float] = {}


class KillSwitchRequest(BaseModel):
    engaged: bool


class ActionRequest(BaseModel):
    action: str
    params: dict[str, Any] = Field(default_factory=dict)
    incident_id: str = "manual"
    approval_token: str | None = None
    dry_run: bool = False
    exp: int | None = None


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "action-api"}


@app.get("/containers")
def list_containers() -> list[dict[str, Any]]:
    return docker_manager.get_containers()


@app.get("/containers/{name}")
def get_container(name: str) -> dict[str, Any]:
    c = docker_manager.get_container(name)
    if not c:
        raise HTTPException(status_code=404, detail=f"Container '{name}' not found")
    return c


@app.get("/events")
def get_events(since_minutes: int = Query(default=60, ge=1, le=1440)) -> dict[str, Any]:
    events = docker_manager.get_events(since_minutes=since_minutes)
    return {
        "events": events,
        "since_minutes": since_minutes,
        "count": len(events),
    }


@app.get("/killswitch")
def get_killswitch() -> dict[str, bool]:
    return {"engaged": killswitch.is_engaged()}


@app.post("/killswitch")
def set_killswitch(req: KillSwitchRequest, request: Request) -> dict[str, bool]:
    engaged = killswitch.set_engaged(req.engaged)
    caller = request.client.host if request.client else "unknown"
    audit_logger.log_action(
        incident_id="system",
        action="killswitch",
        params={"engaged": engaged},
        dry_run=False,
        status="engaged" if engaged else "disengaged",
        detail=f"Killswitch set to {engaged}",
        caller=caller,
    )
    return {"engaged": engaged}


@app.get("/audit")
def get_audit(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, Any]:
    records = audit_logger.get_audit_records(limit=limit)
    return {
        "records": records,
        "count": len(records),
    }


@app.post("/actions")
def execute_action(req: ActionRequest, request: Request) -> dict[str, Any]:
    caller = request.client.host if request.client else "unknown"

    if killswitch.is_engaged() and not req.dry_run:
        audit_logger.log_action(
            incident_id=req.incident_id,
            action=req.action,
            params=req.params,
            dry_run=req.dry_run,
            status="locked",
            detail="Kill switch is engaged. All mutating actions are locked.",
            caller=caller,
        )
        raise HTTPException(
            status_code=423,
            detail="Kill switch is engaged. All mutating actions are locked.",
        )

    action = req.action
    params = req.params

    if action == "scale_service":
        audit_logger.log_action(
            incident_id=req.incident_id,
            action=action,
            params=params,
            dry_run=req.dry_run,
            status="unsupported",
            detail="Kubernetes only; this deployment is Docker Compose",
            caller=caller,
        )
        return {"status": "unsupported", "reason": "Kubernetes only; this deployment is Docker Compose"}

    if action == "restart_service":
        service = str(params.get("service", ""))
        ok, reason = is_service_restart_allowed(service)
        if not ok:
            audit_logger.log_action(
                incident_id=req.incident_id,
                action=action,
                params=params,
                dry_run=req.dry_run,
                status="rejected",
                detail=reason,
                caller=caller,
            )
            raise HTTPException(status_code=400, detail=reason)

    elif action == "set_feature_flag":
        flag = str(params.get("flag", ""))
        variant = str(params.get("variant", ""))
        ok, reason = is_flag_allowed(flag, variant)
        if not ok:
            audit_logger.log_action(
                incident_id=req.incident_id,
                action=action,
                params=params,
                dry_run=req.dry_run,
                status="rejected",
                detail=reason,
                caller=caller,
            )
            raise HTTPException(status_code=400, detail=reason)

    elif action == "throttle_load_generator":
        users = params.get("users")
        spawn_rate = params.get("spawn_rate", 1.0)
        ok, reason = is_throttle_allowed(users, spawn_rate)
        if not ok:
            audit_logger.log_action(
                incident_id=req.incident_id,
                action=action,
                params=params,
                dry_run=req.dry_run,
                status="rejected",
                detail=reason,
                caller=caller,
            )
            raise HTTPException(status_code=400, detail=reason)

    elif action == "rollback":
        target_action_id = str(params.get("action_id", ""))
        if not target_action_id:
            reason = "Missing action_id parameter for rollback"
            audit_logger.log_action(
                incident_id=req.incident_id,
                action=action,
                params=params,
                dry_run=req.dry_run,
                status="rejected",
                detail=reason,
                caller=caller,
            )
            raise HTTPException(status_code=400, detail=reason)
    else:
        reason = f"Unknown action '{action}'"
        audit_logger.log_action(
            incident_id=req.incident_id,
            action=action,
            params=params,
            dry_run=req.dry_run,
            status="rejected",
            detail=reason,
            caller=caller,
        )
        raise HTTPException(status_code=400, detail=reason)

    if req.dry_run:
        summary = ""
        if action == "restart_service":
            svc = str(params.get("service"))
            c = docker_manager.get_container(svc)
            c_status = c.get("status", "unknown") if c else "unknown"
            summary = f"Would restart service '{svc}', currently {c_status}"
        elif action == "set_feature_flag":
            summary = f"Would set flag '{params.get('flag')}' to '{params.get('variant')}' via flagd-ui"
        elif action == "throttle_load_generator":
            summary = f"Would throttle load generator to {params.get('users')} users at spawn rate {params.get('spawn_rate', 1.0)}"
        elif action == "rollback":
            target_aid = str(params.get("action_id"))
            target_rec = audit_logger.get_action_by_id(target_aid)
            if not target_rec:
                raise HTTPException(status_code=404, detail=f"Target action ID '{target_aid}' not found for rollback")
            if target_rec.get("action") == "restart_service":
                return {"status": "not_reversible", "detail": "restart_service is not reversible"}
            summary = f"Would rollback action '{target_aid}' ({target_rec.get('action')})"

        aid = audit_logger.log_action(
            incident_id=req.incident_id,
            action=action,
            params=params,
            dry_run=True,
            status="dry_run",
            detail=summary,
            caller=caller,
        )
        return {
            "dry_run": True,
            "status": "would_apply",
            "action": action,
            "params": params,
            "summary": summary,
            "action_id": aid,
        }

    token_ok, token_reason = verify_approval_token(
        secret=ACTION_API_SECRET,
        token=req.approval_token,
        incident_id=req.incident_id,
        action=action,
        params=params,
        exp_override=req.exp,
    )
    if not token_ok:
        audit_logger.log_action(
            incident_id=req.incident_id,
            action=action,
            params=params,
            dry_run=False,
            status="rejected",
            detail=token_reason,
            caller=caller,
        )
        raise HTTPException(status_code=403, detail=f"Invalid or expired approval token: {token_reason}")

    target_service = get_action_service(action, params)
    if action == "rollback":
        target_aid = str(params.get("action_id"))
        target_rec = audit_logger.get_action_by_id(target_aid)
        if not target_rec:
            raise HTTPException(status_code=404, detail=f"Target action ID '{target_aid}' not found for rollback")
        target_act = target_rec.get("action")
        if target_act == "restart_service":
            audit_logger.log_action(
                incident_id=req.incident_id,
                action=action,
                params=params,
                dry_run=False,
                status="not_reversible",
                detail="restart_service is not reversible",
                caller=caller,
            )
            return {"status": "not_reversible", "detail": "restart_service is not reversible"}
        target_service = get_action_service(target_act, target_rec.get("params", {}))

    now = time.time()
    last_action_ts = _service_last_action_time.get(target_service, 0.0)
    if (now - last_action_ts) < 60.0:
        elapsed = int(now - last_action_ts)
        reason = f"Rate limit exceeded: max 1 action per service per 60s for service '{target_service}' ({elapsed}s since last action)"
        audit_logger.log_action(
            incident_id=req.incident_id,
            action=action,
            params=params,
            dry_run=False,
            status="rate_limited",
            detail=reason,
            caller=caller,
        )
        raise HTTPException(status_code=429, detail=reason)

    if action == "restart_service":
        svc = str(params.get("service"))
        success, msg = docker_manager.restart_container(svc)
        if not success:
            audit_logger.log_action(
                incident_id=req.incident_id,
                action=action,
                params=params,
                dry_run=False,
                status="failed",
                detail=msg,
                caller=caller,
            )
            raise HTTPException(status_code=500, detail=msg)

        _service_last_action_time[target_service] = now
        aid = audit_logger.log_action(
            incident_id=req.incident_id,
            action=action,
            params=params,
            dry_run=False,
            status="applied",
            detail=f"Restarted service {svc}",
            caller=caller,
        )
        return {
            "status": "applied",
            "action_id": aid,
            "action": action,
            "service": svc,
        }

    elif action == "set_feature_flag":
        flag = str(params.get("flag"))
        variant = str(params.get("variant"))
        success, msg, prev_state = set_flag(flag, variant)
        if not success:
            audit_logger.log_action(
                incident_id=req.incident_id,
                action=action,
                params=params,
                dry_run=False,
                status="failed",
                detail=msg,
                caller=caller,
            )
            raise HTTPException(status_code=500, detail=msg)

        _service_last_action_time[target_service] = now
        aid = audit_logger.log_action(
            incident_id=req.incident_id,
            action=action,
            params=params,
            dry_run=False,
            status="applied",
            detail=f"Flag {flag} set to {variant}",
            caller=caller,
            previous_state=prev_state,
        )
        return {
            "status": "applied",
            "action_id": aid,
            "action": action,
            "flag": flag,
            "variant": variant,
        }

    elif action == "throttle_load_generator":
        users = int(params.get("users", 1))
        spawn_rate = float(params.get("spawn_rate", 1.0))
        success, msg, prev_state = throttle_load_generator(users, spawn_rate)
        if not success:
            audit_logger.log_action(
                incident_id=req.incident_id,
                action=action,
                params=params,
                dry_run=False,
                status="failed",
                detail=msg,
                caller=caller,
            )
            raise HTTPException(status_code=500, detail=msg)

        _service_last_action_time[target_service] = now
        aid = audit_logger.log_action(
            incident_id=req.incident_id,
            action=action,
            params=params,
            dry_run=False,
            status="applied",
            detail=f"Throttled load generator to {users} users",
            caller=caller,
            previous_state=prev_state,
        )
        return {
            "status": "applied",
            "action_id": aid,
            "action": action,
            "users": users,
            "spawn_rate": spawn_rate,
        }

    elif action == "rollback":
        target_aid = str(params.get("action_id"))
        target_rec = audit_logger.get_action_by_id(target_aid)
        if not target_rec:
            raise HTTPException(status_code=404, detail=f"Target action ID '{target_aid}' not found for rollback")

        target_act = target_rec.get("action")
        if target_act == "restart_service":
            audit_logger.log_action(
                incident_id=req.incident_id,
                action=action,
                params=params,
                dry_run=False,
                status="not_reversible",
                detail="restart_service is not reversible",
                caller=caller,
            )
            return {"status": "not_reversible", "detail": "restart_service is not reversible"}

        if target_act == "set_feature_flag":
            prev_state = target_rec.get("previous_state")
            if not prev_state:
                raise HTTPException(status_code=400, detail="No previous state recorded for flag action")
            success, msg = rollback_flag(prev_state)
            if not success:
                audit_logger.log_action(
                    incident_id=req.incident_id,
                    action=action,
                    params=params,
                    dry_run=False,
                    status="failed",
                    detail=msg,
                    caller=caller,
                )
                raise HTTPException(status_code=500, detail=msg)

            _service_last_action_time[target_service] = now
            aid = audit_logger.log_action(
                incident_id=req.incident_id,
                action=action,
                params=params,
                dry_run=False,
                status="rolled_back",
                detail=f"Rolled back flag {prev_state.get('flag')}",
                caller=caller,
            )
            return {
                "status": "rolled_back",
                "action_id": aid,
                "target_action_id": target_aid,
                "action": "set_feature_flag",
                "flag": prev_state.get("flag"),
            }

        if target_act == "throttle_load_generator":
            prev_state = target_rec.get("previous_state")
            if not prev_state:
                raise HTTPException(status_code=400, detail="No previous state recorded for load generator action")
            success, msg = rollback_throttle(prev_state)
            if not success:
                audit_logger.log_action(
                    incident_id=req.incident_id,
                    action=action,
                    params=params,
                    dry_run=False,
                    status="failed",
                    detail=msg,
                    caller=caller,
                )
                raise HTTPException(status_code=500, detail=msg)

            _service_last_action_time[target_service] = now
            aid = audit_logger.log_action(
                incident_id=req.incident_id,
                action=action,
                params=params,
                dry_run=False,
                status="rolled_back",
                detail=f"Rolled back load generator to {prev_state.get('users')} users",
                caller=caller,
            )
            return {
                "status": "rolled_back",
                "action_id": aid,
                "target_action_id": target_aid,
                "action": "throttle_load_generator",
                "users": prev_state.get("users"),
            }

        raise HTTPException(status_code=400, detail=f"Action '{target_act}' is not reversible")

    raise HTTPException(status_code=400, detail=f"Unhandled action '{action}'")
