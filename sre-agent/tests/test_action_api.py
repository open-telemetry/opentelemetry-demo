"""Action API server tests: real HTTP, fake docker / locust, temp flag file. Run: python -m tests.run"""
import json
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from action_api import server as S

_tmp = Path(tempfile.mkdtemp())
S.LOG_FILE = _tmp / "server.jsonl"
S.KILL_FILE = _tmp / "KILL"
APPROVED = {"decision": "approved", "by": "tester", "at": "now"}

DOCKER_CALLS = []
_STATE = {"payment": {"Status": "exited", "Running": False, "Paused": False}}


def fake_run(args, timeout=60):
    DOCKER_CALLS.append(args)
    if args[:2] == ["docker", "ps"]:
        svc = args[4].rsplit("=", 1)[1]
        return 0, svc if svc in ("payment", "cart", "valkey-cart") else ""
    if args[:2] == ["docker", "restart"]:
        _STATE[args[-1]] = {"Status": "running", "Running": True, "Paused": False}
        return 0, args[-1]
    if args[:2] == ["docker", "inspect"] and "{{json .State}}" in args:
        return 0, json.dumps(_STATE.get(args[-1], {"Status": "running", "Running": True}))
    if args[:2] == ["docker", "inspect"]:
        return 1, "no such object"
    return 0, ""


S.run = fake_run
S.time.sleep = lambda s: None
FLAGS = _tmp / "demo.flagd.json"
FLAGS.write_text(json.dumps({"flags": {"paymentFailure": {"state": "ENABLED", "variants": {"100%": 1, "off": 0},
                                                             "defaultVariant": "100%"}}}))
S.os.environ["FLAGD_FILE"] = str(FLAGS)
S.FLAGD_UI_URL = "http://127.0.0.1:9"      # never touch the real flagd-ui on the laptop during tests
S.LOADGEN_URL = "http://127.0.0.1:9"


def test_refuses_without_approval_or_with_kill_switch():
    code, r = S.handle("/actions/restart", {"service": "payment"})
    assert code == 403 and "approval" in r["error"]
    code, r = S.handle("/actions/restart", {"service": "payment", "approval": {"decision": "rejected", "by": "x"}})
    assert code == 403
    S.KILL_FILE.write_text("{}")
    try:
        code, r = S.handle("/actions/restart", {"service": "payment", "approval": dict(APPROVED)})
        assert code == 423
    finally:
        S.KILL_FILE.unlink()
    code, r = S.handle("/actions/rm", {"approval": dict(APPROVED)})
    assert code == 404


def test_restart_starts_stopped_container_and_refuses_infra():
    DOCKER_CALLS.clear()
    S._restarts.clear()
    _STATE["payment"] = {"Status": "exited", "Running": False, "Paused": False}
    code, r = S.handle("/actions/restart", {"service": "payment", "approval": dict(APPROVED)})
    assert code == 200 and r["ok"], r
    assert ["docker", "restart", "-t", "10", "payment"] in DOCKER_CALLS
    assert r["detail"]["state_before"] == "exited" and r["detail"]["state_after"] == "running"
    code, r = S.handle("/actions/restart", {"service": "otel-collector", "approval": dict(APPROVED)})
    assert code == 403
    code, r = S.handle("/actions/restart", {"service": "nope; rm -rf /", "approval": dict(APPROVED)})
    assert code == 403


def test_restart_rate_limit():
    S._restarts.clear()
    for _ in range(S.RESTART_LIMIT):
        assert S.handle("/actions/restart", {"service": "cart", "approval": dict(APPROVED)})[0] == 200
    code, r = S.handle("/actions/restart", {"service": "cart", "approval": dict(APPROVED)})
    assert code == 429


