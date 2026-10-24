# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import importlib
import logging

try:
    from oncall.tools.registry import REGISTRY, tool
except ImportError:
    REGISTRY = None
    tool = None


def load_all() -> None:
    for module in ("services", "traces", "metrics", "logs", "containers", "deploys"):
        try:
            importlib.import_module(f"oncall.tools.{module}")
        except ModuleNotFoundError as exc:
            if exc.name == f"oncall.tools.{module}":
                logging.getLogger(__name__).warning("tool module is not available: %s", module)
            else:
                raise


from oncall.tools.prometheus import PrometheusTool
from oncall.tools.jaeger import JaegerTool
from oncall.tools.opensearch import OpenSearchTool
from oncall.tools.deployment_history import DeploymentHistoryTool

__all__ = [
    "REGISTRY",
    "load_all",
    "tool",
    "PrometheusTool",
    "JaegerTool",
    "OpenSearchTool",
    "DeploymentHistoryTool",
]
