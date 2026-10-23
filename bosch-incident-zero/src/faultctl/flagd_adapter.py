"""Fault controller adapter for OpenFeature Flagd used in the OpenTelemetry Demo."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from .base import FaultController


class FlagdAdapter(FaultController):
    """Controls failure scenarios using the demo's flagd configuration."""

    def __init__(self, flagd_config_path: Path | str) -> None:
        self.config_path = Path(flagd_config_path)

    def _load_config(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            raise FileNotFoundError(f"Flagd config file not found: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_config(self, data: Dict[str, Any]) -> None:
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

    def list_available_faults(self) -> List[str]:
        data = self._load_config()
        return list(data.get("flags", {}).keys())

    def get_fault_state(self, fault_name: str) -> Dict[str, Any]:
        data = self._load_config()
        flag = data.get("flags", {}).get(fault_name)
        if not flag:
            raise KeyError(f"Unknown fault: {fault_name}")
        return {
            "name": fault_name,
            "defaultVariant": flag.get("defaultVariant"),
            "state": flag.get("state"),
            "variants": flag.get("variants", {}),
            "description": flag.get("description", ""),
        }

    def inject_fault(self, fault_name: str, variant: str = "on") -> bool:
        data = self._load_config()
        flags = data.get("flags", {})
        if fault_name not in flags:
            raise KeyError(f"Unknown fault: {fault_name}")

        flag = flags[fault_name]
        variants = flag.get("variants", {})
        if variant not in variants:
            # Pick first non-off variant if 'on' is not explicit
            non_off = [v for v in variants.keys() if v != "off"]
            if non_off:
                variant = non_off[0]
            else:
                raise ValueError(f"Variant '{variant}' not found in {list(variants.keys())}")

        flag["defaultVariant"] = variant
        self._save_config(data)
        return True

    def revert_fault(self, fault_name: str) -> bool:
        data = self._load_config()
        flags = data.get("flags", {})
        if fault_name not in flags:
            raise KeyError(f"Unknown fault: {fault_name}")

        flags[fault_name]["defaultVariant"] = "off"
        self._save_config(data)
        return True
