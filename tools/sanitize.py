"""Structural filters applied to every tool result before the ledger or the agent sees it.

This is the ONLY file allowed to name the flag service and the flag UI path. It removes:
  - any key (or {"key": ...} / {"name": ...} attribute or event entry) containing "feature_flag"
  - any series, container, log or span that belongs to the flag service or its UI
  - any value that points at the flag UI path
  - any text (log line, message, value) that mentions the flag service, "feature_flag",
    "feature flag" or "openfeature"
A removed value takes its enclosing list element with it (one log, one span, one series),
so a half-filtered record never reaches the agent. Everything removed is counted
(see clean_counted) and only the count is ever reported, never the removed content.
`clean_spans` applies the same rules to flat spans parsed from Jaeger's OTLP-style JSON.
"""
import re
from dataclasses import fields

# Names of the flag backend and its UI, as service / container names.
BLOCKED_SERVICES = {"flagd", "flagd-ui"}
FLAG_KEY_PREFIX = "feature_flag"  # matched anywhere in a key, so "demo.feature_flag.x" goes too

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

# Matches any text that talks about the flag system. "flagd" also covers "flagd-ui".
_FLAG_TEXT = re.compile(
    "|".join([*(re.escape(n) for n in sorted(BLOCKED_SERVICES, key=len, reverse=True)), r"feature[_ ]flag", "openfeature"]),
    re.IGNORECASE,
)
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
    """True for "feature_flag.key" and also for vendor-prefixed names like "demo.feature_flag.x"."""
    return isinstance(name, str) and FLAG_KEY_PREFIX in name.lower()


def has_flag_text(text) -> bool:
    """True when a string mentions the flag service, feature flags, OpenFeature or the flag UI path."""
    return isinstance(text, str) and bool(_FLAG_TEXT.search(text) or _FLAG_UI_PATH.search(text))


def _bad_key(key) -> bool:
    return _is_flag_key(key) or is_blocked_name(key) or has_flag_text(str(key))


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


class _Tally:
    """Counts what was removed. A dropped record takes the counts made inside it back out."""

    def __init__(self):
        self.n = 0


def _clean(obj, tally: _Tally):
    if isinstance(obj, str):
        return _DROP if has_flag_text(obj) else obj
    if isinstance(obj, list):
        out = []
        for element in obj:
            cleaned = _clean(element, tally)
            if cleaned is _DROP:
                tally.n += 1
            else:
                out.append(cleaned)
        return out
    if isinstance(obj, dict):
        if _belongs_to_blocked(obj):
            return _DROP
        mark = tally.n
        out = {}
        for key, value in obj.items():
            if _bad_key(key):
                tally.n += 1
                continue
            cleaned = _clean(value, tally)
            if cleaned is _DROP:
                tally.n = mark
                return _DROP  # poison travels up to the enclosing list element
            out[key] = cleaned
        return out
    return obj


def clean_counted(obj):
    """Like clean(), but also returns how many items (records, keys, lines) were removed."""
    tally = _Tally()
    if isinstance(obj, dict):
        # The top-level dict is not a list element: drop only the offending keys.
        out = {}
        for key, value in obj.items():
            if _bad_key(key):
                tally.n += 1
                continue
            cleaned = _clean(value, tally)
            if cleaned is _DROP:
                tally.n += 1
            else:
                out[key] = cleaned
        return out, tally.n
    cleaned = _clean(obj, tally)
    if cleaned is _DROP:
        return None, tally.n + 1
    return cleaned, tally.n


def clean(obj):
    """Return a filtered copy of any JSON-like structure (dicts, lists, strings, numbers)."""
    return clean_counted(obj)[0]


# --- OTLP-style spans (Jaeger v3) -------------------------------------------------------

# Span attributes that say where a client span was sent. If one of them names the flag
# service, the span is the flag-evaluation call (or its HTTP leg) and the whole span goes.
_TARGET_KEYS = {
    "server.address", "url.full", "http.url", "net.peer.name", "peer.service", "rpc.service",
    "http.host", "network.peer.address",
}


def attr_value(entry: dict):
    """The plain value of an OTLP attribute entry {"key": k, "value": {"stringValue": v}}."""
    value = entry.get("value")
    if isinstance(value, dict) and value:
        return next(iter(value.values()))
    return value


def _is_flag_span(span: dict) -> bool:
    if is_blocked_name(span.get("service")) or has_flag_text(span.get("scope")):
        return True
    if _FLAG_SPAN_NAME.match(str(span.get("name", ""))):
        return True
    return any(
        a.get("key") in _TARGET_KEYS and has_flag_text(str(attr_value(a)))
        for a in span.get("attributes", [])
    )


def clean_spans(spans: list[dict]) -> tuple[list[dict], int]:
    """Filter flat spans {service, scope, name, status, attributes: [...], events: [...]}.

    - flag-evaluation spans and spans of the flag service are dropped whole;
    - attribute/event entries containing "feature_flag" are removed, an event with such a name goes whole;
    - a status message or exception text that mentions the flag system is blanked rather
      than dropping the span, so a real error is never hidden (the blanking is counted).
    Returns (kept spans, number of items removed).
    """
    removed = 0
    kept = []
    for span in spans:
        if _is_flag_span(span):
            removed += 1
            continue
        span = dict(span)
        attributes = []
        for entry in span.get("attributes", []):
            if _bad_key(entry.get("key")) or has_flag_text(str(attr_value(entry))):
                removed += 1
            else:
                attributes.append(entry)
        span["attributes"] = attributes
        events = []
        for event in span.get("events", []):
            if _bad_key(event.get("name")):
                removed += 1
                continue
            event = dict(event)
            event_attrs = []
            for entry in event.get("attributes", []):
                if _bad_key(entry.get("key")):
                    removed += 1
                elif has_flag_text(str(attr_value(entry))):
                    removed += 1  # e.g. an exception message quoting the flag system
                else:
                    event_attrs.append(entry)
            event["attributes"] = event_attrs
            events.append(event)
        span["events"] = events
        status = dict(span.get("status") or {})
        if has_flag_text(status.get("message")):
            status.pop("message")
            removed += 1
        span["status"] = status
        kept.append(span)
    return kept, removed


def removal_note(count: int) -> str:
    return f"{count} items removed by sanitiser"


def clean_result(result):
    """Filter a ToolResult. If every item was filtered away, 'data' becomes 'no_data'."""
    cleaned, removed = clean_counted(result.to_dict())
    kwargs = {f.name: cleaned.get(f.name) for f in fields(result)}
    for name in ("items", "notes", "query"):
        kwargs[name] = kwargs[name] or []
    kwargs["extra"] = kwargs["extra"] or {}
    if removed:
        kwargs["notes"] = kwargs["notes"] + [removal_note(removed)]
    if kwargs["state"] == "data" and not kwargs["items"]:
        kwargs["state"] = "no_data"
        kwargs["notes"] = kwargs["notes"] + ["no items left after filtering"]
    return type(result)(**kwargs)
