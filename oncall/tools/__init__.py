from __future__ import annotations

import importlib
import logging


def load_all() -> None:
    for module in ("traces", "metrics", "logs", "containers", "deploys", "triage_tool"):
        try:
            importlib.import_module(f"oncall.tools.{module}")
        except ModuleNotFoundError as exc:
            if exc.name == f"oncall.tools.{module}":
                logging.getLogger(__name__).warning("tool module is not available: %s", module)
            else:
                raise


from oncall.tools.registry import REGISTRY, tool

__all__ = ["REGISTRY", "load_all", "tool"]
