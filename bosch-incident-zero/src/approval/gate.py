"""Human approval gate for remediation actions.

ApprovalGate is the only code that can turn a recorded human APPROVED decision into an
ApprovedAction, and action backends accept nothing else.
"""
from __future__ import annotations

import getpass
import hashlib
import io
import json
import secrets
import select
import sys
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, Optional, TextIO

from ..agent.transcript import utc_now
from ..models.action import ApprovalStatus, RemediationAction

APPROVAL_TTL_SECONDS = 120
APPROVAL_TIMEOUT_SECONDS = 120
CHANNELS = ("cli", "chat_ui", "test")
ACTION_ROLE = "action"
ROLLBACK_ROLE = "rollback"


class ApprovalDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ApprovalError(Exception):
    """An ApprovedAction is forged, reused, expired or does not match the action it was issued for."""


@dataclass(frozen=True)
class HumanDecision:
    approved: bool
    approver: str
    channel: str
    decided_at: str
    note: str = ""
    irreversible_acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


ApprovalCallback = Callable[[RemediationAction], Any]

_GATE_KEY = object()
_ISSUED: Dict[str, str] = {}


def _fingerprint(action: RemediationAction) -> str:
    body = action.model_dump(mode="json", include={"action_id", "action_type", "target_service", "parameters"})
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


class ApprovedAction:
    """Proof that a human approved one exact action. Bound to its action_id and content, single use,
    and valid until expires_at. Only ApprovalGate can construct one."""

    __slots__ = ("_action", "_role", "_decision", "_issued_at", "_expires_at", "_clock", "_nonce", "_fingerprint")

    def __init__(self, action: RemediationAction, decision: HumanDecision, role: str, ttl_seconds: float,
                 clock: Callable[[], float], *, _key: object = None) -> None:
        if _key is not _GATE_KEY:
            raise ApprovalError("ApprovedAction can only be issued by ApprovalGate after a recorded human approval")
        if decision.approved is not True:
            raise ApprovalError("cannot issue an ApprovedAction for a decision that is not an approval")
        self._action = action.model_copy(deep=True)
        self._role = role
        self._decision = decision
        self._clock = clock
        self._issued_at = clock()
        self._expires_at = self._issued_at + ttl_seconds
        self._fingerprint = _fingerprint(self._action)
        self._nonce = secrets.token_hex(16)
        _ISSUED[self._nonce] = self._fingerprint

    @property
    def action(self) -> RemediationAction:
        return self._action.model_copy(deep=True)

    @property
    def action_id(self) -> str:
        return self._action.action_id

    @property
    def role(self) -> str:
        return self._role

    @property
    def decision(self) -> HumanDecision:
        return self._decision

    @property
    def expires_at(self) -> str:
        return datetime.fromtimestamp(self._expires_at, timezone.utc).isoformat(timespec="seconds")

    @property
    def irreversible_acknowledged(self) -> bool:
        return self._decision.irreversible_acknowledged

    @property
    def consumed(self) -> bool:
        return getattr(self, "_nonce", None) not in _ISSUED

    def redeem(self, role: str, expected_action_id: Optional[str] = None) -> RemediationAction:
        """Validate and consume the approval, returning the approved action. Raises ApprovalError."""
        nonce = getattr(self, "_nonce", None)
        if nonce is None or nonce not in _ISSUED:
            raise ApprovalError("approval was not issued by ApprovalGate or has already been used")
        if _ISSUED[nonce] != self._fingerprint or _fingerprint(self._action) != self._fingerprint:
            raise ApprovalError("action does not match the action the human approved")
        if expected_action_id is not None and expected_action_id != self._action.action_id:
            raise ApprovalError(f"approval is for action_id '{self._action.action_id}', "
                                f"not '{expected_action_id}'")
        if role != self._role:
            raise ApprovalError(f"approval covers the {self._role}, not the {role}")
        if self._clock() >= self._expires_at:
            _ISSUED.pop(nonce, None)
            raise ApprovalError(f"approval expired at {self.expires_at}")
        del _ISSUED[nonce]
        return self._action.model_copy(deep=True)


@dataclass
class ApprovalResult:
    decision: ApprovalDecision
    human: Optional[HumanDecision]
    action_token: Optional[ApprovedAction] = None
    rollback_token: Optional[ApprovedAction] = None
    reason: str = ""


def _as_decision(result: Any) -> HumanDecision:
    if isinstance(result, HumanDecision):
        if result.channel not in CHANNELS:
            return HumanDecision(False, result.approver, "test", utc_now(),
                                 f"rejected: unknown approval channel '{result.channel}'")
        if result.approved is True and not str(result.approver).strip():
            return HumanDecision(False, "", result.channel, utc_now(), "rejected: approval has no approver")
        return result
    if isinstance(result, bool):
        return HumanDecision(result, "test", "test", utc_now(), "boolean decision from an injected test callback")
    return HumanDecision(False, "unknown", "test", utc_now(),
                         f"rejected: unrecognised approval response of type {type(result).__name__}")


def _mark(action: RemediationAction, human: HumanDecision) -> None:
    for act in (action, action.rollback):
        if act is None:
            continue
        act.approval_status = ApprovalStatus.APPROVED if human.approved is True else ApprovalStatus.REJECTED
        act.approver = human.approver or None
        act.approved_at = human.decided_at
        act.approval_channel = human.channel


