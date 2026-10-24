"""Tool registry: @register_tool records each tool and the schema the LLM sees."""

import functools
from collections.abc import Callable

from oncall.models import ToolResult, make_error, scrub_flags

TOOLS: dict[str, Callable[..., ToolResult]] = {}
TOOL_SCHEMAS: dict[str, dict] = {}


def _nullable(prop: dict) -> dict:
    kind = prop.get("type")
    if not isinstance(kind, str) or kind == "null":
        return prop
    nullable = {**prop, "type": [kind, "null"]}
    if "enum" in prop:
        nullable["enum"] = [*prop["enum"], None]
    return nullable


def register_tool(name: str, description: str, params: dict):
    """Register a tool under `name`.

    `params` holds JSON-schema "properties" and optional "required". The wrapped
    function never raises: any exception becomes make_error(...). Every result
    passes through scrub_flags() before it is returned.

    Optional parameters are advertised as nullable and a null argument means
    "use the default": some models send {"service": null} for "all services".
    """
    required = params.get("required", [])

    def decorator(fn: Callable[..., ToolResult]) -> Callable[..., ToolResult]:
        @functools.wraps(fn)
        def wrapper(**kwargs) -> ToolResult:
            kwargs = {k: v for k, v in kwargs.items() if v is not None}
            try:
                result = fn(**kwargs)
            except Exception as exc:  # noqa: BLE001
                result = make_error(name, kwargs, f"{type(exc).__name__}: {exc}")
            return scrub_flags(result)

        TOOLS[name] = wrapper
        TOOL_SCHEMAS[name] = {
            "name": name,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": {
                    key: prop if key in required else _nullable(prop)
                    for key, prop in params.get("properties", {}).items()
                },
                "required": required,
            },
        }
        return wrapper

    return decorator
