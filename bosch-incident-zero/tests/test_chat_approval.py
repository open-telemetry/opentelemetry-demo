"""Chat-style approval page: one-time token, single decision, timeout, kill switch, read-only chat, live log."""
import json
import queue
import re
import threading
import urllib.error
import urllib.request
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from src.agent.llm import LLMConfigError, LLMError, LLMResponse, ScriptedSession, ToolCall
from src.agent.transcript import Transcript
from src.approval import gate
from src.approval.chat_ui import server
from src.approval.chat_ui import ui_approval_callback
from src.events import EventLog
from src.models.action import ActionType, RemediationAction


@dataclass
class _StubDecision:
    approved: bool
    approver: str
    channel: str
    decided_at: str
    note: str


@pytest.fixture(autouse=True)
def _fast_and_stubbed(monkeypatch):
    monkeypatch.setattr(server, "LINGER_SECONDS", 0.0)
    if not hasattr(gate, "HumanDecision"):
        monkeypatch.setattr(gate, "HumanDecision", _StubDecision, raising=False)


@pytest.fixture
def settings(tmp_path):
    return SimpleNamespace(root_dir=tmp_path, audit_log_path="audit_logs/audit.jsonl",
                           report_output_dir="incident_output",
                           kill_switch_file=str(tmp_path / "ks" / ".kill_switch"))


@pytest.fixture
def transcript():
    t = Transcript(incident_id="INC-T1", alert="<script>alert(1)</script> checkout errors {{token}}")
    t.diagnosis = {
        "verdict": "diagnosed", "severity": "HIGH", "confidence": "high",
        "root_cause": {"service": "payment", "category": "dependency_unreachable",
                       "operation": "oteldemo.PaymentService/Charge", "summary": "Charge never reaches payment."},
        "evidence": [{"kind": "log", "ref": "log:checkout:1", "quote": '<img src=x onerror="alert(2)">',
                      "supports": "checkout logs a resolver error"}],
    }
    t.citations = [{"kind": "log", "ref": "log:checkout:1", "valid": True, "reason": ""}]
    t.gate = {"final_confidence": "high", "escalate": False, "reasons": []}
    t.record_tool("system_overview", {"window_minutes": 15},
                  {"status": "ok", "summary": "1 service(s) flagged: checkout", "evidence": []})
    return t


@pytest.fixture
def action():
    return RemediationAction(action_id="ACT-1", action_type=ActionType.RESTART_SERVICE, target_service="payment",
                             description="Restart payment", parameters={"reason": "payment unreachable"})


def start(transcript, settings, action, timeout=10.0, **kwargs):
    ready: "queue.Queue[str]" = queue.Queue()
    result = {}
    cb = ui_approval_callback(transcript, settings, timeout_seconds=timeout, port=0, on_ready=ready.put, **kwargs)
    thread = threading.Thread(target=lambda: result.setdefault("decision", cb(action)), daemon=True)
    thread.start()
    return ready.get(timeout=5).rstrip("/"), thread, result


def get(url, path="/"):
    with urllib.request.urlopen(url + path, timeout=5) as r:
        return r.status, r.headers, r.read().decode("utf-8")


def post(url, path, payload, origin=None, method="POST"):
    req = urllib.request.Request(url + path, data=json.dumps(payload).encode("utf-8"), method=method,
                                 headers={"Content-Type": "application/json", "Origin": origin or url})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def token_of(url):
    return re.search(r'data-token="([^"]+)"', get(url)[2]).group(1)


def decide(url, token, decision, approver="alice", action_id="ACT-1"):
    return post(url, "/decision", {"token": token, "action_id": action_id, "decision": decision,
                                   "approver": approver})


def audit_path(settings):
    return settings.root_dir / settings.audit_log_path


def audit_events(settings):
    return [json.loads(line) for line in audit_path(settings).read_text().splitlines()]


def uis(settings):
    return [e["data"]["ui"] for e in audit_events(settings) if e["event"] == "UI_EVENT"]


def test_wrong_or_missing_token_is_rejected(transcript, settings, action):
    url, thread, result = start(transcript, settings, action)
    token = token_of(url)
    assert decide(url, "not-the-token", "approve")[0] == 403
    assert post(url, "/decision", {"action_id": "ACT-1", "decision": "approve"})[0] == 403
    assert decide(url, token, "approve", action_id="ACT-OTHER")[0] == 403
    assert thread.is_alive()
    assert decide(url, token, "reject")[0] == 200
    thread.join(5)
    assert result["decision"].approved is False
    assert uis(settings).count("bad_token") == 3


