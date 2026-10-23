"""query_metrics(): per-service request rate, error rate and p95 latency from Prometheus.

Source: the collector's span metrics, `traces_span_metrics_calls_total` and
`traces_span_metrics_duration_milliseconds_bucket` (latency is in MILLISECONDS), keyed by
service_name / span_name / span_kind / status_code.

Why only SERVER and CONSUMER spans for the service-level numbers: a service emits INTERNAL
and CLIENT spans too (one request to `cart` also makes a CLIENT span per cache call), and
counting them all would inflate the request rate and blur the error rate. SERVER (and
CONSUMER, for Kafka workers that handle messages instead of requests) spans are the work
a service was asked to do. The per-span drill-down below uses ALL span kinds on purpose:
the span that errors first is often a CLIENT span pointing at the failing dependency.

Error rate = STATUS_CODE_ERROR calls / ALL calls. Most spans are STATUS_CODE_UNSET, so
dividing by STATUS_CODE_OK calls would be wrong.

Every service is also compared with a baseline: the same three figures over the 30 minutes
that end where the requested window starts (the same queries with a PromQL `offset`). The
comparison is written once, in code, as the row's `change` string, so a model can quote it.
"""
import math
import re
from datetime import timedelta
from itertools import zip_longest

import requests

from tools import sanitize
from tools.endpoints import get_endpoints
from tools.result import ToolResult, backend_error, utc_now, window_dict

TOOL = "query_metrics"
HTTP_TIMEOUT = 10
MIN_WINDOW_MINUTES = 2
BASELINE_MINUTES = 30
INBOUND_KINDS = 'span_kind=~"SPAN_KIND_SERVER|SPAN_KIND_CONSUMER"'
ERROR_STATUS = 'status_code="STATUS_CODE_ERROR"'
SERVICE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")  # keeps user input out of PromQL syntax
MAX_WORST = 5  # how many services get a top-erroring-spans drill-down
SPANS_PER_SERVICE = 3


class PromError(Exception):
    pass


def instant_query(base_url: str, promql: str, at: float, http_get=requests.get) -> list[tuple[dict, float | None]]:
    """Run one instant query. Returns [(labels, value)]; raises PromError on any failure."""
    try:
        response = http_get(
            f"{base_url}/api/v1/query", params={"query": promql, "time": at}, timeout=HTTP_TIMEOUT
        )
    except requests.exceptions.RequestException as exc:
        raise PromError(f"Prometheus unreachable: {type(exc).__name__}: {str(exc)[:120]}") from exc
    if not response.ok:
        detail = response.text[:150] if response.status_code == 400 else ""
        raise PromError(f"Prometheus returned HTTP {response.status_code} {detail}".strip())
    try:
        return parse_vector(response.json())
    except ValueError as exc:
        raise PromError(str(exc)) from exc


def parse_vector(body: dict) -> list[tuple[dict, float | None]]:
    """Read a Prometheus instant-vector response. NaN becomes None (e.g. p95 with no traffic)."""
    if not isinstance(body, dict) or body.get("status") != "success":
        raise ValueError(f"Prometheus status={body.get('status') if isinstance(body, dict) else None!r}")
    data = body.get("data", {})
    if data.get("resultType") != "vector":
        raise ValueError(f"unexpected result type {data.get('resultType')!r}")
    rows = []
    for series in data.get("result", []):
        raw = float(series["value"][1])
        rows.append((series["metric"], None if math.isnan(raw) else raw))
    return rows


def _by_label(rows, label: str) -> dict[str, float | None]:
    return {labels[label]: value for labels, value in rows if label in labels}


def error_rate_pct(error_rate: float | None, total_rate: float | None) -> float | None:
    """Errors / ALL calls, as a percentage. None (unknown) when there was no traffic."""
    if not total_rate:
        return None
    return round(100.0 * (error_rate or 0.0) / total_rate, 2)


def service_figures(calls, errors, p95) -> dict[str, dict]:
    """service -> the four figures of one period."""
    totals, errs, latency = _by_label(calls, "service_name"), _by_label(errors, "service_name"), _by_label(p95, "service_name")
    figures = {}
    for service, total in totals.items():
        err = errs.get(service, 0.0)  # no ERROR series at all means zero errors
        p = latency.get(service)
        figures[service] = {
            "request_rate_per_s": round(total or 0.0, 3),
            "error_rate_per_s": round(err or 0.0, 4),
            "error_rate_pct": error_rate_pct(err, total),
            "p95_ms": None if p is None else round(p, 1),
        }
    return figures


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}%"


def _ms(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.0f} ms" if value >= 10 else f"{value:.1f} ms"


