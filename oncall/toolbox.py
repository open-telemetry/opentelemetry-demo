"""The five telemetry tools as the model sees them: JSON schemas, argument checks, compact views.

Schemas are generated from each tool's typed signature (`inspect`), so a parameter added to a
tool shows up here without a second list to keep in sync. Only the parameters in EXPOSED are
offered to the model; the rest (base_url, http_get, runner, ...) are test hooks.

A compact view is a PROJECTION of the ledger entry: it drops keys and rows and never rewrites a
value. Every string or number in a view is therefore also in the ledger entry (the id aside), so
a quote copied from a view can later be matched against the ledger exactly.
"""
import inspect
import json
import types
import typing
from dataclasses import dataclass

from oncall.llm import ToolSpec
from tools import containers, deploys, logs, metrics, traces
from tools.ledger import LedgerEntry
from tools.result import ToolResult, backend_error

HIGH_CPU_PCT = 90  # a running container at or above these percentages is shown as abnormal; memory is higher
HIGH_MEMORY_PCT = 97  # because several healthy JVM containers sit above 90% of their limit all the time
SANITISER_NOTE = "removed by sanitiser"  # a note about filtering is of no use to the model


class ArgumentError(Exception):
    """The model sent arguments the tool cannot take. The message goes back to the model."""


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    fn: typing.Callable
    exposed: tuple[str, ...]
    defaults: dict  # used when the model leaves a parameter out; recorded in the ledger as the arguments

    def spec(self) -> ToolSpec:
        return ToolSpec(self.name, self.description, schema_from_signature(self))


# Per-parameter text and limits shown to the model. The limits mirror the tool modules' own constants.
PARAMS = {
    "window_minutes": {
        "query_metrics": ("How many minutes back to look.", metrics.MIN_WINDOW_MINUTES, 120),
        "query_traces": ("How many minutes back to look.", 1, traces.MAX_WINDOW_MINUTES),
        "query_logs": ("How many minutes back to look.", 1, logs.MAX_WINDOW_MINUTES),
    },
    "service": {
        "query_metrics": ("Only this service (omit for all services).",),
        "query_traces": ("Only traces that touch this service (omit for all).",),
        "query_logs": ("Only this service (omit for all).",),
    },
    "top_n": {"query_metrics": ("How many services to return, worst first.", 1, 10)},
    "limit": {
        "query_traces": ("How many traces to return.", 1, traces.MAX_LIMIT),
        "query_logs": ("How many message groups to return.", 1, logs.MAX_LIMIT),
    },
    "mode": {"query_traces": ("'errors' = traces with errors, 'slow' = slowest traces.",)},
}
ENUMS = {("query_traces", "mode"): ["errors", "slow"]}

_JSON_TYPES = {int: "integer", str: "string", float: "number", bool: "boolean"}


def _json_type(annotation) -> str:
    """int -> 'integer', 'str | None' -> 'string' (optionality is expressed by not being required)."""
    if isinstance(annotation, types.UnionType) or typing.get_origin(annotation) is typing.Union:
        annotation = next(a for a in typing.get_args(annotation) if a is not type(None))
    return _JSON_TYPES[annotation]


def schema_from_signature(tool: Tool) -> dict:
    signature = inspect.signature(tool.fn)
    hints = typing.get_type_hints(tool.fn)
    properties, required = {}, []
    for name in tool.exposed:
        parameter = signature.parameters[name]
        docs = PARAMS.get(name, {}).get(tool.name, ("",))
        prop = {"type": _json_type(hints[name]), "description": docs[0]}
        if len(docs) == 3:
            prop["minimum"], prop["maximum"] = docs[1], docs[2]
        if (tool.name, name) in ENUMS:
            prop["enum"] = ENUMS[(tool.name, name)]
        default = tool.defaults.get(name, parameter.default)
        if default is inspect.Parameter.empty:
            required.append(name)
        elif default is not None:
            prop["default"] = default
        properties[name] = prop
    return {"type": "object", "properties": properties, "required": required, "additionalProperties": False}


def _tool(name, fn, description, exposed=(), defaults=None) -> Tool:
    return Tool(name, description, fn, tuple(exposed), defaults or {})


