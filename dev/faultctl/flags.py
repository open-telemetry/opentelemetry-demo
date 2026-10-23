"""Flag faults, driven through the flag UI's HTTP API (the same one its web page uses).

GET  <base>/feature/api/read   -> {"flags": {...}}
POST <base>/feature/api/write  <- {"data": {...}}   replaces the WHOLE flag set

So every change is: read everything, change only the target flag, write it all back,
read again and compare. Flag names and variants come from that live read, never from files.
"""
import copy
from urllib.parse import urlparse

import requests

from dev.faultctl.catalog import Incident
from dev.faultctl.outcome import Outcome, Refused, Result

READ_PATH = "/feature/api/read"
WRITE_PATH = "/feature/api/write"
FRONT_DOOR_PATH = "/"

LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
CONNECT_TIMEOUT = 5
READ_TIMEOUT = 15
WRITE_TIMEOUT = 30


class HttpTimeout(Exception):
    pass


class HttpFailure(Exception):
    pass


class FlagError(Exception):
    """The live flag set is not what faultctl expects (missing flag, odd structure, ...)."""


def require_loopback(base_url: str) -> str:
    """Return the base URL without a trailing slash, or raise Refused if it is not this machine."""
    parsed = urlparse(base_url)
    if parsed.scheme not in ("http", "https") or parsed.hostname not in LOOPBACK_HOSTS:
        raise Refused(f"base URL {base_url!r} is not a loopback http(s) URL "
                      f"(allowed hosts: {', '.join(sorted(LOOPBACK_HOSTS))})")
    return base_url.rstrip("/")


class FlagUiHttp:
    """Thin HTTP client for the flag UI. Tests replace it with a fake that has the same methods."""

    def __init__(self, base_url: str, session: requests.Session | None = None):
        self.base_url = require_loopback(base_url)
        self.session = session or requests.Session()
        # Ignore proxy environment variables so loopback traffic can never be routed elsewhere.
        self.session.trust_env = False

    def _request(self, method: str, path: str, timeout: tuple[int, int], **kwargs) -> requests.Response:
        try:
            return self.session.request(method, self.base_url + path, timeout=timeout,
                                        allow_redirects=False, **kwargs)
        except requests.exceptions.Timeout as exc:
            raise HttpTimeout(f"{method} {path} timed out") from exc
        except requests.exceptions.RequestException as exc:
            raise HttpFailure(f"{method} {path}: {type(exc).__name__}") from exc

    def get_json(self, path: str) -> dict:
        response = self._request("GET", path, (CONNECT_TIMEOUT, READ_TIMEOUT))
        if not response.ok:
            raise HttpFailure(f"GET {path}: HTTP {response.status_code}")
        try:
            return response.json()
        except ValueError as exc:
            raise HttpFailure(f"GET {path}: response was not JSON") from exc

    def post_json(self, path: str, body: dict) -> None:
        response = self._request("POST", path, (CONNECT_TIMEOUT, WRITE_TIMEOUT), json=body)
        if not response.ok:
            raise HttpFailure(f"POST {path}: HTTP {response.status_code}")

    def get_status(self, path: str) -> int:
        """HTTP status code only; the body is never read."""
        return self._request("GET", path, (CONNECT_TIMEOUT, READ_TIMEOUT)).status_code


def read_flag_set(http) -> dict:
    data = http.get_json(READ_PATH)
    if not isinstance(data, dict) or not isinstance(data.get("flags"), dict):
        raise FlagError("flag UI returned an unexpected structure (no 'flags' object)")
    return data


def _branches(flag: dict) -> list | None:
    """The [condition, then, else] list of a targeting rule, or None for a plain switch.

    Only `{"if": [condition, "variantA", "variantB"]}` is understood; any other rule raises.
    """
    targeting = flag.get("targeting")
    if not targeting:
        return None
    rule = targeting.get("if") if isinstance(targeting, dict) and len(targeting) == 1 else None
    if isinstance(rule, list) and len(rule) == 3 and isinstance(rule[1], str) and isinstance(rule[2], str):
        return rule
    raise FlagError("flag has a targeting rule of a shape faultctl does not handle")


