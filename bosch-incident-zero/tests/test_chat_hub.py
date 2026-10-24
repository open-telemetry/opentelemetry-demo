"""Always-on incident hub: read-only incident view and chat, redirect to a waiting approval page, port fallback."""
import json
import socket
import threading
import time
import urllib.error
import urllib.request

import pytest

from src.agent.llm import LLMResponse, ScriptedSession
from src.approval.chat_ui import server
from src.approval.chat_ui.hub import Hub, active_approval
from tests.test_chat_approval import action, decide, get, post, settings, start, token_of, transcript  # noqa: F401


@pytest.fixture(autouse=True)
def _fast(monkeypatch):
    monkeypatch.setattr(server, "LINGER_SECONDS", 0.0)


def store(settings, transcript, report_status="ESCALATED"):
    folder = settings.root_dir / settings.report_output_dir / transcript.incident_id
    folder.mkdir(parents=True, exist_ok=True)
    record = {**vars(transcript), "report": {"status": report_status}}
    (folder / "transcript.json").write_text(json.dumps(record, default=str))


@pytest.fixture
def hub(settings):
    sessions = []

    def factory(system, tools):
        sessions.append(system)
        return ScriptedSession([LLMResponse(text="Because log:checkout:1 shows a resolver error.")])

    h = Hub(settings, port=0, new_session=factory)
    h.sessions = sessions
    threading.Thread(target=h.serve_forever, daemon=True).start()
    yield h
    h.shutdown()


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def get_no_redirect(url):
    try:
        with urllib.request.build_opener(_NoRedirect).open(url, timeout=5) as r:
            return r.status, r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.headers


def test_idle_hub_shows_stored_incident_read_only(settings, transcript, hub):
    store(settings, transcript)
    status, _, body = get(hub.url.rstrip("/"))
    assert status == 200
    assert "INC-T1" in body and "Charge never reaches payment." in body and "ESCALATED" in body
    assert "<script>alert(1)</script>" not in body
    assert "/decision" not in body and 'id="approve"' not in body


def test_hub_with_no_incidents_still_serves(hub):
    status, _, body = get(hub.url.rstrip("/"))
    assert status == 200 and "No stored incidents yet" in body


def test_chat_answers_from_transcript_with_token(settings, transcript, hub):
    store(settings, transcript)
    url = hub.url.rstrip("/")
    token = token_of(url)
    assert post(url, "/chat", {"token": "wrong", "incident_id": "INC-T1", "question": "why?"})[0] == 403
    assert post(url, "/chat", {"token": token, "incident_id": "INC-T1", "question": "why?"},
                origin="http://evil.example")[0] == 403
    assert post(url, "/chat", {"token": token, "incident_id": "../../etc", "question": "why?"})[0] == 404
    status, body = post(url, "/chat", {"token": token, "incident_id": "INC-T1", "question": "why?"})
    assert status == 200 and "log:checkout:1" in body["answer"]
    assert "Charge never reaches payment." in hub.sessions[0]


def test_hub_redirects_to_waiting_approval_and_back(settings, transcript, action, hub):
    url, thread, result = start(transcript, settings, action)
    assert active_approval(settings) == url + "/"
    status, headers = get_no_redirect(hub.url)
    assert status == 303 and headers["Location"] == url + "/"
    assert json.loads(get(hub.url.rstrip("/"), "/status")[2])["approval_url"] == url + "/"
    assert decide(url, token_of(url), "reject")[0] == 200
    thread.join(5)
    assert result["decision"].approved is False
    assert active_approval(settings) is None
    assert get_no_redirect(hub.url)[0] == 200


def test_stale_or_foreign_active_records_are_ignored(settings):
    path = server.active_file(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        port = s.getsockname()[1]
        path.write_text(json.dumps({"url": f"http://127.0.0.1:{port}/", "deadline": time.time() + 60}))
        assert active_approval(settings) == f"http://127.0.0.1:{port}/"
        path.write_text(json.dumps({"url": f"http://127.0.0.1:{port}/", "deadline": time.time() - 1}))
        assert active_approval(settings) is None
        path.write_text(json.dumps({"url": f"http://evil.example:{port}/", "deadline": time.time() + 60}))
        assert active_approval(settings) is None
    path.write_text(json.dumps({"url": f"http://127.0.0.1:{port}/", "deadline": time.time() + 60}))
    assert active_approval(settings) is None


def test_approval_page_moves_off_a_busy_port(settings, transcript, action, hub):
    cb = server.ui_approval_callback(transcript, settings, timeout_seconds=10, port=hub.port,
                                     on_ready=lambda u: ready.append(u))
    ready = []
    result = {}
    thread = threading.Thread(target=lambda: result.setdefault("decision", cb(action)), daemon=True)
    thread.start()
    for _ in range(50):
        if ready:
            break
        time.sleep(0.1)
    url = ready[0].rstrip("/")
    assert not url.endswith(f":{hub.port}")
    assert decide(url, token_of(url), "approve")[0] == 200
    thread.join(5)
    assert result["decision"].approved is True
