"""Preview the approval page for a stored transcript; prints the decision and executes nothing.

    python -m src.approval.chat_ui incident_output/<incident>/transcript.json [--timeout 120] [--port 8799] [--open]
"""
from __future__ import annotations

import argparse
import dataclasses
import json
from pathlib import Path

from ...agent.transcript import Transcript
from ...config import Settings
from ...models.action import ActionType, RemediationAction
from .server import ui_approval_callback


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("transcript", type=Path)
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--port", type=int, default=8799, help="0 picks a free port; the URL is printed")
    parser.add_argument("--open", action="store_true", help="open the page in the default browser")
    parser.add_argument("--keep-alive", action="store_true",
                        help="serve a fresh page after every decision or timeout until Ctrl+C")
    args = parser.parse_args()

    raw = json.loads(args.transcript.read_text(encoding="utf-8"))
    names = {f.name for f in dataclasses.fields(Transcript)}
    transcript = Transcript(**{k: v for k, v in raw.items() if k in names})
    root = (transcript.diagnosis or {}).get("root_cause") or {}
    remediation = (transcript.report or {}).get("remediation") or {}
    action = RemediationAction(
        action_id=f"PREVIEW-{transcript.incident_id}", action_type=ActionType.RESTART_SERVICE,
        target_service=root.get("service") or "unknown",
        description=remediation.get("recommended_action") or "preview only",
        parameters={"reason": root.get("summary") or "preview only"}, dry_run=True)
    hook = ui_approval_callback(transcript, Settings(), timeout_seconds=args.timeout, port=args.port,
                                open_browser=args.open)
    while True:
        decision = hook(action)
        print("[APPROVAL] decision:", json.dumps(vars(decision), default=str), flush=True)
        if not args.keep_alive or decision.note == "interrupted" or decision.note.startswith("approval UI failed"):
            break


if __name__ == "__main__":
    main()
