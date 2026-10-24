"""Central settings. Everything can be overridden with environment variables / .env."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
RUNS.mkdir(exist_ok=True)


def _f(name, default):
    return float(os.getenv(name, default))


# --- Telemetry backends (read-only) ---
PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
JAEGER_URL = os.getenv("JAEGER_URL", "http://localhost:8080/jaeger/ui")
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "")  # empty -> auto-discover with `docker port opensearch 9200`
OPENSEARCH_INDEX = os.getenv("OPENSEARCH_INDEX", "otel-logs-*")
HTTP_TIMEOUT = _f("HTTP_TIMEOUT", "8")

# --- Analysis windows ---
WINDOW = os.getenv("WINDOW", "5m")
BASELINE_OFFSET = os.getenv("BASELINE_OFFSET", "30m")

# --- Detection thresholds (the "alert") ---
ALERT_ERROR_RATE = _f("ALERT_ERROR_RATE", "0.05")      # >=5% server-span errors ...
ALERT_ERROR_DELTA = _f("ALERT_ERROR_DELTA", "0.03")    # ... and +3pp over baseline
ALERT_P95_FACTOR = _f("ALERT_P95_FACTOR", "2.5")       # p95 >= 2.5x baseline ...
ALERT_P95_MIN_MS = _f("ALERT_P95_MIN_MS", "500")       # ... and >= 500 ms
ALERT_CONSECUTIVE = int(os.getenv("ALERT_CONSECUTIVE", "2"))  # polls in a row before firing
POLL_SECONDS = int(os.getenv("POLL_SECONDS", "20"))

# --- Decision policy ---
CONFIDENCE_TO_ACT = _f("CONFIDENCE_TO_ACT", "0.6")     # below this: escalate, never act
MAX_TOOL_CALLS = int(os.getenv("MAX_TOOL_CALLS", "14"))

# --- LLM (any OpenAI-compatible /chat/completions endpoint: OpenAI, Gemini, Groq, Ollama...) ---
LLM_API_KEY = os.getenv("LLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
LLM_BASE_URL = (os.getenv("LLM_BASE_URL", "") or "https://api.openai.com/v1/").rstrip("/") + "/"
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_TIMEOUT = _f("LLM_TIMEOUT", "45")
# tried in order when LLM_MODEL is overloaded (503), missing (404) or times out
LLM_FALLBACK_MODELS = [m.strip() for m in os.getenv("LLM_FALLBACK_MODELS", "").split(",") if m.strip()]
LLM_REASONING_EFFORT = os.getenv("LLM_REASONING_EFFORT", "")   # e.g. low / none for Gemini thinking models

# --- HANDS: Action API (the ONLY way the agent changes the system) ---
ACTION_API_URL = os.getenv("ACTION_API_URL", "http://localhost:8000").rstrip("/")
ACTION_API_TOKEN = os.getenv("ACTION_API_TOKEN", "")
ACTION_API_MODE = os.getenv("ACTION_API_MODE", "http")   # http | mock (mock = offline tests only)
VERIFY_SECONDS = int(os.getenv("VERIFY_SECONDS", "240"))  # how long to watch for recovery
VERIFY_WINDOW = os.getenv("VERIFY_WINDOW", "1m")          # short rate window so recovery shows quickly
VERIFY_POLL = int(os.getenv("VERIFY_POLL", "20"))

# --- Kill switch: if this file exists, NO action is executed (checked before every call) ---
KILL_FILE = RUNS / "KILL"

# --- Optional organisers' JSON schema (drop their file here and it is enforced) ---
OUTPUT_SCHEMA_FILE = ROOT / "config" / "output_schema.json"