def change_line(now: dict, before: dict | None) -> str:
    """One fixed-format sentence comparing a service now with its baseline."""
    if not before or not before["request_rate_per_s"]:
        return "baseline n/a"
    if not now["request_rate_per_s"]:
        return f"absent now (was {before['request_rate_per_s']:.2f}/s)"
    return (
        f"errors {_pct(before['error_rate_pct'])} -> {_pct(now['error_rate_pct'])}; "
        f"p95 {_ms(before['p95_ms'])} -> {_ms(now['p95_ms'])}; "
        f"rate {before['request_rate_per_s']:.2f}/s -> {now['request_rate_per_s']:.2f}/s"
    )


def build_service_rows(calls, errors, p95, base_calls=(), base_errors=(), base_p95=()) -> list[dict]:
    now, before = service_figures(calls, errors, p95), service_figures(base_calls, base_errors, base_p95)
    gone = {"request_rate_per_s": 0.0, "error_rate_per_s": 0.0, "error_rate_pct": None, "p95_ms": None}
    rows = []
    for service in [*now, *(s for s in before if s not in now)]:
        current, baseline = now.get(service, gone), before.get(service)
        rows.append({"service": service, **current, "baseline": baseline, "change": change_line(current, baseline)})
    return rows


def _absent(row: dict) -> bool:
    return row["change"].startswith("absent now")


def _error_rise(row: dict) -> float:
    """Rise in the error percentage over the baseline (no baseline counts as 0 %, i.e. plain error rate)."""
    return (row["error_rate_pct"] or 0) - ((row["baseline"] or {}).get("error_rate_pct") or 0)


def _p95_ratio(row: dict) -> float:
    before = (row["baseline"] or {}).get("p95_ms")
    return row["p95_ms"] / before if row["p95_ms"] and before else 1.0


def _worse_key(row: dict) -> tuple:
    """Most worsened first: error rise, then p95 ratio, then absent; ties fall back to the current figures."""
    return (-_error_rise(row), -_p95_ratio(row), not _absent(row), -(row["error_rate_pct"] or 0), -(row["p95_ms"] or 0))


def pick_worst(rows: list[dict], top_n: int) -> list[dict]:
    """Choose top_n rows, taking in turn the most absent, the worst error rise and the worst p95 ratio.

    Ranking by errors alone would hide a latency incident behind noise-level error rates.
    """
    absent = sorted((r for r in rows if _absent(r)), key=lambda r: -r["baseline"]["request_rate_per_s"])
    by_errors = sorted(rows, key=lambda r: (-_error_rise(r), -(r["error_rate_pct"] or 0)))
    by_latency = sorted(rows, key=lambda r: (-_p95_ratio(r), -(r["p95_ms"] or 0)))
    chosen: list[dict] = []
    for group in zip_longest(absent, by_errors, by_latency):
        for row in group:
            if row is not None and row not in chosen and len(chosen) < top_n:
                chosen.append(row)
    return sorted(chosen, key=_worse_key)


def erroring_spans(span_rows) -> list[dict]:
    """Every (service, span) with a non-zero error rate, worst first, flag-service rows removed."""
    spans = [{
        "service": labels["service_name"],
        "span_name": labels["span_name"],
        "span_kind": labels.get("span_kind", "").removeprefix("SPAN_KIND_").lower(),
        "error_rate_per_s": round(value, 4),
    } for labels, value in span_rows if value and "service_name" in labels and "span_name" in labels]
    return sanitize.clean(sorted(spans, key=lambda s: -s["error_rate_per_s"]))


def attach_error_spans(rows: list[dict], span_rows) -> None:
    """For the worst services with errors, add their top erroring span names (all span kinds)."""
    per_service: dict[str, list[dict]] = {}
    for labels, value in span_rows:
        if value and "service_name" in labels and "span_name" in labels:
            per_service.setdefault(labels["service_name"], []).append({
                "span_name": labels["span_name"],
                "span_kind": labels.get("span_kind", "").removeprefix("SPAN_KIND_").lower(),
                "error_rate_per_s": round(value, 4),
            })
    erroring = [r for r in rows if (r["error_rate_pct"] or 0) > 0][:MAX_WORST]
    for row in erroring:
        spans = sanitize.clean(sorted(per_service.get(row["service"], []), key=lambda s: -s["error_rate_per_s"]))
        row["top_error_spans"] = spans[:SPANS_PER_SERVICE]