TOOLS: dict[str, Tool] = {t.name: t for t in (
    _tool("container_health", containers.container_health,
          "State of every container of the application: status, health, restart count, exit code, OOM kill, CPU and "
          "memory. The only way to see a stopped or crash-looping container, because a stopped container emits no "
          "metrics. Returns a summary and only the abnormal containers."),
    _tool("query_metrics", metrics.query_metrics,
          "Per-service request rate, error rate (%) and p95 latency (ms) over the last N minutes, worst first, with "
          "the top erroring spans of each failing service. Compare a short and a long window to see what changed.",
          ("window_minutes", "service", "top_n"), {"window_minutes": 5, "top_n": 6}),
    _tool("query_traces", traces.query_traces,
          "Recent error traces (mode 'errors') or the slowest traces (mode 'slow'): real trace IDs, root service and "
          "the deepest erroring span, which is where an error starts. Error traces are also grouped by where they start.",
          ("service", "window_minutes", "limit", "mode"), {"limit": 4}),
    _tool("query_logs", logs.query_logs,
          "Top error log lines over the last N minutes, grouped by service and exact message, with counts and "
          "first/last seen times and a sample trace ID. Messages are verbatim.",
          ("service", "window_minutes", "limit"), {"limit": 6}),
    _tool("deploy_history", deploys.deploy_history,
          "When containers last started or restarted. Lists only containers marked as restarted recently, plus a "
          "summary. A restart of the whole stack makes start times uninformative; the result says when that applies."),
)}


def validate_arguments(tool: Tool, arguments: dict) -> dict:
    """Check names and types, drop nulls, fill defaults. Range errors are left to the tool itself."""
    if not isinstance(arguments, dict):
        raise ArgumentError("arguments must be a JSON object")
    unknown = sorted(set(arguments) - set(tool.exposed))
    if unknown:
        raise ArgumentError(f"unknown argument(s) {unknown}; {tool.name} takes {list(tool.exposed) or 'no arguments'}")
    schema = schema_from_signature(tool)["properties"]
    given = {k: v for k, v in arguments.items() if v is not None}
    for name, value in given.items():
        expected = schema[name]["type"]
        is_int = isinstance(value, int) and not isinstance(value, bool)
        ok = {"integer": is_int, "string": isinstance(value, str), "number": is_int or isinstance(value, float),
              "boolean": isinstance(value, bool)}[expected]
        if not ok:
            raise ArgumentError(f"argument {name!r} must be of type {expected}, got {value!r}")
        if "enum" in schema[name] and value not in schema[name]["enum"]:
            raise ArgumentError(f"argument {name!r} must be one of {schema[name]['enum']}")
    return {**{k: v for k, v in tool.defaults.items() if k in tool.exposed}, **given}


def call_tool(tool: Tool, arguments: dict) -> ToolResult:
    """Run a tool. ValueError (bad range, bad name) becomes ArgumentError; any other crash becomes a backend_error result."""
    try:
        return tool.fn(**arguments)
    except ValueError as exc:
        raise ArgumentError(str(exc)) from exc
    except Exception as exc:  # a tool must never take the whole run down
        return backend_error(tool.name, [f"{tool.name}({json.dumps(arguments, sort_keys=True)})"], {},
                             f"{type(exc).__name__}: {str(exc)[:150]}")


# --- compact views --------------------------------------------------------------------------

def _pick(row: dict, keys) -> dict:
    return {k: row[k] for k in keys if row.get(k) is not None}


def _notes(notes: list[str], *needles: str) -> list[str]:
    return [n for n in notes if any(needle in n for needle in needles)]


def _abnormal_container(row: dict) -> bool:
    return (
        row["status"] != "running"
        or row["health"] not in containers.GOOD_HEALTH
        or row["restart_count"] > 0
        or row["oom_killed"]
        or (row.get("cpu_percent") or 0) >= HIGH_CPU_PCT
        or (row.get("memory_percent") or 0) >= HIGH_MEMORY_PCT
    )


def _container_view(r: dict) -> dict:
    summary = r["extra"].get("summary", {})
    return {
        "at": r["window"].get("at"),
        "summary": {k: v for k, v in summary.items() if k in ("total", "running") or v},
        "abnormal": [
            _pick(c, ("name", "status", "health", "restart_count", "exit_code", "oom_killed",
                      "cpu_percent", "memory_percent", "started_at", "finished_at"))
            for c in r["items"] if _abnormal_container(c)],
    }


def _metrics_view(r: dict) -> dict:
    rows = []
    for s in r["items"]:
        row = _pick(s, ("service", "request_rate_per_s", "error_rate_pct", "p95_ms"))
        if s.get("top_error_spans"):
            row["top_error_spans"] = [_pick(e, ("span_name", "span_kind", "error_rate_per_s")) for e in s["top_error_spans"]]
        rows.append(row)
    view = {"window": r["window"], "services": rows, "services_total": r["total_items"]}
    extra = r["extra"]
    if extra.get("top_error_spans"):
        view["worst_error_spans"] = [_pick(e, ("service", "span_name", "span_kind", "error_rate_per_s"))
                                     for e in extra["top_error_spans"][:5]]
    for key in ("container_memory_percent", "kafka_consumer_lag"):
        if extra.get(key):
            view[key] = extra[key][:3]
    return view