def test_toggle_flag_edits_file_and_does_not_leak_state():
    code, r = S.handle("/actions/flag", {"flag": "paymentFailure", "variant": "off", "approval": dict(APPROVED)})
    assert code == 200, r
    assert json.loads(FLAGS.read_text())["flags"]["paymentFailure"]["defaultVariant"] == "off"
    assert "100%" not in json.dumps(r)          # the previous value is never returned
    code, r = S.handle("/actions/flag", {"flag": "paymentFailure", "variant": "bogus", "approval": dict(APPROVED)})
    assert code == 400
    code, r = S.handle("/actions/flag", {"flag": "noSuchFlag", "variant": "off", "approval": dict(APPROVED)})
    assert code == 404


def test_throttle_and_scale():
    sent = {}

    class R:
        status_code, text = 200, '{"success": true}'

    orig = S.requests.post
    S.requests.post = lambda url, data=None, timeout=None: sent.update(url=url, data=data) or R()
    try:
        code, r = S.handle("/actions/load", {"users": "2", "approval": dict(APPROVED)})
    finally:
        S.requests.post = orig
    assert code == 200 and sent["url"].endswith("/swarm") and sent["data"]["user_count"] == 2
    code, r = S.handle("/actions/load", {"users": 10_000, "approval": dict(APPROVED)})
    assert code == 400
    code, r = S.handle("/actions/scale", {"service": "ad", "replicas": 2, "approval": dict(APPROVED)})
    assert code == 409                         # docker compose: kubernetes only


def test_agent_client_talks_to_server_over_http():
    """The agent's real client (http mode) -> this server -> fake docker. Also: every call is logged."""
    from agent import actions, config
    srv = ThreadingHTTPServer(("127.0.0.1", 0), S.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    old = (config.ACTION_API_MODE, actions._API, config.KILL_FILE, config.RUNS)
    config.ACTION_API_MODE = "http"
    config.KILL_FILE, config.RUNS = _tmp / "AGENT_KILL", _tmp
    actions._API = {**actions.api_cfg(), "base_url": f"http://127.0.0.1:{srv.server_port}"}
    S._restarts.clear()
    try:
        r = actions.execute("restart_service", {"service": "payment"}, approval=dict(APPROVED))
        assert r["result"] == "ok" and r["status"] == 200, r
        r = actions.execute("restart_service", {"service": "payment"}, approval={"decision": "rejected"})
        assert r["result"] == "refused"        # agent-side gate
    finally:
        config.ACTION_API_MODE, actions._API, config.KILL_FILE, config.RUNS = old
        srv.shutdown()
    rows = [json.loads(l) for l in S.LOG_FILE.read_text().splitlines()]
    assert rows[-1]["action"] == "restart_service" and rows[-1]["approved_by"] == "tester"


def test_toggle_flag_goes_through_flagd_ui_when_running():
    """flagd-ui caches flags in memory; changing them through its API keeps UI, file and flagd in sync."""
    from http.server import BaseHTTPRequestHandler
    store = {"flags": {"paymentFailure": {"variants": {"100%": 1, "off": 0}, "defaultVariant": "100%"}}}

    class UI(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            body = json.dumps(store).encode()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            store.update(json.loads(self.rfile.read(int(self.headers["Content-Length"])))["data"])
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"{}")

    ui = ThreadingHTTPServer(("127.0.0.1", 0), UI)
    threading.Thread(target=ui.serve_forever, daemon=True).start()
    old_url, old_sleep = S.FLAGD_UI_URL, S.time.sleep
    S.FLAGD_UI_URL = f"http://127.0.0.1:{ui.server_port}"
    file_before = FLAGS.read_text()
    try:
        code, r = S.handle("/actions/flag", {"flag": "paymentFailure", "variant": "off", "approval": dict(APPROVED)})
    finally:
        S.FLAGD_UI_URL = old_url
        ui.shutdown()
    assert code == 200 and "flagd-ui" in r["detail"]["via"], r
    assert store["flags"]["paymentFailure"]["defaultVariant"] == "off"
    assert FLAGS.read_text() == file_before        # file left to flagd-ui, not edited behind its back
    assert "100%" not in json.dumps(r)
