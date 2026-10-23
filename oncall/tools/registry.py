from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from typing import Any, Callable

from oncall.contracts import ToolOutput
from oncall.guard import is_banned_text
from oncall.ledger import EvidenceLedger


@dataclass
class ToolDefinition:
    name: str
    description: str
    params: dict[str, dict[str, Any]]
    required: list[str]
    function: Callable[..., ToolOutput]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, definition: ToolDefinition) -> None:
        self._tools[definition.name] = definition

    def openai_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": item.name,
                    "description": item.description,
                    "parameters": {
                        "type": "object",
                        "properties": item.params,
                        "required": item.required,
                    },
                },
            }
            for item in self._tools.values()
        ]

    def call(self, name: str, args: dict[str, Any], ledger: EvidenceLedger) -> str:
        definition = self._tools.get(name)
        if definition is None:
            return f"Error: unknown tool {name}"
        error = self._validate(definition, args)
        if error:
            return f"Error: {error}"
        if _contains_banned_text(args):
            return "Error: banned text in tool arguments"
        try:
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(definition.function, **args)
                result = future.result(timeout=20)
        except TimeoutError:
            return "Error: tool timed out after 20 seconds"
        except Exception as exc:
            result = ToolOutput(ok=False, text="", error=str(exc))
        query = json.dumps(args, sort_keys=True, default=str)
        tags = [f"[{ledger.add(name, query, fact).id}]" for fact in result.facts]
        if tags:
            suffix = f" {' '.join(tags)}"
            text = f"{result.text[: max(0, 1800 - len(suffix))]}{suffix}".strip()
        else:
            text = result.text[:1800]
        if result.error and not result.ok:
            text = f"{text} Error: {result.error}".strip()
        logging.getLogger(__name__).debug("tool_result name=%s ok=%s", name, result.ok)
        return text[:1800]

    @staticmethod
    def _validate(definition: ToolDefinition, args: dict[str, Any]) -> str | None:
        missing = [key for key in definition.required if key not in args]
        if missing:
            return f"missing required arguments: {', '.join(missing)}"
        for key in args:
            if key not in definition.params:
                return f"unexpected argument: {key}"
            expected = definition.params[key].get("type")
            value = args[key]
            if expected == "string" and not isinstance(value, str):
                return f"argument {key} must be a string"
            if expected == "integer" and (not isinstance(value, int) or isinstance(value, bool)):
                return f"argument {key} must be an integer"
        return None


REGISTRY = ToolRegistry()


def tool(
    name: str,
    description: str,
    params: dict[str, dict[str, Any]],
    required: list[str] | None = None,
) -> Callable[[Callable[..., ToolOutput]], Callable[..., ToolOutput]]:
    def decorate(function: Callable[..., ToolOutput]) -> Callable[..., ToolOutput]:
        REGISTRY.register(ToolDefinition(name, description, params, required or [], function))
        return function

    return decorate


def _contains_banned_text(value: Any) -> bool:
    if isinstance(value, str):
        return is_banned_text(value)
    if isinstance(value, dict):
        return any(_contains_banned_text(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_banned_text(item) for item in value)
    return False