def _traces_view(r: dict) -> dict:
    items = []
    for t in r["items"]:
        item = _pick(t, ("trace_id", "start", "root_service", "root_operation", "duration_ms", "span_count", "error_span_count"))
        if t.get("deepest_error"):
            item["deepest_error"] = _pick(t["deepest_error"], ("service", "span", "kind", "why", "message"))
        items.append(item)
    view = {"window": r["window"], "traces": items, "traces_total": r["total_items"]}
    if r["extra"].get("error_groups"):
        view["error_groups"] = r["extra"]["error_groups"][:5]
    return view


def _logs_view(r: dict) -> dict:
    return {"window": r["window"], "lines": r["items"], "groups_total": r["total_items"]}


def _deploys_view(r: dict) -> dict:
    summary = r["extra"].get("summary", {})
    return {
        "summary": summary,
        "restarted_recently": [
            _pick(c, ("name", "status", "started_at", "age_seconds", "restart_count"))
            for c in r["items"] if c.get("restarted_recently")],
    }


VIEWS = {
    "container_health": (_container_view, ()),
    "query_metrics": (_metrics_view, ()),
    "query_traces": (_traces_view, ("ranked among",)),
    "query_logs": (_logs_view, ("counts cover",)),
    "deploy_history": (_deploys_view, ("whole-stack",)),
}


def compact_view(entry: LedgerEntry) -> dict:
    """What the model is shown for one ledger entry. Unknown tools fall back to the state only."""
    r = entry.result
    view = {"id": entry.id, "state": r["state"]}
    if r["state"] != "data":
        # A failure or an empty answer is stated outright; the tool's own notes explain it.
        if r.get("error"):
            view["error"] = r["error"]
        view["notes"] = [n for n in r.get("notes", []) if SANITISER_NOTE not in n]
        return view
    build, note_needles = VIEWS[entry.tool]
    view.update(build(r))
    notes = _notes(r.get("notes", []), *note_needles)
    if notes:
        view["notes"] = notes
    return view


def view_text(view: dict) -> str:
    return json.dumps(view, separators=(",", ":"))


# --- one-line findings (for the step list; built from the view, not written by the model) ----

def _short(text: str, width: int = 90) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def finding_line(view: dict, tool: str) -> str:
    if view["state"] != "data":
        return f"{view['id']}: {view['state']} - {_short(view.get('error') or ' '.join(view.get('notes', [])), 120)}"
    if tool == "container_health":
        s = view["summary"]
        parts = [f"{s['running']}/{s['total']} running"]
        parts += [f"{k.replace('_', ' ')}: {', '.join(v)}" for k, v in s.items() if isinstance(v, list)]
        if not view["abnormal"]:
            parts.append("none abnormal")
        text = "; ".join(parts)
    elif tool == "query_metrics":
        failing = [f"{s['service']} {s['error_rate_pct']}%" for s in view["services"] if s.get("error_rate_pct")]
        slow = max((s for s in view["services"] if s.get("p95_ms") is not None), key=lambda s: s["p95_ms"], default=None)
        text = ("errors: " + ", ".join(failing[:3])) if failing else "no service with errors"
        if slow:
            text += f"; slowest p95: {slow['service']} {slow['p95_ms']} ms"
    elif tool == "query_traces":
        groups = view.get("error_groups")
        if groups:
            g = groups[0]
            text = f"{view['traces_total']} traces; most common deepest error: {g['deepest_service']} / {g['deepest_span']} (x{g['traces']})"
        else:  # slow mode: the first trace is the slowest
            t = view["traces"][0]
            text = f"{view['traces_total']} traces; slowest {t['root_service']}:{t['root_operation']} {t['duration_ms']} ms"
    elif tool == "query_logs":
        top = view["lines"][:2]
        text = "; ".join(f"x{g['count']} {g['service']}: {_short(g['message'], 55)}" for g in top)
    elif tool == "deploy_history":
        flagged = [c["name"] for c in view["restarted_recently"]]
        text = ("restarted recently: " + ", ".join(flagged)) if flagged else "no container marked as restarted recently"
    else:
        text = "ok"
    return f"{view['id']}: {_short(text, 150)}"
