"""Action API - the ONLY component that changes the running demo.

The agent never touches Docker / flagd / Locust itself. After a human approves a plan, the agent sends
one HTTP request here, and this server performs exactly one allowlisted runbook action:

  POST /actions/restart  {"service": "payment"}                 -> docker restart <container> (also starts a
                                                                   stopped one, unpauses a paused one)
  POST /actions/flag     {"flag": "paymentFailure", "variant": "off"}
                                                                -> set the flag's defaultVariant through the
                                                                   flagd-ui API (keeps UI + file + flagd in
                                                                   sync); direct file edit if flagd-ui is off
  POST /actions/load     {"users": 2}                           -> Locust /swarm: change load-generator users
  POST /actions/scale    {"service": "ad", "replicas": 2}       -> kubectl scale (Kubernetes only)
  GET  /                 health + which backends are reachable
  GET  /actions/log      last 200 executed / refused calls

Safety, enforced HERE as well as in the agent (defence in depth):
  * every POST must carry an approval record {"approval": {"decision": "approved", "by": "<human>"}}
  * kill switch: if runs/KILL exists every POST is refused (423)
  * only allowlisted actions; restart refuses observability/infra tooling (runbook.yaml never_restart)
    and unknown containers; at most RESTART_LIMIT restarts of one service per 10 minutes
  * optional bearer token (ACTION_API_TOKEN)
  * every call, accepted or refused, is appended to runs/action_api_server.jsonl

This server is used ONLY to act after approval. It never returns flag values to the caller, so it cannot
be used to diagnose from flag settings.

Run:  python -m action_api.server            (listens on 127.0.0.1:8000, see env vars below)
Env:  ACTION_API_PORT=8000  ACTION_API_TOKEN=  PLATFORM=docker|kubernetes  K8S_NAMESPACE=otel-demo
      FLAGD_FILE=<path to demo.flagd.json>   (auto-discovered from the flagd container's mount if unset)
      OTEL_DEMO_DIR=<path to opentelemetry-demo checkout>   (2nd way to find the flag file)
      FLAGD_UI_URL=http://localhost:8080/feature            (preferred way to change flags)
      LOADGEN_URL=http://localhost:8080/loadgen             (Locust web UI behind the frontend proxy)
"""
import json
import os
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
RUNS.mkdir(exist_ok=True)
LOG_FILE = RUNS / "action_api_server.jsonl"
KILL_FILE = RUNS / "KILL"

RB = yaml.safe_load((ROOT / "config" / "runbook.yaml").read_text(encoding="utf-8"))
SVC = yaml.safe_load((ROOT / "config" / "services.yaml").read_text(encoding="utf-8"))
_deps = SVC["dependencies"]
RESTARTABLE = (set(_deps) | {c for cs in _deps.values() for c in cs}) - set(RB.get("never_restart", [])) \
    - {"load-generator"}

PORT = int(os.getenv("ACTION_API_PORT", "8000"))
TOKEN = os.getenv("ACTION_API_TOKEN", "")
PLATFORM = os.getenv("PLATFORM", RB.get("platform", "docker"))
K8S_NS = os.getenv("K8S_NAMESPACE", "otel-demo")
FLAGD_UI_URL = os.getenv("FLAGD_UI_URL", "http://localhost:8080/feature").rstrip("/")
LOADGEN_URL = os.getenv("LOADGEN_URL", "http://localhost:8080/loadgen").rstrip("/")
RESTART_LIMIT = int(os.getenv("RESTART_LIMIT", "3"))
MAX_USERS = int(os.getenv("MAX_LOAD_USERS", "50"))
MAX_REPLICAS = int(os.getenv("MAX_REPLICAS", "5"))

_lock = threading.Lock()          # one action at a time
_restarts: dict = {}              # service -> [timestamps]


class ActionError(Exception):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status = status


# ------------------------------------------------------------------ helpers (patched in tests)
def run(args, timeout=60):
    r = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def log(rec: dict) -> dict:
    rec = {"at": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **rec}
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, default=str) + "\n")
    return rec


