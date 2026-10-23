"""Structural filters applied to every tool result before the ledger or the agent sees it.

This is the ONLY file allowed to name the flag service and the flag UI path. It removes:
  - any key (or {"key": ...} attribute entry) starting with "feature_flag"
  - any series, container, log or span that belongs to the flag service or its UI
  - any value that points at the flag UI path
A removed value takes its enclosing list element with it (one log, one span, one series),
so a half-filtered record never reaches the agent.
"""
import re
from dataclasses import fields

# Names of the flag backend and its UI, as service / container names.
BLOCKED_SERVICES = {"flagd", "flagd-ui"}
FLAG_KEY_PREFIX = "feature_flag"

# Fields that name the service, container or job a record belongs to.
IDENTITY_KEYS = {
    "service", "service_name", "service.name", "servicename", "container", "container_name",
    "compose_service", "com.docker.compose.service", "job", "name",
}
# Fields whose value names an attribute/event, as in Jaeger tags: {"key": "feature_flag.key"}.
ATTRIBUTE_NAME_KEYS = {"key", "event", "name"}

# Span/operation names of the flag-evaluation protocol, e.g. "<flag service>.evaluation.v2.Service/...".
# Every service that uses flags has client spans with these names; they carry flag keys and hints.
SPAN_NAME_KEYS = {"span_name", "operation", "operationname", "name"}
_FLAG_SPAN_NAME = re.compile(r"^(?:flagd|feature_flag)[./]", re.IGNORECASE)

# Matches the flag UI path "/feature", "/feature/...", "/feature?..." or "/feature HTTP" but
# not "/features" or "/feature-x" (the path must not continue with a word character or hyphen).
_FLAG_UI_PATH = re.compile(r"/feature(?![\w-])")
# Matches a compose-style container name for a blocked service: "<project>-<service>-<n>".
_COMPOSE_NAME = re.compile(r"^(?:[\w.-]+[-_])?flagd(?:-ui)?(?:[-_]\d+)?$")

_DROP = object()


def _normal(name: str) -> str:
    """Lower-case and strip docker's leading '/' and a 'namespace/' prefix (job names)."""
    return name.strip().lower().lstrip("/").rsplit("/", 1)[-1]


def is_blocked_name(name) -> bool:
    if not isinstance(name, str):
        return False
    normal = _normal(name)
    return normal in BLOCKED_SERVICES or bool(_COMPOSE_NAME.match(normal))


def _is_flag_key(name) -> bool:
    return isinstance(name, str) and name.strip().lower().startswith(FLAG_KEY_PREFIX)


def _belongs_to_blocked(record: dict) -> bool:
    for key, value in record.items():
        lowered = str(key).lower()
        if lowered in IDENTITY_KEYS and is_blocked_name(value):
            return True
        if lowered in ATTRIBUTE_NAME_KEYS and _is_flag_key(value):
            return True
        if lowered in SPAN_NAME_KEYS and isinstance(value, str) and _FLAG_SPAN_NAME.match(value):
            return True
    return False


def _clean(obj):
    if isinstance(obj, str):
        return _DROP if _FLAG_UI_PATH.search(obj) else obj
    if isinstance(obj, list):
        return [c for c in (_clean(e) for e in obj) if c is not _DROP]
    if isinstance(obj, dict):
        if _belongs_to_blocked(obj):
            return _DROP
        out = {}
        for key, value in obj.items():
            if _is_flag_key(key) or is_blocked_name(key) or _FLAG_UI_PATH.search(str(key)):
                continue
            cleaned = _clean(value)
            if cleaned is _DROP:
                return _DROP  # poison travels up to the enclosing list element
            out[key] = cleaned
        return out
    return obj


def clean(obj):
    """Return a filtered copy of any JSON-like structure (dicts, lists, strings, numbers)."""
    if isinstance(obj, dict):
        # The top-level dict is not a list element: drop only the offending keys.
        out = {}
        for key, value in obj.items():
            if _is_flag_key(key) or is_blocked_name(key) or _FLAG_UI_PATH.search(str(key)):
                continue
            cleaned = _clean(value)
            if cleaned is not _DROP:
                out[key] = cleaned
        return out
    cleaned = _clean(obj)
    return None if cleaned is _DROP else cleaned


def clean_result(result):
    """Filter a ToolResult. If every item was filtered away, 'data' becomes 'no_data'."""
    cleaned = clean(result.to_dict())
    kwargs = {f.name: cleaned.get(f.name) for f in fields(result)}
    for name in ("items", "notes", "query"):
        kwargs[name] = kwargs[name] or []
    kwargs["extra"] = kwargs["extra"] or {}
    if kwargs["state"] == "data" and not kwargs["items"]:
        kwargs["state"] = "no_data"
        kwargs["notes"] = kwargs["notes"] + ["no items left after filtering"]
    return type(result)(**kwargs)