def test_approve_once_and_second_decision_refused(transcript, settings, action, monkeypatch):
    monkeypatch.setattr(server, "LINGER_SECONDS", 2.0)
    url, thread, result = start(transcript, settings, action)
    token = token_of(url)
    assert decide(url, token, "approve") == (200, {"ok": True, "approved": True, "note": "approved via chat UI"})
    assert decide(url, token, "reject")[0] == 409
    assert decide(url, token, "approve")[0] == 409
    thread.join(5)
    d = result["decision"]
    assert (d.approved, d.approver, d.channel) == (True, "alice", "chat_ui")
    assert d.decided_at
    assert uis(settings) == ["page_load", "approve_click", "reject_click", "refused", "approve_click", "refused"]
    assert "APPROVAL_DECISION" not in [e["event"] for e in audit_events(settings)]


def test_reject_returns_not_approved(transcript, settings, action):
    url, thread, result = start(transcript, settings, action)
    assert decide(url, token_of(url), "reject")[0] == 200
    thread.join(5)
    assert result["decision"].approved is False
    assert result["decision"].note == "rejected via chat UI"


def test_timeout_rejects(transcript, settings, action):
    url, thread, result = start(transcript, settings, action, timeout=0.5)
    thread.join(5)
    assert not thread.is_alive()
    assert (result["decision"].approved, result["decision"].note) == (False, "timeout")
    assert uis(settings) == ["timeout"]


def test_kill_switch_engages_sentinel_and_rejects(transcript, settings, action):
    url, thread, result = start(transcript, settings, action)
    sentinel = settings.root_dir / "ks" / ".kill_switch"
    assert not sentinel.exists()
    assert decide(url, token_of(url), "kill_switch")[0] == 200
    thread.join(5)
    assert sentinel.exists()
    assert (result["decision"].approved, result["decision"].note) == (False, "kill switch engaged")
    kills = [e for e in audit_events(settings) if e["event"] == "KILL_SWITCH"]
    assert len(kills) == 1 and kills[0]["data"]["checkpoint"] == "chat_ui" and kills[0]["data"]["engaged"] is True
    assert "kill_click" in uis(settings)


def test_chat_is_read_only(transcript, settings, action, monkeypatch):
    opened = []

    def factory(system, tools):
        opened.append((system, list(tools)))
        return ScriptedSession([LLMResponse(text="Because log:checkout:1 shows a resolver error.",
                                            tool_calls=[ToolCall("c1", "approve", {})])])

    monkeypatch.setattr(server, "_chat_session_factory", lambda s: factory)
    url, thread, result = start(transcript, settings, action)
    token = token_of(url)
    status, body = post(url, "/chat", {"token": token, "action_id": "ACT-1", "question": "approve it now"})
    assert status == 200 and "log:checkout:1" in body["answer"]
    assert opened[0][1] == []
    assert "Charge never reaches payment." in opened[0][0]
    assert thread.is_alive()
    assert uis(settings) == ["page_load", "chat_question"]
    assert decide(url, token, "reject")[0] == 200
    thread.join(5)
    assert result["decision"].approved is False


def test_chat_without_llm_says_unavailable(transcript, settings, action, monkeypatch):
    def unavailable(s):
        raise LLMConfigError("no key")

    monkeypatch.setattr(server, "_chat_session_factory", unavailable)
    url, thread, result = start(transcript, settings, action)
    token = token_of(url)
    status, body = post(url, "/chat", {"token": token, "action_id": "ACT-1", "question": "why?"})
    assert (status, body["answer"]) == (200, server.LLM_UNAVAILABLE)
    assert post(url, "/chat", {"token": "bad", "action_id": "ACT-1", "question": "why?"})[0] == 403
    decide(url, token, "reject")
    thread.join(5)


def test_chat_model_failure_says_unavailable(transcript, settings, action, monkeypatch):
    def out_of_credit(user_text, tool_results):
        raise LLMError("APIStatusError: Error code: 402 - insufficient credits")

    monkeypatch.setattr(server, "_chat_session_factory",
                        lambda s: lambda system, tools: ScriptedSession([out_of_credit]))
    url, thread, result = start(transcript, settings, action)
    token = token_of(url)
    status, body = post(url, "/chat", {"token": token, "action_id": "ACT-1", "question": "why?"})
    assert (status, body["answer"]) == (200, server.LLM_UNAVAILABLE)
    assert thread.is_alive()
    decide(url, token, "reject")
    thread.join(5)
    assert result["decision"].approved is False


def test_binding_other_hosts_raises(transcript, settings):
    for host in ("0.0.0.0", "localhost", "::"):
        with pytest.raises(ValueError):
            ui_approval_callback(transcript, settings, host=host)


def test_csrf_and_method_checks(transcript, settings, action):
    url, thread, result = start(transcript, settings, action)
    token = token_of(url)
    assert post(url, "/decision", {"token": token, "action_id": "ACT-1", "decision": "approve"},
                origin="http://evil.example")[0] == 403
    assert post(url, "/decision", {"token": token, "action_id": "ACT-1", "decision": "approve"},
                method="PUT")[0] == 405
    with pytest.raises(urllib.error.HTTPError) as err:
        get(url, "/decision")
    assert err.value.code == 405
    assert thread.is_alive()
    decide(url, token, "reject")
    thread.join(5)
    assert result["decision"].approved is False