# ------------------------------------------------------------------ restart_service
def container_for(service: str) -> str:
    code, out = run(["docker", "ps", "-a", "--filter", f"label=com.docker.compose.service={service}",
                     "--format", "{{.Names}}"], timeout=15)
    names = [n for n in out.split() if n] if code == 0 else []
    if names:
        return names[0]
    code, _ = run(["docker", "inspect", service], timeout=15)
    if code == 0:
        return service
    raise ActionError(404, f"no container found for service '{service}'")


def container_state(name: str) -> dict:
    code, out = run(["docker", "inspect", "-f", "{{json .State}}", name], timeout=15)
    if code != 0:
        return {}
    try:
        s = json.loads(out)
        return {"status": s.get("Status"), "running": s.get("Running"), "paused": s.get("Paused"),
                "health": (s.get("Health") or {}).get("Status"), "started_at": s.get("StartedAt")}
    except ValueError:
        return {}


def restart_service(body: dict) -> dict:
    svc = str(body.get("service") or "").strip()
    if svc not in RESTARTABLE:
        raise ActionError(403, f"'{svc}' is not a restartable application service "
                               f"(allowed: {', '.join(sorted(RESTARTABLE))})")
    now = time.time()
    recent = [t for t in _restarts.get(svc, []) if now - t < 600]
    if len(recent) >= RESTART_LIMIT:
        raise ActionError(429, f"{svc} was already restarted {len(recent)}x in 10 min - escalate to a human")
    if PLATFORM == "kubernetes":
        code, out = run(["kubectl", "-n", K8S_NS, "rollout", "restart", f"deployment/{svc}"])
        if code != 0:
            raise ActionError(502, f"kubectl rollout restart failed: {out[:300]}")
        _restarts[svc] = recent + [now]
        return {"service": svc, "platform": "kubernetes", "output": out[:300]}
    name = container_for(svc)
    before = container_state(name)
    steps = []
    if before.get("paused"):
        code, out = run(["docker", "unpause", name])
        steps.append(f"unpause rc={code}")
    code, out = run(["docker", "restart", "-t", "10", name], timeout=90)
    steps.append(f"restart rc={code}")
    if code != 0:
        raise ActionError(502, f"docker restart {name} failed: {out[:300]}")
    _restarts[svc] = recent + [now]
    after = {}
    for _ in range(15):                       # wait up to ~30 s for it to be running (+healthy if it has a check)
        after = container_state(name)
        if after.get("running") and after.get("health") in (None, "healthy"):
            break
        time.sleep(2)
    return {"service": svc, "container": name, "steps": steps, "state_before": before.get("status"),
            "state_after": after.get("status"), "health_after": after.get("health")}


# ------------------------------------------------------------------ toggle_flag
def flag_file():
    if os.getenv("FLAGD_FILE"):
        return Path(os.environ["FLAGD_FILE"])
    code, out = run(["docker", "inspect", "-f", "{{json .Mounts}}", "flagd"], timeout=15)
    if code == 0:
        try:
            for m in json.loads(out) or []:
                if str(m.get("Destination", "")).rstrip("/") == "/etc/flagd":
                    p = Path(m["Source"]) / "demo.flagd.json"
                    if p.exists():
                        return p
        except (ValueError, KeyError):
            pass
    if os.getenv("OTEL_DEMO_DIR"):
        p = Path(os.environ["OTEL_DEMO_DIR"]) / "src" / "flagd" / "demo.flagd.json"
        if p.exists():
            return p
    return None


def _set_variant(doc: dict, flag: str, variant: str):
    flags = doc.get("flags") or {}
    if flag not in flags:
        raise ActionError(404, f"unknown flag '{flag}'")
    if variant not in (flags[flag].get("variants") or {}):
        raise ActionError(400, f"flag '{flag}' has no variant '{variant}'")
    flags[flag]["defaultVariant"] = variant


