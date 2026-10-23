import os
from pathlib import Path


def _resolve_data_dir() -> Path:
    env_dir = os.environ.get("ONCALL_DATA_DIR")
    if env_dir:
        return Path(env_dir)
    p = Path("/data")
    try:
        if p.exists() or p.parent.exists():
            p.mkdir(parents=True, exist_ok=True)
            return p
    except OSError:
        pass
    local_dir = Path("oncall-data/agent")
    local_dir.mkdir(parents=True, exist_ok=True)
    return local_dir


DATA_DIR = _resolve_data_dir()
MEMORY_SQLITE_PATH = Path(os.environ.get("ONCALL_SQLITE_PATH", DATA_DIR / "memory.sqlite"))

PROMETHEUS_URL = os.environ.get("ONCALL_PROMETHEUS_URL", "http://prometheus:9090")
JAEGER_URL = os.environ.get("ONCALL_JAEGER_URL", "http://jaeger:16686")
OPENSEARCH_URL = os.environ.get("ONCALL_OPENSEARCH_URL", "http://opensearch:9200")
ACTION_API_URL = os.environ.get("ONCALL_ACTION_API_URL", "http://action-api:8201")

HOST_FALLBACK_URLS = {
    "prometheus": os.environ.get("HOST_PROMETHEUS_URL", "http://localhost:9090"),
    "jaeger": os.environ.get("HOST_JAEGER_URL", "http://localhost:64371"),
    "opensearch": os.environ.get("HOST_OPENSEARCH_URL", "http://localhost:64368"),
    "action_api": os.environ.get("HOST_ACTION_API_URL", "http://localhost:8201"),
}
