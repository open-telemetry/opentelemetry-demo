"""Read-only tools the agent can call. Each tool module registers itself on import."""

from oncall.tools.registry import TOOL_SCHEMAS, TOOLS, register_tool

__all__ = ["TOOLS", "TOOL_SCHEMAS", "register_tool"]

# --- tool imports ---
import oncall.platform.containers  # noqa: F401
