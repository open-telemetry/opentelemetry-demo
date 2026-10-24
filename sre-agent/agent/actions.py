"""Step 6 - ACT, only through the Action API, with three safety layers:

  1. allowlist  - only actions in config/runbook.yaml `allowlist` can run
  2. approval   - execute() refuses unless an approval record is passed (see approval.py)
  3. kill switch - if runs/KILL exists (python -m agent.main kill), NOTHING executes; checked before every call
Dry runs never call the API (read-only); they log exactly what WOULD be sent.
Every call / dry run / refusal is appended to runs/<id>/actions.jsonl and runs/action_log.jsonl.
"""
import json
import os
import re
import time

import requests
import yaml

from agent import config
from agent.runbook import RB

_API = None


class KillSwitchEngaged(RuntimeError):
    pass


def api_cfg() -> dict:
    global _API
    if _API is None:
        txt = (config.ROOT / "config" / "action_api.yaml").read_text(encoding="utf-8")
        txt = re.sub(r"\$\{(\w+)\}", lambda m: os.getenv(m.group(1), getattr(config, m.group(1), "")), txt)
        _API = yaml.safe_load(txt)
    return _API


def kill_engaged() -> bool:
    return config.KILL_FILE.exists()


def engage_kill(reason: str = "manual"):
    config.KILL_FILE.write_text(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "reason": reason}), encoding="utf-8")


def release_kill():
    config.KILL_FILE.unlink(missing_ok=True)


def _fill(obj, params):
    if isinstance(obj, dict):
        return {k: _fill(v, params) for k, v in obj.items()}
    if isinstance(obj, str):
        m = re.fullmatch(r"\{(\w+)\}", obj)
        if m:
            return params.get(m.group(1))
        return obj.format(**params)
    return obj


def build_request(action: str, params: dict) -> dict:
    spec = api_cfg()["actions"][action]
    return {"method": spec.get("method", "POST"), "url": api_cfg()["base_url"].rstrip("/") + _fill(spec["path"], params),
            "json": _fill(spec.get("body", {}), params)}


def _log(incident_dir, rec):
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **rec}
    for path in ([incident_dir / "actions.jsonl"] if incident_dir else []) + [config.RUNS / "action_log.jsonl"]:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=str) + "\n")
    return rec


def execute(action: str, params: dict, approval: dict = None, dry_run: bool = False, incident_dir=None) -> dict:
    base = {"action": action, "params": params, "dry_run": dry_run}
    if action not in RB["allowlist"] or action not in api_cfg()["actions"]:
        return _log(incident_dir, {**base, "result": "refused", "why": "not on allowlist"})
    req = build_request(action, params)
    if dry_run:
        return _log(incident_dir, {**base, "result": "dry_run", "would_send": req})
    if kill_engaged():
        _log(incident_dir, {**base, "result": "refused", "why": "kill switch engaged"})
        raise KillSwitchEngaged("kill switch engaged - no action executed")
    if not approval or approval.get("decision") != "approved":
        return _log(incident_dir, {**base, "result": "refused", "why": "no human approval"})
    if config.ACTION_API_MODE == "mock":
        return _log(incident_dir, {**base, "result": "ok", "mock": True, "request": req, "approval": approval})
    headers = {k: v for k, v in (api_cfg().get("headers") or {}).items() if v}
    if config.ACTION_API_TOKEN and "Authorization" not in headers:
        headers["Authorization"] = f"Bearer {config.ACTION_API_TOKEN}"
    try:
        # the approval record travels with the request: the Action API server refuses calls without it
        payload = {**req["json"], "approval": approval,
                   "incident_id": incident_dir.name if incident_dir else None}
        r = requests.request(req["method"], req["url"], json=payload, headers=headers, timeout=120)
        ok = r.status_code < 400
        return _log(incident_dir, {**base, "result": "ok" if ok else "failed", "status": r.status_code,
                                   "response": r.text[:500], "request": req, "approval": approval})
    except requests.RequestException as e:
        return _log(incident_dir, {**base, "result": "failed", "error": str(e)[:300], "request": req,
                                   "approval": approval})
