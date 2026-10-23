"""Tool registry: @register_tool records each tool and the schema the LLM sees."""

import functools
from collections.abc import Callable

from oncall.models import ToolResult, make_error

TOOLS: dict[str, Callable[..., ToolResult]] = {}
TOOL_SCHEMAS: dict[str, dict] = {}


def register_tool(name: str, description: str, params: dict):
    """Register a tool under `name`.

    `params` holds JSON-schema "properties" and optional "required". The wrapped
    function never raises: any exception becomes make_error(...).
    """

    def decorator(fn: Callable[..., ToolResult]) -> Callable[..., ToolResult]:
        @functools.wraps(fn)
        def wrapper(**kwargs) -> ToolResult:
            try:
                return fn(**kwargs)
            except Exception as exc:  # noqa: BLE001
                return make_error(name, kwargs, f"{type(exc).__name__}: {exc}")

        TOOLS[name] = wrapper
        TOOL_SCHEMAS[name] = {
            "name": name,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": params.get("properties", {}),
                "required": params.get("required", []),
            },
        }
        return wrapper

    return decorator
