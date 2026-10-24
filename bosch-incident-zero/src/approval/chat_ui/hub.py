"""Always-on incident hub on 127.0.0.1: browse stored incidents, ask "why?" about one, and jump to a waiting approval.

The hub never approves anything. While an agent run waits for a decision, GET / redirects to that run's own
one-time approval page; otherwise it shows stored transcripts read-only.

    python -m src.approval.chat_ui.hub [--port 8799]
"""
from __future__ import annotations

import argparse
import dataclasses
import html
import json
import re
import secrets
import socket
import threading
import time
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import parse_qs, urlsplit

from ...agent.transcript import Transcript
from .server import (ALLOWED_HOST, CHAT_SYSTEM_PROMPT, LLM_UNAVAILABLE, MAX_QUESTION_CHARS, MAX_RECORD_CHARS,
                     _Handler, _chat_session_factory, active_file, evidence_rows, output_dir, tool_rows)

_PAGE = Path(__file__).with_name("hub.html")
# Incident ids are directory names such as INC-20261024-052210 or REPLAY-DEMO-001-105203.
_INCIDENT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_PLACEHOLDER = re.compile(r"\{\{(\w+)\}\}")
MAX_INCIDENTS = 30
HUB_SYSTEM_PROMPT = ("You are a read-only assistant on an incident review page. A human engineer asks you "
                     "questions about a stored incident investigation.\n\n"
                     + CHAT_SYSTEM_PROMPT[CHAT_SYSTEM_PROMPT.index("Rules:"):])


def active_approval(settings: Any) -> Optional[str]:
    """URL of an approval page that is waiting for a decision right now, else None."""
    try:
        record = json.loads(active_file(settings).read_text(encoding="utf-8"))
        url = str(record["url"])
        deadline = float(record["deadline"])
    except (OSError, ValueError, KeyError, TypeError):
        return None
    parts = urlsplit(url)
    if (parts.scheme != "http" or parts.hostname != ALLOWED_HOST or not parts.port or parts.path != "/"
            or parts.query or time.time() > deadline):
        return None
    try:
        with socket.create_connection((ALLOWED_HOST, parts.port), timeout=0.5):
            return f"http://{ALLOWED_HOST}:{parts.port}/"
    except OSError:
        return None


def load_transcript(path: Path) -> Transcript:
    raw = json.loads(path.read_text(encoding="utf-8"))
    names = {f.name for f in dataclasses.fields(Transcript)}
    return Transcript(**{k: v for k, v in raw.items() if k in names})