def query_metrics(
    window_minutes: int = 5,
    service: str | None = None,
    top_n: int = 10,
    base_url: str | None = None,
    http_get=requests.get,
) -> ToolResult:
    # Prometheus scrapes once a minute, so rate() needs at least two samples: 2 minutes minimum.
    if not MIN_WINDOW_MINUTES <= window_minutes <= 120:
        raise ValueError(f"window_minutes must be between {MIN_WINDOW_MINUTES} and 120")
    if not 1 <= top_n <= 50:
        raise ValueError("top_n must be between 1 and 50")
    if service is not None and not SERVICE_NAME.match(service):
        raise ValueError(f"invalid service name {service!r}")

    now = utc_now()
    window = window_dict(window_minutes, now)
    baseline_window = window_dict(BASELINE_MINUTES, now - timedelta(minutes=window_minutes))
    w = f"{window_minutes}m"
    svc = f',service_name="{service}"' if service else ""

    def service_queries(range_: str, offset: str = "") -> list[str]:
        return [
            f'sum by (service_name) (rate(traces_span_metrics_calls_total{{{INBOUND_KINDS}{svc}}}[{range_}]{offset}))',
            f'sum by (service_name) (rate(traces_span_metrics_calls_total{{{INBOUND_KINDS},{ERROR_STATUS}{svc}}}[{range_}]{offset}))',
            'histogram_quantile(0.95, sum by (service_name, le) '
            f'(rate(traces_span_metrics_duration_milliseconds_bucket{{{INBOUND_KINDS}{svc}}}[{range_}]{offset})))',
        ]

    calls_q, errors_q, p95_q = service_queries(w)
    base_queries = service_queries(f"{BASELINE_MINUTES}m", f" offset {w}")
    spans_q = f'sum by (service_name, span_name, span_kind) (rate(traces_span_metrics_calls_total{{{ERROR_STATUS}{svc}}}[{w}]))'
    memory_q = (
        'container_memory_percent_ratio and on (container_name) '
        '(time() - timestamp(container_memory_percent_ratio) < 120)'
    )
    lag_q = "kafka_consumer_group_lag_sum_ratio"
    queries = [calls_q, errors_q, p95_q, spans_q, *base_queries]

    if base_url is None:
        endpoint = get_endpoints()["prometheus"]
        base_url = endpoint.url
    at = now.timestamp()
    try:
        calls = instant_query(base_url, calls_q, at, http_get)
        errors = instant_query(base_url, errors_q, at, http_get)
        p95 = instant_query(base_url, p95_q, at, http_get)
        span_rows = instant_query(base_url, spans_q, at, http_get)
        base_calls, base_errors, base_p95 = (instant_query(base_url, q, at, http_get) for q in base_queries)
    except PromError as exc:
        return backend_error(TOOL, queries, window, str(exc))

    rows = sanitize.clean(build_service_rows(calls, errors, p95, base_calls, base_errors, base_p95))
    if not rows:
        return ToolResult(
            TOOL, "no_data", queries, window,
            notes=["Prometheus answered but has no span-metric series for this window; this is NOT a healthy signal"],
        )

    chosen = pick_worst(rows, top_n)
    attach_error_spans(chosen, [(l, v) for l, v in span_rows if not sanitize.is_blocked_name(l.get("service_name"))])

    # Errors often show on a client span (a load generator, a proxy) rather than on the failing
    # service's own server span, so list the worst erroring spans across all services and kinds.
    extra = {"baseline_window": baseline_window}
    worst_spans = erroring_spans(span_rows)
    if worst_spans:
        extra["top_error_spans"] = worst_spans[:top_n]

    # Optional sections: included only when the series exist; a failure is a note, not fatal.
    notes = [
        "service rates count SERVER and CONSUMER spans only; top_error_spans covers all span kinds",
        f"change compares the requested window with the {BASELINE_MINUTES} minutes before it (baseline_window)",
        "container memory comes from collector metrics and can lag; container_health is authoritative",
    ]
    if not service:
        for key, promql, build in (
            ("container_memory_percent", memory_q, lambda r: sorted(
                [{"container": l.get("container_name"), "memory_percent": round(v, 1)} for l, v in r if v is not None],
                key=lambda x: -x["memory_percent"])),
            ("kafka_consumer_lag", lag_q, lambda r: sorted(
                [{"group": l.get("group"), "topic": l.get("topic"), "lag_messages": v} for l, v in r if v is not None],
                key=lambda x: -x["lag_messages"])),
        ):
            queries.append(promql)
            try:
                section = sanitize.clean(build(instant_query(base_url, promql, at, http_get)))
            except PromError as exc:
                notes.append(f"{key} unavailable: {exc}")
                continue
            if section:
                extra[key] = section[:top_n]

    return ToolResult(
        TOOL, "data", queries, window,
        items=chosen, total_items=len(rows), extra=extra, notes=notes,
    )
