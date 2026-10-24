# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0
"""Action API Adapter with dual mode (HTTP client / local Docker-faultctl adapter / mock)."""

import json
import subprocess
import time
from urllib import error, request
import uuid

from .models import ActionCategory, utc_now_iso


class ActionApiAdapter:
    def __init__(self, config: dict):
        self.config = config
        self.mode = config.get("mode", "local_docker")
        self.base_url = config.get("api_url", "http://localhost:8080/action/api").rstrip("/")
        self.timeout_seconds = float(config.get("timeout_seconds", 10.0))
        self.compose_project = config.get("compose_project", "opentelemetry-demo")
        self.allowed_services = set(config.get("services", []))
        self.mock_responses: dict[str, dict] = {}

    def execute(self, action_type: str, target: str, parameters: dict, idempotency_key: str) -> dict:
        start_time = time.perf_counter()
        dispatched_at = utc_now_iso()

        if action_type not in ActionCategory.ALL:
            raise ValueError(f"Action type '{action_type}' is not supported")

        if action_type == ActionCategory.SCALE_SERVICE:
            raise ValueError("scale_service is unsupported in Docker Compose environments")

        if self.mode == "mock":
            res = self._execute_mock(action_type, target, parameters, idempotency_key)
        elif self.mode == "http":
            res = self._execute_http(action_type, target, parameters, idempotency_key)
        elif self.mode == "local_docker":
            res = self._execute_local(action_type, target, parameters)
        else:
            raise ValueError(f"Unknown adapter mode: {self.mode}")

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return {
            "attempt_id": idempotency_key,
            "action_type": action_type,
            "target": target,
            "parameters": parameters,
            "dispatched_at": dispatched_at,
            "duration_ms": duration_ms,
            "status": res.get("status", "ok"),
            "response_data": res.get("data", {}),
            "error_message": res.get("error"),
        }

    def _execute_mock(self, action_type: str, target: str, parameters: dict, key: str) -> dict:
        if key in self.mock_responses:
            return self.mock_responses[key]
        if action_type in self.mock_responses:
            return self.mock_responses[action_type]
        return {
            "status": "ok",
            "data": {
                "message": f"Mock executed {action_type} for {target}",
                "operation": action_type,
                "target": target,
                "parameters": parameters,
            },
        }

    def _execute_http(self, action_type: str, target: str, parameters: dict, idempotency_key: str) -> dict:
        url = f"{self.base_url}/{action_type}"
        payload = json.dumps({
            "target": target,
            "parameters": parameters,
            "idempotency_key": idempotency_key,
        }).encode("utf-8")

        req = request.Request(
            url,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return {"status": "ok", "data": body}
        except error.HTTPError as ex:
            err_body = ex.read().decode("utf-8", errors="replace")
            return {"status": "error", "error": f"HTTP {ex.code}: {err_body}"}
        except Exception as ex:
            return {"status": "error", "error": str(ex)}

    def _execute_local(self, action_type: str, target: str, parameters: dict) -> dict:
        if action_type == ActionCategory.RESTART_SERVICE:
            if self.allowed_services and target not in self.allowed_services:
                return {"status": "error", "error": f"Target service '{target}' not allowlisted"}

            # Check if docker container exists directly with target name
            inspect_proc = subprocess.run(
                ["docker", "inspect", target],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if inspect_proc.returncode == 0:
                cmd = ["docker", "restart", target]
            else:
                cmd = [
                    "docker",
                    "compose",
                    "-p",
                    self.compose_project,
                    "restart",
                    target,
                ]

            try:
                proc = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=self.timeout_seconds,
                    check=False,
                )
                if proc.returncode != 0:
                    return {
                        "status": "error",
                        "error": f"docker restart failed (exit {proc.returncode}): {proc.stderr.strip()}",
                    }
                return {
                    "status": "ok",
                    "data": {"stdout": proc.stdout.strip(), "target": target},
                }
            except subprocess.TimeoutExpired:
                return {"status": "error", "error": f"Restart timed out after {self.timeout_seconds}s"}
            except Exception as ex:
                return {"status": "error", "error": str(ex)}

        elif action_type == ActionCategory.TOGGLE_FEATURE_FLAG:
            desired_state = parameters.get("desired_state", False)
            try:
                import sys
                from pathlib import Path
                src_path = str(Path(__file__).resolve().parent.parent.parent / "src")
                if src_path not in sys.path:
                    sys.path.insert(0, src_path)

                from faultctl.client import FaultClient
                from faultctl import flags
                client = FaultClient()
                cfg = client.read()
                flags_dict = cfg.get("flags", {})
                if target in flags_dict:
                    variant = "on" if desired_state else "off"
                    # If flag is being disabled, resting variant is off
                    target_variant = "off" if not desired_state else "on"
                    available_variants = flags.get_variants(flags_dict[target])
                    if target_variant not in available_variants and desired_state:
                        # pick first non-off variant
                        non_off = [v for v in available_variants if v != "off"]
                        target_variant = non_off[0] if non_off else "on"

                    flags.set_flag(cfg, target, target_variant)
                    client.write(cfg)
                    return {"status": "ok", "data": {"flag": target, "state": desired_state, "variant": target_variant}}
                else:
                    return {"status": "error", "error": f"Flag '{target}' not found in configuration"}
            except Exception as ex:
                return {"status": "error", "error": f"Failed to toggle flag: {ex}"}

        elif action_type == ActionCategory.THROTTLE_LOAD_GENERATOR:
            # Locust API call to change user count or swarm rate if locust is available
            locust_url = self.config.get("locust_url", "http://localhost:8080/loadgen")
            users = parameters.get("users", 10)
            spawn_rate = parameters.get("spawn_rate", 2)
            try:
                req_url = f"{locust_url}/swarm"
                data = json.dumps({"user_count": users, "spawn_rate": spawn_rate}).encode("utf-8")
                req = request.Request(
                    req_url,
                    data=data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    method="POST",
                )
                with request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    return {"status": "ok", "data": {"users": users, "spawn_rate": spawn_rate}}
            except Exception as ex:
                return {"status": "error", "error": f"Failed to throttle Locust: {ex}"}

        return {"status": "error", "error": f"Unsupported local action: {action_type}"}