def _flagd_ui_set(flag: str, variant: str):
    """Change the flag THROUGH flagd-ui when it runs. flagd-ui keeps its own in-memory copy of the flags
    (read once at start-up) and writes it back to the file on every save, so editing the file behind its
    back leaves the UI stale and a later UI save would silently undo our fix. Returns None if not running."""
    try:
        r = requests.get(FLAGD_UI_URL + "/api/read", timeout=5)
        r.raise_for_status()
        doc = r.json()
    except (requests.RequestException, ValueError):
        return None
    _set_variant(doc, flag, variant)
    requests.post(FLAGD_UI_URL + "/api/write", json={"data": doc}, timeout=10).raise_for_status()
    for _ in range(10):        # the write is async in flagd-ui: confirm it took effect (value is not returned)
        time.sleep(0.5)
        try:
            now = requests.get(FLAGD_UI_URL + "/api/read", timeout=5).json()
            if now["flags"][flag]["defaultVariant"] == variant:
                return "flagd-ui api (UI, file and flagd updated)"
        except (requests.RequestException, ValueError, KeyError):
            pass
    raise ActionError(502, "flagd-ui accepted the write but did not apply it")


def _flagd_ui_up() -> bool:
    try:
        return requests.get(FLAGD_UI_URL + "/api/read", timeout=3).status_code == 200
    except requests.RequestException:
        return False


def toggle_flag(body: dict) -> dict:
    flag, variant = str(body.get("flag") or ""), str(body.get("variant") or "")
    if not flag or not variant:
        raise ActionError(400, "need 'flag' and 'variant'")
    via = _flagd_ui_set(flag, variant)
    if via:
        return {"flag": flag, "variant": variant, "via": via}
    path = flag_file()        # flagd-ui not running (minimal mode): edit the file flagd watches
    if not path:
        raise ActionError(502, "flagd-ui unreachable and flag file not found; set FLAGD_FILE or OTEL_DEMO_DIR")
    doc = json.loads(path.read_text(encoding="utf-8"))
    _set_variant(doc, flag, variant)
    # write IN PLACE (same inode) so flagd's file watcher reloads it
    with open(path, "r+", encoding="utf-8") as f:
        f.seek(0)
        f.write(json.dumps(doc, indent=2) + "\n")
        f.truncate()
    return {"flag": flag, "variant": variant, "via": "flagd file (hot reload; flagd-ui not running)"}


# ------------------------------------------------------------------ throttle_load
def throttle_load(body: dict) -> dict:
    try:
        users = int(body.get("users"))
    except (TypeError, ValueError):
        raise ActionError(400, "'users' must be an integer")
    if not 0 <= users <= MAX_USERS:
        raise ActionError(400, f"users must be 0..{MAX_USERS}")
    if users == 0:
        r = requests.get(LOADGEN_URL + "/stop", timeout=15)
    else:
        form = {"user_count": users, "spawn_rate": int(body.get("spawn_rate") or max(1, users))}
        if os.getenv("LOCUST_HOST"):
            form["host"] = os.environ["LOCUST_HOST"]
        r = requests.post(LOADGEN_URL + "/swarm", data=form, timeout=15)
    if r.status_code >= 400:
        raise ActionError(502, f"locust answered HTTP {r.status_code}: {r.text[:200]}")
    return {"users": users, "locust": r.text[:200]}


# ------------------------------------------------------------------ scale_service
def scale_service(body: dict) -> dict:
    svc = str(body.get("service") or "")
    try:
        replicas = int(body.get("replicas"))
    except (TypeError, ValueError):
        raise ActionError(400, "'replicas' must be an integer")
    if svc not in RESTARTABLE:
        raise ActionError(403, f"'{svc}' may not be scaled")
    if not 1 <= replicas <= MAX_REPLICAS:
        raise ActionError(400, f"replicas must be 1..{MAX_REPLICAS}")
    if PLATFORM != "kubernetes":
        raise ActionError(409, "scale_service is only available on Kubernetes (PLATFORM=kubernetes)")
    code, out = run(["kubectl", "-n", K8S_NS, "scale", f"deployment/{svc}", f"--replicas={replicas}"])
    if code != 0:
        raise ActionError(502, f"kubectl scale failed: {out[:300]}")
    return {"service": svc, "replicas": replicas, "output": out[:300]}


