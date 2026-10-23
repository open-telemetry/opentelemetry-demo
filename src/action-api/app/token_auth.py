import hashlib
import hmac
import json
import time
from typing import Any


def mint_approval_token(
    secret: str,
    incident_id: str,
    action: str,
    params: dict[str, Any],
    ttl_seconds: int = 900,
) -> str:
    exp = int(time.time()) + ttl_seconds
    payload = {
        "action": action,
        "exp": exp,
        "incident_id": incident_id,
        "params": params,
    }
    canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(secret.encode("utf-8"), canonical_bytes, hashlib.sha256).hexdigest()
    return f"{exp}:{sig}"


def verify_approval_token(
    secret: str,
    token: str | None,
    incident_id: str,
    action: str,
    params: dict[str, Any],
    exp_override: int | None = None,
) -> tuple[bool, str]:
    if not token or not isinstance(token, str):
        return False, "Approval token is required for mutating actions"

    token = token.strip()
    exp: int | None = None
    sig: str = ""

    if ":" in token:
        parts = token.split(":", 1)
        try:
            exp = int(parts[0])
            sig = parts[1]
        except ValueError:
            return False, "Malformed token: invalid expiration prefix"
    elif "." in token:
        parts = token.split(".", 1)
        try:
            exp = int(parts[0])
            sig = parts[1]
        except ValueError:
            return False, "Malformed token: invalid expiration prefix"
    else:
        sig = token
        exp = exp_override

    if exp is None:
        return False, "Missing token expiration time"

    now = int(time.time())
    if exp <= now:
        return False, f"Token expired at {exp} (current time {now})"

    payload = {
        "action": action,
        "exp": exp,
        "incident_id": incident_id,
        "params": params,
    }
    canonical_bytes = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    expected_sig = hmac.new(secret.encode("utf-8"), canonical_bytes, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(sig.lower(), expected_sig.lower()):
        return False, "Token signature mismatch"

    return True, ""
