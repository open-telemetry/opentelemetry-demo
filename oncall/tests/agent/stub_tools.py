"""Stub tools whose output depends on their arguments, for loop tests."""

from oncall.models import make_result

TS = "2026-10-23T10:00:00Z"
HOT_SERVICE = "cart"


def stub_get_metrics(service: str | None = None):
    if service is None:
        return make_result(
            "stub_get_metrics",
            {},
            f"error rate by service: {HOT_SERVICE}=0.31, frontend=0.02",
            [
                {
                    "id": f"metric:error_rate@{TS}",
                    "text": f"{HOT_SERVICE} 0.31",
                    "ts": TS,
                }
            ],
        )
    return make_result(
        "stub_get_metrics", {"service": service}, f"{service} error rate 0.31", []
    )


def stub_search_traces(service: str):
    if service == HOT_SERVICE:
        return make_result(
            "stub_search_traces",
            {"service": service},
            f"{service}: 12 error traces, top span GetCart status ERROR",
            [{"id": "trace:abc123/span:GetCart", "text": "GetCart ERROR", "ts": TS}],
        )
    return make_result(
        "stub_search_traces", {"service": service}, f"{service}: no errors", []
    )


def stub_search_logs(service: str):
    return make_result(
        "stub_search_logs",
        {"service": service},
        f"{service}: 'connection refused' x40",
        [{"id": f"log:{service}@{TS}", "text": "connection refused", "ts": TS}],
    )


STUB_TOOLS = {
    "stub_get_metrics": stub_get_metrics,
    "stub_search_traces": stub_search_traces,
    "stub_search_logs": stub_search_logs,
}


def _schema(name: str, props: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": f"{name} stub",
        "input_schema": {"type": "object", "properties": props, "required": required},
    }


SERVICE = {"service": {"type": "string"}}
STUB_SCHEMAS = {
    "stub_get_metrics": _schema("stub_get_metrics", SERVICE, []),
    "stub_search_traces": _schema("stub_search_traces", SERVICE, ["service"]),
    "stub_search_logs": _schema("stub_search_logs", SERVICE, ["service"]),
}