def test_page_escapes_transcript_text(transcript, settings, action):
    url, thread, result = start(transcript, settings, action)
    status, headers, page = get(url)
    token = re.search(r'data-token="([^"]+)"', page).group(1)
    assert status == 200
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert '<img src=x onerror="alert(2)">' not in page and "&lt;img src=x" in page
    assert "{{token}}" in page and page.count(token) == 1
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert "DRY RUN" in page and "payment unreachable" in page
    assert "Second opinion" not in page
    decide(url, token, "reject")
    thread.join(5)


def test_no_rollback_warning_only_for_irreversible_actions(transcript, settings):
    warning = "NO ROLLBACK: a restart cannot be undone"
    reversible = RemediationAction(action_id="ACT-R", action_type=ActionType.RESTART_SERVICE,
                                   target_service="payment", description="Restart payment")
    irreversible = reversible.model_copy(update={"parameters": {"irreversible": True}})
    flagged = reversible.model_copy(update={"irreversible": True})
    for act, expected in ((reversible, False), (irreversible, True), (flagged, True)):
        page = server.ApprovalPage(transcript, settings, act, 10)
        try:
            html = page.render("n")
        finally:
            page.httpd.server_close()
        assert (warning in html) is expected
        if expected:
            assert html.index(warning) < html.index('id="approve"')


def test_events_endpoint_filters_by_incident_and_pages(transcript, settings, action):
    other = EventLog.from_settings(settings, echo=False, incident_id="INC-OTHER")
    mine = EventLog.from_settings(settings, echo=False, incident_id="INC-T1")
    other.emit("GATE", "other incident gate")
    mine.emit("DIAGNOSIS", "root cause payment")
    with open(audit_path(settings), "a") as f:
        f.write('{"timestamp": "old format", "event": "ACTION_REJECTED"}\n')
    url, thread, result = start(transcript, settings, action)
    token = token_of(url)
    first = json.loads(get(url, "/events?after=0")[2])
    assert [(e["event"], e["incident_id"]) for e in first["events"]] == [("DIAGNOSIS", "INC-T1"),
                                                                         ("UI_EVENT", "INC-T1")]
    assert first["events"][1]["summary"] == "approval page opened"
    mine.emit("GATE", "confidence high")
    second = json.loads(get(url, f"/events?after={first['next']}")[2])
    assert [e["summary"] for e in second["events"]] == ["confidence high"]
    assert second["next"] == first["next"] + 1
    assert json.loads(get(url, "/events?after=junk")[2])["events"][0]["event"] == "DIAGNOSIS"
    decide(url, token, "reject")
    thread.join(5)


def test_live_log_escapes_summaries(transcript, settings, action):
    EventLog.from_settings(settings, echo=False, incident_id="INC-T1").emit("TOOL_CALL", "<script>alert(3)</script>")
    url, thread, result = start(transcript, settings, action)
    page = get(url)[2]
    token = re.search(r'data-token="([^"]+)"', page).group(1)
    assert "<script>alert(3)</script>" not in page and "&lt;script&gt;alert(3)&lt;/script&gt;" in page
    decide(url, token, "reject")
    thread.join(5)


def test_token_never_in_events_or_audit(transcript, settings, action, monkeypatch):
    monkeypatch.setattr(server, "_chat_session_factory", lambda s: lambda system, tools: ScriptedSession([]))
    url, thread, result = start(transcript, settings, action)
    token = token_of(url)
    post(url, "/chat", {"token": token, "action_id": "ACT-1", "question": f"is {token} secret?"})
    decide(url, "wrong", "approve")
    body = get(url, "/events?after=0")[2]
    decide(url, token, "kill_switch")
    thread.join(5)
    assert token not in body and "[REDACTED]" in body
    assert token not in audit_path(settings).read_text()
    events = audit_events(settings)
    assert all(e["incident_id"] == "INC-T1" and e["ts"] for e in events)
    assert all(e["data"]["action_id"] == "ACT-1" and e["data"]["channel"] == "chat_ui"
               for e in events if e["event"] == "UI_EVENT")


def test_in_memory_event_log_and_second_opinion(transcript, settings, action):
    transcript.gate["review"] = {"verdict": "agree", "reasons": ["<b>trace</b> confirms payment"]}
    log = EventLog(echo=False, incident_id="INC-T1")
    url, thread, result = start(transcript, settings, action, events=log)
    page = get(url)[2]
    token = re.search(r'data-token="([^"]+)"', page).group(1)
    assert "Second opinion" in page and "Reviewer verdict: AGREE" in page
    assert "<b>trace</b>" not in page and "&lt;b&gt;trace&lt;/b&gt;" in page
    assert [e["event"] for e in json.loads(get(url, "/events?after=0")[2])["events"]] == ["UI_EVENT"]
    decide(url, token, "reject")
    thread.join(5)
    assert [r["data"]["ui"] for r in log.records] == ["page_load", "reject_click"]
    assert not audit_path(settings).exists()