ROUTES = {"/actions/restart": ("restart_service", restart_service),
          "/actions/flag": ("toggle_flag", toggle_flag),
          "/actions/load": ("throttle_load", throttle_load),
          "/actions/scale": ("scale_service", scale_service)}


def handle(path: str, body: dict, auth_header: str = "") -> tuple:
    """Pure request handler -> (http_status, response_dict). Used by the HTTP server and the tests."""
    if path not in ROUTES:
        return 404, {"ok": False, "error": f"unknown action endpoint {path}"}
    action, fn = ROUTES[path]
    approval = body.pop("approval", None) or {}
    incident = body.pop("incident_id", None)
    base = {"action": action, "params": body, "incident_id": incident,
            "approved_by": approval.get("by"), "approved_at": approval.get("at")}
    if TOKEN and auth_header != f"Bearer {TOKEN}":
        log({**base, "result": "refused", "why": "bad token"})
        return 401, {"ok": False, "error": "missing/invalid bearer token"}
    if KILL_FILE.exists():
        log({**base, "result": "refused", "why": "kill switch engaged"})
        return 423, {"ok": False, "error": "kill switch engaged - nothing executed"}
    if action not in RB.get("allowlist", []):
        log({**base, "result": "refused", "why": "not on allowlist"})
        return 403, {"ok": False, "error": f"{action} is not on the allowlist"}
    if approval.get("decision") != "approved" or not approval.get("by"):
        log({**base, "result": "refused", "why": "no human approval"})
        return 403, {"ok": False, "error": "refused: no approval record from a human"}
    with _lock:
        t0 = time.time()
        try:
            detail = fn(body)
        except ActionError as e:
            log({**base, "result": "failed", "error": str(e)})
            return e.status, {"ok": False, "action": action, "error": str(e)}
        except Exception as e:  # noqa: BLE001 - never crash the server
            log({**base, "result": "failed", "error": f"{type(e).__name__}: {e}"})
            return 500, {"ok": False, "action": action, "error": f"{type(e).__name__}: {str(e)[:200]}"}
    rec = log({**base, "result": "ok", "detail": detail, "took_s": round(time.time() - t0, 1)})
    return 200, {"ok": True, "action": action, "detail": detail, "logged_at": rec["at"]}


def status() -> dict:
    code, _ = run(["docker", "version", "--format", "{{.Server.Version}}"], timeout=10)
    return {"ok": True, "service": "action-api", "platform": PLATFORM, "kill_switch": KILL_FILE.exists(),
            "docker": code == 0, "flag_file_found": flag_file() is not None, "flagd_ui": _flagd_ui_up(),
            "actions": {path: a for path, (a, _) in ROUTES.items()}}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        data = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path in ("/", "/health"):
            return self._send(200, status())
        if path == "/actions/log":
            rows = LOG_FILE.read_text(encoding="utf-8").splitlines()[-200:] if LOG_FILE.exists() else []
            return self._send(200, {"entries": [json.loads(r) for r in rows if r.strip()]})
        self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0) or 0)) or b"{}")
            if not isinstance(body, dict):
                raise ValueError
        except ValueError:
            return self._send(400, {"ok": False, "error": "body must be a JSON object"})
        code, resp = handle(urlparse(self.path).path.rstrip("/"), body, self.headers.get("Authorization", ""))
        print(f"{time.strftime('%H:%M:%S')} {self.path} -> {code} {json.dumps(resp)[:200]}", flush=True)
        self._send(code, resp)


def main():
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    st = status()
    print(f"Action API on http://127.0.0.1:{PORT}  platform={PLATFORM}  docker={'ok' if st['docker'] else 'NOT FOUND'}"
          f"  flags via={'flagd-ui api' if st['flagd_ui'] else ('flag file' if st['flag_file_found'] else 'NOTHING FOUND')}"
          f"  kill switch={'ENGAGED' if st['kill_switch'] else 'off'}", flush=True)
    print(f"log: {LOG_FILE}   Ctrl-C to stop", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