class ApprovalGate:
    """Asks a human through the callback; rejects on anything but an explicit approval."""

    def __init__(
        self,
        approval_callback: Optional[ApprovalCallback] = None,
        ttl_seconds: float = APPROVAL_TTL_SECONDS,
        clock: Callable[[], float] = time.time,
        rollback_ttl_seconds: Optional[float] = None,
    ) -> None:
        self.approval_callback = approval_callback
        self.ttl_seconds = ttl_seconds
        self.rollback_ttl_seconds = ttl_seconds if rollback_ttl_seconds is None else rollback_ttl_seconds
        self.clock = clock

    def review(self, action: RemediationAction) -> ApprovalResult:
        """Ask for one decision covering the action and its rollback; issue tokens only on approval."""
        if self.approval_callback is None:
            return ApprovalResult(ApprovalDecision.REJECTED, None, reason="no approval channel configured")
        try:
            human = _as_decision(self.approval_callback(action))
        except TimeoutError:
            human = HumanDecision(False, "unknown", "test", utc_now(), "approval timed out")
        except Exception as e:
            human = HumanDecision(False, "unknown", "test", utc_now(), f"approval channel failed: {e}")
        _mark(action, human)
        if human.approved is not True:
            return ApprovalResult(ApprovalDecision.REJECTED, human, reason=human.note or "rejected by human")
        if action.irreversible and not human.irreversible_acknowledged:
            human = replace(human, irreversible_acknowledged=True,
                            note=(human.note + "; " if human.note else "") + "approval covers the NO ROLLBACK warning")
        token = ApprovedAction(action, human, ACTION_ROLE, self.ttl_seconds, self.clock, _key=_GATE_KEY)
        rb_token = None
        if action.rollback is not None:
            rb_token = ApprovedAction(action.rollback, human, ROLLBACK_ROLE, self.rollback_ttl_seconds,
                                      self.clock, _key=_GATE_KEY)
        return ApprovalResult(ApprovalDecision.APPROVED, human, token, rb_token, reason=human.note)

    def request_approval(self, action: RemediationAction) -> ApprovalDecision:
        return self.review(action).decision


def describe_for_approval(action: RemediationAction) -> str:
    mode = "DRY RUN (nothing is changed)" if action.dry_run else "LIVE via the Action API"
    lines = [""]
    if action.irreversible:
        lines += ["!" * 78, f" NO ROLLBACK: a {action.action_type.value.lower().replace('_', ' ')} cannot be undone.",
                  " If it does not help, the incident is escalated to a human; nothing is reverted.", "!" * 78]
    lines += [
        "=" * 78,
        " HUMAN APPROVAL REQUIRED",
        "=" * 78,
        f" Action    : {action.action_type.value} -> '{action.target_service}' ({action.action_id})",
        f" Reason    : {action.parameters.get('reason') or action.description}",
        f" Mode      : {mode}",
    ]
    rb = action.rollback
    if rb is not None:
        lines.append(f" Rollback  : {rb.action_type.value} -> '{rb.target_service}' ({rb.action_id})")
        lines.append(f"             {rb.parameters.get('reason') or rb.description}")
        lines.append("             runs only if verification measures no recovery")
    elif action.irreversible:
        lines.append(" Rollback  : NONE - irreversible action, approving accepts that it cannot be undone")
    else:
        lines.append(" Rollback  : NONE (the action will not be executed)")
    lines.append("=" * 78)
    return "\n".join(lines)


def _os_user() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown-operator"


def _readline(stream: TextIO, timeout: float) -> str:
    try:
        fd = stream.fileno()
    except (AttributeError, OSError, ValueError, io.UnsupportedOperation):
        return stream.readline()
    ready, _, _ = select.select([fd], [], [], timeout)
    if not ready:
        raise TimeoutError
    return stream.readline()


def cli_approval_callback(
    timeout_seconds: float = APPROVAL_TIMEOUT_SECONDS,
    stdin: Optional[TextIO] = None,
    stdout: Optional[TextIO] = None,
    approver: Optional[str] = None,
) -> Callable[[RemediationAction], HumanDecision]:
    """Terminal y/N prompt. A non-interactive stdin, EOF, a timeout or any answer but y/yes rejects."""

    def prompt(action: RemediationAction) -> HumanDecision:
        inp = stdin or sys.stdin
        out = stdout or sys.stdout
        who = approver or _os_user()

        def reject(note: str) -> HumanDecision:
            out.write(f"\n[APPROVAL] REJECTED: {note}\n")
            out.flush()
            return HumanDecision(False, who, "cli", utc_now(), note)

        out.write(describe_for_approval(action) + "\n")
        isatty = getattr(inp, "isatty", None)
        if not (callable(isatty) and isatty()):
            return reject("stdin is not an interactive terminal")
        question = "the IRREVERSIBLE action" if action.irreversible else "the action AND its rollback"
        out.write(f" Approve {question}? Answer within {int(timeout_seconds)}s [y/N]: ")
        out.flush()
        try:
            line = _readline(inp, timeout_seconds)
        except TimeoutError:
            return reject(f"no answer within {int(timeout_seconds)}s (approval timeout)")
        if line == "":
            return reject("end of input (EOF)")
        if line.strip().lower() in ("y", "yes"):
            return HumanDecision(True, who, "cli", utc_now(), "approved at the terminal prompt",
                                 irreversible_acknowledged=action.irreversible)
        return reject(f"operator answered {line.strip()!r}")

    return prompt
