# Copyright The OpenTelemetry Authors / Bosch Incident Zero Hackathon
# SPDX-License-Identifier: Apache-2.0

"""
Action API Client with Evidence Consistency Validation.
Enforces that actions are never executed if the system is already in the target state.
"""

import json
import os
import requests
from typing import Dict, Any, Optional

FLAGD_UI_HOST = os.environ.get("FLAGD_UI_HOST", "localhost")
FLAGD_UI_PORT = os.environ.get("FLAGD_UI_PORT", "8080")
FLAGD_READ_URL = f"http://{FLAGD_UI_HOST}:{FLAGD_UI_PORT}/feature/api/read"
FLAGD_WRITE_URL = f"http://{FLAGD_UI_HOST}:{FLAGD_UI_PORT}/feature/api/write"
LOCAL_FLAGD_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "src", "flagd", "demo.flagd.json")


class FlagdActionClient:
    def __init__(self, write_url: Optional[str] = None, read_url: Optional[str] = None):
        self.write_url = write_url or FLAGD_WRITE_URL
        self.read_url = read_url or FLAGD_READ_URL
        self.timeout = 5.0

    def get_current_configuration(self) -> Dict[str, Any]:
        """Fetch the current full flagd configuration."""
        try:
            resp = requests.get(self.read_url, timeout=self.timeout)
            if resp.status_code == 200:
                return resp.json()
        except Exception:
            pass

        norm_path = os.path.abspath(LOCAL_FLAGD_PATH)
        if os.path.exists(norm_path):
            with open(norm_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"flags": {}}

    def reset_flag(self, flag_name: str, target_variant: str = "off", dry_run: bool = False) -> Dict[str, Any]:
        """
        Remediation Action: Set a feature flag back to its resting variant ('off').
        CRITICAL CONSISTENCY CHECK: If the flag is already in target_variant, STOP!
        """
        config = self.get_current_configuration()
        flags = config.get("flags", {})

        if flag_name not in flags:
            return {
                "success": False,
                "consistency_passed": False,
                "action": "RESET_FLAG",
                "flag_name": flag_name,
                "error": f"Consistency Failure: Flag '{flag_name}' does not exist in configuration."
            }

        flag_entry = flags[flag_name]
        previous_variant = str(flag_entry.get("defaultVariant"))
        target_variant_str = str(target_variant)

        # =====================================================================
        # EVIDENCE CONSISTENCY CHECK:
        # If the flag is already in the target variant, halt immediately!
        # =====================================================================
        if previous_variant == target_variant_str:
            return {
                "success": False,
                "consistency_passed": False,
                "action": "RESET_FLAG",
                "flag_name": flag_name,
                "current_variant": previous_variant,
                "target_variant": target_variant_str,
                "error": (
                    f"EVIDENCE CONSISTENCY ERROR: Proposed action would change flag '{flag_name}' "
                    f"to '{target_variant_str}', but it is ALREADY '{previous_variant}'. "
                    "Action is redundant and based on invalid causation. Execution halted for investigation."
                )
            }

        available_variants = [str(k) for k in flag_entry.get("variants", {}).keys()]
        if target_variant_str not in available_variants:
            return {
                "success": False,
                "consistency_passed": False,
                "action": "RESET_FLAG",
                "flag_name": flag_name,
                "error": f"Target variant '{target_variant_str}' not valid. Choose from: {available_variants}"
            }

        if dry_run:
            return {
                "success": True,
                "consistency_passed": True,
                "dry_run": True,
                "action": "RESET_FLAG",
                "flag_name": flag_name,
                "previous_variant": previous_variant,
                "proposed_variant": target_variant_str,
                "message": f"[DRY-RUN] Verified valid state change: '{flag_name}' ({previous_variant} -> {target_variant_str})."
            }

        # Apply mutation
        flags[flag_name]["defaultVariant"] = target_variant
        payload = {"data": {"$schema": "https://flagd.dev/schema/v0/flags.json", "flags": flags}}

        try:
            resp = requests.post(self.write_url, json=payload, headers={"Content-Type": "application/json"}, timeout=self.timeout)
            resp.raise_for_status()
            return {
                "success": True,
                "consistency_passed": True,
                "dry_run": False,
                "action": "RESET_FLAG",
                "flag_name": flag_name,
                "previous_variant": previous_variant,
                "new_variant": target_variant_str,
                "message": f"Successfully updated flag '{flag_name}' from '{previous_variant}' to resting variant '{target_variant_str}' via Action API."
            }
        except Exception as e:
            norm_path = os.path.abspath(LOCAL_FLAGD_PATH)
            if os.path.exists(norm_path):
                try:
                    with open(norm_path, "w", encoding="utf-8") as f:
                        json.dump({"$schema": "https://flagd.dev/schema/v0/flags.json", "flags": flags}, f, indent=2)
                    return {
                        "success": True,
                        "consistency_passed": True,
                        "dry_run": False,
                        "action": "RESET_FLAG",
                        "flag_name": flag_name,
                        "previous_variant": previous_variant,
                        "new_variant": target_variant_str,
                        "message": f"Successfully updated flag '{flag_name}' from '{previous_variant}' to '{target_variant_str}' via local storage sync."
                    }
                except Exception as write_err:
                    return {"success": False, "consistency_passed": False, "error": f"HTTP and disk write failed: {write_err}"}
            return {"success": False, "consistency_passed": False, "error": f"HTTP write failed: {e}"}