class Hub:
    def __init__(self, settings: Any, port: int = 8799,
                 new_session: Optional[Callable[[str, Any], Any]] = None) -> None:
        self.settings = settings
        self.token = secrets.token_urlsafe(32)
        self._new_session = new_session
        self._chats: Dict[str, Any] = {}
        self._chat_lock = threading.Lock()
        self.httpd = ThreadingHTTPServer((ALLOWED_HOST, port), _HubHandler)
        self.httpd.daemon_threads = True
        self.httpd.page = self  # type: ignore[attr-defined]
        self.port = self.httpd.server_address[1]
        self.url = f"http://{ALLOWED_HOST}:{self.port}/"
        self.allowed_hosts = {f"{ALLOWED_HOST}:{self.port}", f"localhost:{self.port}"}
        self.allowed_origins = {f"http://{h}" for h in self.allowed_hosts}

    def ui_event(self, ui: str, summary: str, **data: Any) -> None:
        pass

    def serve_forever(self) -> None:
        self.httpd.serve_forever(poll_interval=0.2)

    def shutdown(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def incidents(self) -> List[str]:
        root = output_dir(self.settings)
        try:
            found = [p for p in root.glob("*/transcript.json") if _INCIDENT_ID.match(p.parent.name)]
        except OSError:
            return []
        found.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        return [p.parent.name for p in found[:MAX_INCIDENTS]]

    def transcript(self, incident_id: str) -> Optional[Transcript]:
        if not _INCIDENT_ID.match(incident_id or ""):
            return None
        path = output_dir(self.settings) / incident_id / "transcript.json"
        try:
            return load_transcript(path)
        except (OSError, ValueError, TypeError):
            return None

    def record_json(self, t: Transcript) -> str:
        calls = []
        for c in t.tool_calls or []:
            result = c.get("result") or {}
            calls.append({"n": c.get("n"), "tool": c.get("tool"), "arguments": c.get("arguments"),
                          "status": result.get("status"), "summary": result.get("summary"),
                          "evidence_refs": [ev.get("ref") for ev in (result.get("evidence") or [])[:20]]})
        report = t.report or {}
        record = {"incident_id": t.incident_id, "alert": t.alert, "diagnosis": t.diagnosis,
                  "confidence_gate": t.gate, "citation_checks": t.citations,
                  "report_status": report.get("status"), "remediation": report.get("remediation"),
                  "errors": t.errors, "tool_calls": calls}
        text = json.dumps(record, default=str)
        return text if len(text) <= MAX_RECORD_CHARS else text[:MAX_RECORD_CHARS] + "...(truncated)"

    def answer(self, t: Transcript, question: str) -> str:
        with self._chat_lock:
            try:
                chat = self._chats.get(t.incident_id)
                if chat is None:
                    factory = self._new_session or _chat_session_factory(self.settings)
                    chat = factory(HUB_SYSTEM_PROMPT + self.record_json(t), [])
                    self._chats[t.incident_id] = chat
                text = (chat.send(user_text=question).text or "").strip()
            except Exception:
                self._chats.pop(t.incident_id, None)
                return LLM_UNAVAILABLE
        return text or LLM_UNAVAILABLE

    def render(self, nonce: str, selected: Optional[str]) -> str:
        e = lambda v: html.escape("" if v is None else str(v), quote=True)  # noqa: E731
        ids = self.incidents()
        incident_id = selected if selected in ids else (ids[0] if ids else "")
        t = self.transcript(incident_id) if incident_id else None
        options = "".join(f'<option value="{e(i)}"{" selected" if i == incident_id else ""}>{e(i)}</option>'
                          for i in ids)
        values: Dict[str, str] = {"nonce": e(nonce), "token": e(self.token), "options": options,
                                  "incident_id": e(incident_id)}
        if t is None:
            values["body_class"] = "empty"
            return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), ""), _PAGE.read_text(encoding="utf-8"))
        diag = t.diagnosis or {}
        root = diag.get("root_cause") or {}
        gate = t.gate or {}
        report = t.report or {}
        remediation = report.get("remediation") or {}
        values.update({
            "alert": e(t.alert), "status": e(report.get("status") or "-"),
            "verdict": e(diag.get("verdict") or "no diagnosis"),
            "rc_service": e(root.get("service") or "unknown"), "rc_category": e(root.get("category") or "unknown"),
            "rc_summary": e(root.get("summary") or report.get("root_cause_summary") or "-"),
            "final_confidence": e(gate.get("final_confidence") or "-"),
            "gate_reasons": "".join(f"<li>{e(r)}</li>" for r in gate.get("reasons") or []) or "<li>none</li>",
            "action": e(remediation.get("recommended_action") or "-"),
            "approval_status": e(remediation.get("approval_status") or "-"),
            "evidence_rows": evidence_rows(t, diag, e), "tool_rows": tool_rows(t, e),
        })
        return _PLACEHOLDER.sub(lambda m: values.get(m.group(1), ""), _PAGE.read_text(encoding="utf-8"))


class _HubHandler(_Handler):
    server_version = "IncidentZeroHub"

    @property
    def hub(self) -> Hub:
        return self.server.page  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        if not self._host_ok():
            return self._refuse(403, "bad host")
        parts = urlsplit(self.path)
        if parts.path == "/status":
            return self._json(200, {"approval_url": active_approval(self.hub.settings)})
        if parts.path != "/":
            return self._json(404, {"error": "not found"})
        approval = active_approval(self.hub.settings)
        if approval:
            self.send_response(303)
            self.send_header("Location", approval)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return None
        selected = parse_qs(parts.query).get("incident", [None])[0]
        nonce = secrets.token_urlsafe(16)
        self._send(200, self.hub.render(nonce, selected).encode("utf-8"), "text/html; charset=utf-8", nonce=nonce)

    def do_POST(self) -> None:
        if not self._host_ok() or not self._origin_ok():
            return self._refuse(403, "bad host or origin")
        if urlsplit(self.path).path != "/chat":
            return self._json(404, {"error": "not found"})
        data = self._read_json()
        if data is None:
            return None
        token = data.get("token")
        if not isinstance(token, str) or not secrets.compare_digest(token.encode("utf-8"),
                                                                    self.hub.token.encode("utf-8")):
            return self._refuse(403, "bad token")
        question = data.get("question")
        if not isinstance(question, str) or not question.strip():
            return self._refuse(400, "empty question")
        t = self.hub.transcript(str(data.get("incident_id") or ""))
        if t is None:
            return self._refuse(404, "unknown incident")
        self._json(200, {"answer": self.hub.answer(t, question.strip()[:MAX_QUESTION_CHARS])})


def main() -> None:
    from ...config import Settings

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=None, help="default CHAT_UI_PORT (8799)")
    args = parser.parse_args()
    settings = Settings()
    hub = Hub(settings, port=settings.chat_ui_port if args.port is None else args.port)
    print(f"[HUB] Incident hub at {hub.url} (Ctrl+C to stop)", flush=True)
    try:
        hub.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        hub.shutdown()


if __name__ == "__main__":
    main()
