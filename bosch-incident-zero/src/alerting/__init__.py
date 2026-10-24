"""Automatic alerting: detect unhealthy services from metrics and start an agent run."""
from .watcher import AgentLauncher, Alert, AlertWatcher, Rules, evaluate

__all__ = ["AgentLauncher", "Alert", "AlertWatcher", "Rules", "evaluate"]
