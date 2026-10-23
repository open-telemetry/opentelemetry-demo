# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
Action API Client for container lifecycle management (Service Restarts).
Used by Teammate 4 (The Hands) when service crashes or memory leaks require a container reboot.
"""

import subprocess
from typing import Dict, Any, List


class DockerActionClient:
    ALLOWED_SERVICES: List[str] = [
        "cart", "product-catalog", "frontend", "checkout", "payment",
        "email", "shipping", "recommendation", "ad", "currency", "quote"
    ]

    PROHIBITED_SERVICES: List[str] = [
        "otel-collector", "jaeger", "prometheus", "opensearch", "grafana",
        "flagd", "flagd-ui", "astronomy-db", "valkey-cart"
    ]

    def restart_service(self, service_name: str, dry_run: bool = False) -> Dict[str, Any]:
        """
        Remediation Action: Restarts a microservice container.
        Enforces strict safety barriers against killing core telemetry or databases.
        """
        if service_name in self.PROHIBITED_SERVICES:
            return {
                "success": False,
                "action": "RESTART_CONTAINER",
                "service_name": service_name,
                "error": f"SAFETY VIOLATION: Service '{service_name}' is a protected core dependency. Autonomous restart is prohibited."
            }

        if service_name not in self.ALLOWED_SERVICES:
            return {
                "success": False,
                "action": "RESTART_CONTAINER",
                "service_name": service_name,
                "error": f"Unknown service '{service_name}'. Permitted services: {self.ALLOWED_SERVICES}"
            }

        if dry_run:
            return {
                "success": True,
                "dry_run": True,
                "action": "RESTART_CONTAINER",
                "service_name": service_name,
                "message": f"[DRY-RUN] Verified restart command for service '{service_name}'."
            }

        try:
            cmd = ["docker", "compose", "restart", service_name]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=30.0, check=False)
            if res.returncode == 0:
                return {
                    "success": True,
                    "dry_run": False,
                    "action": "RESTART_CONTAINER",
                    "service_name": service_name,
                    "message": f"Service '{service_name}' container restarted successfully."
                }
            else:
                return {
                    "success": False,
                    "error": f"docker compose restart failed: {res.stderr.strip() or res.stdout.strip()}"
                }
        except Exception as e:
            return {"success": False, "error": f"Failed to execute container restart: {e}"}