def current_variant(flag: dict) -> str:
    """The variant a flag is set to: a plain switch uses defaultVariant, a rule uses its 'then' branch.

    (With a rule that always yields a variant, defaultVariant is never consulted, so it
    cannot be the switch.)
    """
    rule = _branches(flag)
    return rule[1] if rule else flag.get("defaultVariant")


def with_variant(flag: dict, variant: str) -> dict:
    """A copy of the flag set to `variant`; nothing else about it changes."""
    new = copy.deepcopy(flag)
    rule = _branches(new)
    if rule:
        rule[1] = variant
    else:
        new["defaultVariant"] = variant
    return new


def set_flag(http, incident: Incident, variant: str, dry_run: bool) -> Result:
    """Put one flag on `variant` (idempotent), changing no other flag, and verify by reading back."""
    name = incident.target
    try:
        before = read_flag_set(http)
    except HttpTimeout:
        return Result(Outcome.FAILED, ["reading the flag set timed out; nothing was changed"], variant)
    except (HttpFailure, FlagError) as exc:
        return Result(Outcome.FAILED, [f"could not read the flag set: {exc}; nothing was changed"], variant)

    flag = before["flags"].get(name)
    if flag is None:
        return Result(Outcome.FAILED, [f"flag {name} is not in the live flag set"], variant)
    if flag.get("state") != "ENABLED":
        return Result(Outcome.REFUSED, [f"flag {name} is not ENABLED; faultctl does not change flag state"], variant)
    if variant not in flag.get("variants", {}):
        known = ", ".join(flag.get("variants", {}))
        return Result(Outcome.REFUSED, [f"flag {name} has no variant {variant!r} (live variants: {known})"], variant)
    try:
        was = current_variant(flag)
        new_flag = with_variant(flag, variant)
    except FlagError as exc:
        return Result(Outcome.REFUSED, [f"flag {name}: {exc}"], variant)

    if was == variant:
        note = f"flag {name} is already {variant!r}; no write needed"
        return Result(Outcome.DRY_RUN if dry_run else Outcome.VERIFIED, [note], variant)
    plan = f"flag {name}: {was!r} -> {variant!r} (read all, change only this flag, write all, re-read)"
    if dry_run:
        return Result(Outcome.DRY_RUN, [f"plan: {plan}"], variant)

    expected = copy.deepcopy(before)
    expected["flags"][name] = new_flag
    try:
        http.post_json(WRITE_PATH, {"data": expected})
    except HttpTimeout:
        return Result(Outcome.TIMED_OUT, [plan, "the write timed out and was NOT retried; "
                                          "its effect is unknown, check the flag UI"], variant)
    except HttpFailure as exc:
        return Result(Outcome.FAILED, [plan, f"the write failed: {exc}"], variant)

    try:
        after = read_flag_set(http)
    except (HttpTimeout, HttpFailure, FlagError) as exc:
        return Result(Outcome.UNVERIFIED, [plan, f"the write was accepted but the re-read failed: {exc}"], variant)
    if after == expected:
        return Result(Outcome.VERIFIED, [plan, "re-read matches: target flag changed, all others untouched"], variant)

    differing = sorted(k for k in set(after["flags"]) | set(expected["flags"])
                       if after["flags"].get(k) != expected["flags"].get(k))
    if name in differing:
        return Result(Outcome.FAILED, [plan, "the write was accepted but the re-read shows the target flag "
                                       "is not as written"], variant)
    detail = (f"flags differ from what was written: {', '.join(differing)}" if differing
              else "the set differs from what was written outside 'flags'")
    return Result(Outcome.UNVERIFIED, [plan, f"target flag is as written, but {detail}"], variant)
