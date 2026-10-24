"""Readiness checks and operator-owned configuration, without inference by default."""
from copy import deepcopy
from datetime import timedelta
import json
import os
from pathlib import Path

from incident_tools.eyes.runtime import load, Router
from incident_tools.f02 import ObservabilityTools
from incident_tools.f02.boundary import iso, utc_now

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/openai"
PLACEHOLDER = "YOUR_GEMINI_FLASH_MODEL"


def initialize(directory, model=PLACEHOLDER, project="opentelemetry-demo",
               prometheus="http://localhost:9090", jaeger="http://localhost:8080",
               opensearch=""):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).parents[1] / "f02" / "operator.example.toml"
    f02 = source.read_text(encoding="utf-8")
    for old, new in (('endpoint = "http://localhost:9090"', "endpoint = " + json.dumps(prometheus)),
                     ('endpoint = "http://localhost:8080"', "endpoint = " + json.dumps(jaeger)),
                     ('endpoint = ""', "endpoint = " + json.dumps(opensearch)),
                     ('project = "opentelemetry-demo"', "project = " + json.dumps(project))):
        f02 = f02.replace(old, new, 1)
    (directory / "f02.toml").write_text(f02, encoding="utf-8")
    eyes = '''f02_config = "f02.toml"
artifact_dir = "runs"

[workflow]
services = ["checkout"]
poll_seconds = 15
window_seconds = 300
warmup_seconds = 120
consecutive_breaches = 2
max_age_seconds = 90
min_requests = 10
max_calls = 8
max_seconds = 120
per_call_limit = 1

[workflow.thresholds]
latency_p95_ms = 1000

[models]
route = "cloud-only"

[models.cloud]
enabled = true
backend = "openai-compatible"
endpoint = ENDPOINT
model = MODEL
api_key_env = "GEMINI_API_KEY"
timeout_seconds = 30
retries = 1
requests_per_minute = 12
max_output_tokens = 2048
context_chars = 48000
temperature = 0.0
'''
    eyes = eyes.replace("ENDPOINT", json.dumps(GEMINI_ENDPOINT)).replace("MODEL", json.dumps(model))
    (directory / "eyes.toml").write_text(eyes, encoding="utf-8")
    return str(directory / "eyes.toml")


def readiness(config, live=False, probe_model=False, clock=utc_now):
    cfg, settings, f02_path, artifact_dir = load(config)
    tools = ObservabilityTools(f02_path)
    checks, issues, warnings = {}, [], []
    if not set(settings["services"]) <= set(tools.config.services):
        issues.append("MONITORED_SERVICES_OUTSIDE_F02_ALLOWLIST")
    if len(settings["services"]) != 1:
        issues.append("ACCEPTANCE_REQUIRES_ONE_MONITORED_SERVICE")
    if tools.config.origin != "backend":
        issues.append("LIVE_ACCEPTANCE_REQUIRES_BACKEND_ORIGIN")
    if tools.config.section("docker").get("transport", "native") != "native":
        issues.append("PRACTICE_RUN_REQUIRES_NATIVE_DOCKER_IN_UBUNTU")
    for backend in ("prometheus", "jaeger", "opensearch"):
        if not tools.config.section(backend).get("endpoint"):
            issues.append("CONFIGURE_" + backend.upper() + "_ENDPOINT")
    model_issues = []
    route = cfg.get("models", {}).get("route")
    order = {"cloud-only": ["cloud"], "local-only": ["local"],
             "local-first": ["local", "cloud"], "cloud-first": ["cloud", "local"]}.get(route, [])
    if not order:
        model_issues.append("INVALID_MODEL_ROUTE")
    for slot in order:
        provider = cfg["models"].get(slot, {})
        if not provider.get("model") or provider["model"] == PLACEHOLDER:
            model_issues.append("SET_" + slot.upper() + "_MODEL_ID")
        name = provider.get("api_key_env", "")
        if slot == "cloud" and (not name or not os.environ.get(name, "").strip()):
            model_issues.append("MISSING_" + slot.upper() + "_ENVIRONMENT_KEY")
        if name and os.environ.get(name):
            tools.config.secrets.append(os.environ[name])
    router = None
    if not model_issues:
        try:
            router = Router(deepcopy(cfg["models"]))
        except Exception:
            model_issues.append("INVALID_PROVIDER_CONFIGURATION")
    if live:
        end = clock()
        window = {"service": settings["services"][0],
                  "start": iso(end - timedelta(seconds=settings["window_seconds"])), "end": iso(end), "limit": 1}
        for name, extra in (("query_metrics", {"metric": "request_rate"}),
                            ("search_logs", {}), ("search_traces", {}),
                            ("container_health", {}), ("deployment_history", {})):
            result = tools.call(name, {**window, **extra})
            checks[name] = result
            usable = result.get("status") in ("ok", "partial") and bool(result.get("observations"))
            if name in ("query_metrics", "search_logs", "search_traces") and not usable:
                issues.append("NO_USABLE_" + name.upper())
            if result.get("status") != "ok":
                warnings.append(name + ": " + result.get("status", "unknown"))
    model_probe = None
    if probe_model and router:
        try:
            answer, identity = router.decide([
                {"role": "system", "content": 'Return exactly the JSON object {"ready":true}. No markdown.'},
                {"role": "user", "content": "Connection check only; no incident or telemetry."}], 45)
            if answer != {"ready": True}:
                raise ValueError("Probe response")
            model_probe = identity
        except Exception:
            model_issues.append("MODEL_PROBE_FAILED")
    result = {"configuration_usable": not issues, "model_configuration_usable": not model_issues,
              "issues": issues, "model_issues": model_issues, "warnings": warnings,
              "live_probes_executed": live, "model_probe": model_probe,
              "telemetry": checks, "artifact_dir": artifact_dir,
              "model_configuration": router.public_configuration if router else {},
              "note": "Configuration validation does not establish provider connectivity or live acceptance."}
    return result, tools, settings, router
