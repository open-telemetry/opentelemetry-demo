"""Environment and dependency verification script for Bosch Incident Zero.

Checks:
- Python runtime version (>=3.11)
- Installed python packages
- Docker daemon reachability
- Observability and Demo endpoint availability
- Kill-switch status and configuration validity
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict
from urllib.parse import urlsplit

root_dir = Path(__file__).resolve().parents[1]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.config import Settings
from src.telemetry.discovery import docker_host_url


def check_python_version() -> Dict[str, Any]:
    v = sys.version_info
    passed = (v.major == 3 and v.minor >= 11)
    return {
        "check": "Python Version",
        "passed": passed,
        "detail": f"{v.major}.{v.minor}.{v.micro}",
        "requirement": ">= 3.11"
    }


def check_packages() -> Dict[str, Any]:
    packages = ["pydantic", "requests", "yaml", "jsonschema", "pytest"]
    missing = []
    installed = {}
    import importlib.metadata

    for pkg in packages:
        try:
            installed[pkg] = importlib.metadata.version(pkg)
        except Exception:
            try:
                mod = __import__(pkg)
                installed[pkg] = getattr(mod, "__version__", "installed")
            except ImportError:
                missing.append(pkg)

    return {
        "check": "Python Dependencies",
        "passed": len(missing) == 0,
        "installed": installed,
        "missing": missing,
        "detail": f"{len(installed)}/{len(packages)} installed"
    }


def check_docker() -> Dict[str, Any]:
    try:
        res = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5
        )
        passed = (res.returncode == 0)
        detail = "Docker daemon is running" if passed else "Docker daemon is NOT running or unreachable"
    except Exception as e:
        passed = False
        detail = f"Docker CLI error: {str(e)}"

    return {
        "check": "Docker Daemon",
        "passed": passed,
        "detail": detail
    }


def check_port(host: str, port: int, timeout: float = 1.0) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, port))
        s.close()
        return True
    except (socket.timeout, ConnectionRefusedError, OSError):
        return False


def check_endpoints() -> Dict[str, Any]:
    settings = Settings()
    targets = {
        "Jaeger UI / API": settings.jaeger_url,
        "Prometheus API": settings.prometheus_url,
        "OpenSearch API": settings.opensearch_url,
        "Frontend Proxy (Envoy)": settings.frontend_proxy_url,
        "Flagd Service": docker_host_url("flagd", 8013) or "http://localhost:8013",
    }

    results = {}
    for name, url in targets.items():
        parts = urlsplit(url)
        host, port = parts.hostname or "localhost", parts.port or 80
        results[name] = {
            "endpoint": f"{host}:{port}",
            "reachable": check_port(host, port, timeout=0.5)
        }

    reachable_count = sum(1 for r in results.values() if r["reachable"])
    return {
        "check": "Demo Service Endpoints",
        "passed": reachable_count > 0,
        "detail": f"{reachable_count}/{len(targets)} reachable (Demo running: {reachable_count > 0})",
        "endpoints": results
    }


def check_safety_controls() -> Dict[str, Any]:
    kill_switch_env = os.environ.get("KILL_SWITCH_ENABLED", "false").lower() in ("true", "1", "yes")
    sentinel_path = Path(__file__).resolve().parent.parent / ".kill_switch"
    kill_switch_file = sentinel_path.exists()
    engaged = kill_switch_env or kill_switch_file

    return {
        "check": "Emergency Kill-Switch",
        "passed": True,  # Check itself passes
        "kill_switch_engaged": engaged,
        "detail": f"Status: {'ENGAGED (Autonomous actions BLOCKED)' if engaged else 'Disengaged (Normal Operation)'}",
        "triggers": {
            "KILL_SWITCH_ENABLED_env": kill_switch_env,
            "sentinel_file_exists": kill_switch_file,
            "sentinel_path": str(sentinel_path)
        }
    }


def main() -> int:
    print("=" * 70)
    print(" Bosch Incident Zero - Environment Diagnostics")
    print("=" * 70)

    checks = [
        check_python_version(),
        check_packages(),
        check_docker(),
        check_endpoints(),
        check_safety_controls(),
    ]

    for c in checks:
        status_marker = "[OK]  " if c["passed"] else "[WARN]"
        print(f"{status_marker} {c['check']:<25} : {c['detail']}")

    print("=" * 70)
    all_critical_passed = checks[0]["passed"] and checks[1]["passed"]
    if not all_critical_passed:
        print("ACTION REQUIRED: Fix missing dependencies or Python version.")
        return 1

    if not checks[2]["passed"]:
        print("NOTE: Docker daemon is not active. Start Docker Desktop to launch the demo.")

    if not checks[3]["passed"]:
        print("NOTE: OpenTelemetry Demo containers are not running yet.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
