"""Read-only tools the agent can call. Each tool module registers itself on import."""

import oncall.platform.containers
from oncall.platform import deploys  # noqa: F401
from oncall.tools.logs import search_logs
from oncall.tools.metrics import get_metrics
from oncall.tools.registry import TOOL_SCHEMAS, TOOLS, register_tool

__all__ = ["TOOLS", "TOOL_SCHEMAS", "get_metrics", "register_tool", "search_logs"]

# --- tool imports ---
import oncall.tools.metrics  # noqa: F401
